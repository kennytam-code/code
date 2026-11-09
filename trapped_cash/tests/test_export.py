"""Offline regression tests. Never connect to a real Outlook mailbox."""
import ast
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("trapped_cash_export", ROOT / "trapped_cash_export.py")
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)

TABLE = '''<table><tr><td colspan="5">Daily report</td></tr>
<tr><th>Extra</th><th>Maturity Date</th><th>Trading&nbsp;Book</th>
<th>Effective<br>Date</th><th>Notional</th></tr>
<tr><td>X</td><td>02-Apr-26</td><td rowspan="2">00123</td><td>01-Apr-26</td><td>1,234.50</td></tr>
<tr><td>Y</td><td>03-Apr-26</td><td>01-Apr-26</td><td>(500.00)</td></tr>
<tr><td>Extra</td><td>MaturityDate</td><td>Trading Book</td><td>EffectiveDate</td><td>Notional</td></tr>
<tr><td>Z</td><td>04-Apr-26</td><td>NA</td><td></td><td>0</td></tr>
<tr><td>Z</td><td>04-Apr-26</td><td>NA</td><td></td><td>0</td></tr>
<tr><td></td><td></td><td></td><td></td><td></td></tr></table>'''
BODY = f'<html><body><table><tr><td>Layout{TABLE}</td></tr></table></body></html>'
DAYS = [date(2026, 4, d) for d in (1, 2, 3)]


class Collection:
    def __init__(self, entries):
        self.entries = entries
        self.Count = len(entries)

    def Item(self, key):
        if isinstance(key, str):
            return next(v for v in self.entries if v.Name == key)
        return self.entries[key - 1]


class Items(Collection):
    def Restrict(self, query):
        subjects = {s.replace("''", "'") for s in re.findall(r"\[Subject\] = '((?:[^']|'')*)'", query)}
        return Collection([v for v in self.entries if v.Subject in subjects])


def message(day, hour, entry_id, content=BODY):
    return SimpleNamespace(Class=43, Subject=export.subject_for(day), EntryID=entry_id,
                           ReceivedTime=datetime(2026, 4, 4, hour, tzinfo=timezone.utc),
                           HTMLBody=content)


def mailbox():
    old = message(DAYS[0], 10, "old", "<p>Old incomplete message</p>")
    new = message(DAYS[0], 12, "new")
    bad = message(DAYS[1], 13, "bad", "<p>Missing table</p>")
    reply = message(DAYS[0], 14, "reply")
    reply.Subject = "RE: " + reply.Subject
    folder = SimpleNamespace(Name="Reports", FolderPath="Inbox/Reports", StoreID="store",
                             Folders=Collection([]), Items=Items([new, bad, reply]))
    inbox = SimpleNamespace(Name="Inbox", FolderPath="Inbox", StoreID="store",
                            Folders=Collection([folder]), Items=Items([old]))
    return SimpleNamespace(GetDefaultFolder=lambda _: inbox), inbox, new


class ExportTests(unittest.TestCase):
    def setUp(self):
        for name, value in {"MAILBOX_NAME": None, "FOLDER_PATH": [],
                            "INCLUDE_SUBFOLDERS": True, "INCLUDE_REPORT_DATE": False,
                            "SOURCE_DATE_FORMAT": None}.items():
            patcher = patch.object(export, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def collect(self, namespace, days=DAYS):
        with redirect_stdout(io.StringIO()):
            return export.collect_messages(namespace, days)

    def test_subject_examples_and_calendar_boundaries(self):
        cases = [((2026, 6, 29), "29-Jun-26 to 30-Jun-26"),
                 ((2026, 8, 1), "01-Aug-26 to 02-Aug-26"),
                 ((2026, 4, 30), "30-Apr-26 to 01-May-26"),
                 ((2026, 12, 31), "31-Dec-26 to 01-Jan-27"),
                 ((2028, 2, 28), "28-Feb-28 to 29-Feb-28")]
        for parts, expected in cases:
            with self.subTest(parts=parts):
                self.assertEqual(export.subject_for(date(*parts)), f"Trapped Cash ({expected})")

    def test_nested_layout_reordered_headers_and_merged_cells(self):
        data, tables = export.extract_tables(BODY)
        self.assertEqual(tables, 1)
        self.assertEqual(list(data.columns), export.COLUMNS)
        self.assertEqual(data.iloc[0].tolist(), ["00123", "1,234.50", "01-Apr-26", "02-Apr-26"])
        self.assertEqual(data.iloc[1, 0], "00123")

    def test_repeated_headers_blank_rows_and_duplicate_data(self):
        data, _ = export.extract_tables(BODY)
        self.assertEqual(len(data), 4)
        self.assertEqual(data.iloc[2].tolist(), data.iloc[3].tolist())
        self.assertEqual(data.iloc[2].tolist(), ["NA", "0", "", "04-Apr-26"])

    def test_all_matching_tables_are_included(self):
        data, tables = export.extract_tables(f"<html>{TABLE}{TABLE}</html>")
        self.assertEqual(tables, 2)
        self.assertEqual(len(data), 8)

    def test_empty_table_and_missing_headers_are_distinct(self):
        body = "<table><tr>" + "".join(f"<th>{c}</th>" for c in export.COLUMNS) + "</tr></table>"
        data, tables = export.extract_tables(body)
        self.assertTrue(data.empty)
        self.assertEqual(tables, 1)
        for invalid in ["", "<p>No table</p>", TABLE.replace("Notional", "Amount")]:
            with self.subTest(invalid=invalid[:40]), self.assertRaises(ValueError):
                export.extract_tables(invalid)

    def test_duplicate_headers_are_rejected(self):
        headers = export.COLUMNS + ["Notional"]
        body = "<table><tr>" + "".join(f"<td>{c}</td>" for c in headers) + "</tr></table>"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            export.extract_tables(body)

    def test_source_dates_are_converted_only_with_explicit_format(self):
        export.SOURCE_DATE_FORMAT = "%d-%b-%y"
        data, _ = export.extract_tables(BODY)
        self.assertEqual(data.iloc[0]["EffectiveDate"], DAYS[0])
        self.assertIsNone(data.iloc[2]["EffectiveDate"])
        with self.assertRaises(ValueError):
            export.extract_tables(BODY.replace("01-Apr-26", "not a date"))

    def test_latest_email_delayed_delivery_and_reply_exclusion(self):
        namespace, _, new = mailbox()
        latest, counts = self.collect(namespace)
        self.assertEqual(counts, {DAYS[0]: 2, DAYS[1]: 1})
        self.assertIs(latest[DAYS[0]]["message"], new)
        self.assertEqual(latest[DAYS[0]]["folder"], "Inbox/Reports")

    def test_configured_subfolder_and_disabled_recursion(self):
        namespace, _, new = mailbox()
        export.FOLDER_PATH = ["Reports"]
        latest, counts = self.collect(namespace)
        self.assertIs(latest[DAYS[0]]["message"], new)
        self.assertEqual(counts[DAYS[0]], 1)
        export.FOLDER_PATH = []
        export.INCLUDE_SUBFOLDERS = False
        latest, counts = self.collect(namespace)
        self.assertEqual(latest[DAYS[0]]["message"].EntryID, "old")
        self.assertNotIn(DAYS[1], latest)

    def test_explicit_mailbox(self):
        namespace, inbox, new = mailbox()
        export.MAILBOX_NAME = "Reports Mailbox"
        root = SimpleNamespace(Name=export.MAILBOX_NAME,
                               Store=SimpleNamespace(GetDefaultFolder=lambda _: inbox))
        namespace.Folders = Collection([root])
        latest, _ = self.collect(namespace)
        self.assertIs(latest[DAYS[0]]["message"], new)

    def test_subject_batches_cover_more_than_25_days(self):
        days = pd.date_range("2026-04-01", "2026-05-10").date.tolist()
        inbox = SimpleNamespace(FolderPath="Inbox", StoreID="store", Folders=Collection([]),
                                Items=Items([message(d, 12, str(d)) for d in days]))
        latest, counts = self.collect(SimpleNamespace(GetDefaultFolder=lambda _: inbox), days)
        self.assertEqual(set(latest), set(days))
        self.assertTrue(all(counts[d] == 1 for d in days))

    def test_log_status_and_row_ranges(self):
        namespace, _, _ = mailbox()
        latest, counts = self.collect(namespace)
        data, log = export.assemble_report(DAYS, latest, counts)
        self.assertEqual(len(data), 4)
        self.assertEqual(log.Status.tolist(), ["Extracted", "Extraction error", "Missing email"])
        self.assertEqual(log.iloc[0].ExcelFirstRow, 2)
        self.assertEqual(log.iloc[0].ExcelLastRow, 5)
        self.assertIn("Latest", log.iloc[0].Details)
        export.INCLUDE_REPORT_DATE = True
        dated, _ = export.assemble_report(DAYS, latest, counts)
        self.assertEqual(list(dated.columns), ["ReportDate"] + export.COLUMNS)
        self.assertEqual(dated.iloc[0].ReportDate, DAYS[0])

    def test_latest_bad_email_does_not_fall_back_to_stale_data(self):
        namespace, inbox, new = mailbox()
        inbox.Items.Item(1).HTMLBody = BODY
        new.HTMLBody = "<p>No current table</p>"
        latest, counts = self.collect(namespace)
        data, log = export.assemble_report(DAYS, latest, counts)
        self.assertTrue(data.empty)
        self.assertEqual(log.iloc[0].Status, "Extraction error")

    def test_missing_every_day_still_has_headers(self):
        data, log = export.assemble_report(DAYS, {}, {})
        self.assertEqual(list(data.columns), export.COLUMNS)
        self.assertTrue(data.empty)
        self.assertEqual(log.Status.tolist(), ["Missing email"] * 3)

    def test_search_failure_is_not_reported_as_missing_mail(self):
        namespace, inbox, _ = mailbox()
        inbox.Items.Restrict = MagicMock(side_effect=RuntimeError("Access denied"))
        with self.assertRaisesRegex(RuntimeError, "Access denied"):
            self.collect(namespace)

    def test_saved_excel_preserves_values_and_literal_text(self):
        namespace, _, _ = mailbox()
        latest, counts = self.collect(namespace)
        data, log = export.assemble_report(DAYS, latest, counts)
        data.loc[len(data)] = ["=1+1", "999999999999999999", "01/02/2026", ""]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "report.xlsx"
            export.write_excel(data, log, output)
            wb = load_workbook(output)
            try:
                self.assertEqual(wb.sheetnames, ["Data", "ExtractionLog"])
                sheet = wb["Data"]
                self.assertEqual((sheet.max_row, sheet.max_column), (6, 4))
                self.assertEqual(sheet["A2"].value, "00123")
                self.assertEqual(sheet["A4"].value, "NA")
                self.assertEqual((sheet["A6"].value, sheet["A6"].data_type), ("=1+1", "s"))
                self.assertEqual(sheet["B6"].value, "999999999999999999")
                self.assertEqual(sheet.freeze_panes, "A2")
                self.assertEqual(sheet.auto_filter.ref, "A1:D6")
                self.assertIsInstance(wb["ExtractionLog"]["A2"].value, datetime)
            finally:
                wb.close()

    def test_notebook_has_same_definitions_as_script(self):
        notebook = json.loads((ROOT / "trapped_cash_export.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(notebook["nbformat"], 4)
        self.assertEqual(sum(c["cell_type"] == "code" for c in notebook["cells"]), 2)
        definitions = []
        for cell in notebook["cells"]:
            if cell["cell_type"] != "code":
                continue
            self.assertEqual(cell["outputs"], [])
            source = "".join(cell["source"])
            if source.startswith("%"):
                continue
            compile(source, "notebook", "exec")
            definitions.extend(ast.parse(source).body)
        script = ast.parse((ROOT / "trapped_cash_export.py").read_text(encoding="utf-8"))
        # The complete second cell can be copied directly into a blank notebook.
        self.assertEqual([ast.dump(node) for node in definitions],
                         [ast.dump(node) for node in script.body])

    def test_complete_export_with_simulated_outlook(self):
        namespace, _, _ = mailbox()
        client = ModuleType("win32com.client")
        client.Dispatch = MagicMock(return_value=SimpleNamespace(GetNamespace=lambda _: namespace))
        package = ModuleType("win32com")
        package.client = client
        pythoncom = ModuleType("pythoncom")
        pythoncom.CoInitialize = MagicMock()
        pythoncom.CoUninitialize = MagicMock()
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(export, "sys", SimpleNamespace(platform="win32")), \
                patch.object(export, "START_DATE", DAYS[0]), \
                patch.object(export, "END_DATE", DAYS[-1]), \
                patch.object(export, "OUTPUT_DIR", Path(temp)), \
                patch.dict(sys.modules, {"win32com": package, "win32com.client": client,
                                         "pythoncom": pythoncom}), \
                redirect_stdout(io.StringIO()):
            data, log, output = export.run_export()
            self.assertEqual(len(data), 4)
            self.assertEqual(len(log), 3)
            self.assertTrue(output.is_file())
            _, _, another = export.run_export()
            self.assertNotEqual(output, another)
            self.assertTrue(output.is_file())
        self.assertEqual(pythoncom.CoInitialize.call_count, 2)
        self.assertEqual(pythoncom.CoUninitialize.call_count, 2)

    def test_non_windows_gives_clear_error(self):
        with patch.object(export, "sys", SimpleNamespace(platform="darwin")):
            with self.assertRaisesRegex(RuntimeError, "Windows with classic Outlook"):
                export.run_export()


if __name__ == "__main__":
    unittest.main()
