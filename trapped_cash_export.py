"""Read daily Trapped Cash HTML tables from classic Outlook on Windows.

Jupyter: install pandas lxml openpyxl pywin32, then run this file or its notebook.
Mail is read only. Re-running creates a fresh Excel export, not an append.
"""

# %% Settings
from datetime import date, datetime, timedelta
from pathlib import Path
import re
import sys

import pandas as pd
from lxml import html
from openpyxl.styles import Font, PatternFill

START_DATE = date(2026, 4, 1)
END_DATE = date.today()  # Inclusive; uses the Jupyter computer's local date.
MAILBOX_NAME = None  # None = default mailbox; otherwise its Outlook display name.
FOLDER_PATH = []  # Relative to Inbox, e.g. ["Reports", "Trapped Cash"].
INCLUDE_SUBFOLDERS = True
INCLUDE_REPORT_DATE = False  # True adds ReportDate before the four requested columns.
OUTPUT_DIR = Path.cwd()

# Keep source values as text by default, including leading zeros and date formats.
# Optional: set the exact source format, e.g. "%d/%m/%Y", to create Excel dates.
SOURCE_DATE_FORMAT = None

COLUMNS = ["Trading Book", "Notional", "EffectiveDate", "MaturityDate"]
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


# %% Subject generation and HTML table extraction
def subject_for(day):
    """English month names, independent of the computer's language settings."""
    def fmt(d):
        return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year % 100:02d}"
    return f"Trapped Cash ({fmt(day)} to {fmt(day + timedelta(days=1))})"


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def table_grid(table):
    """Expand merged cells; exclude rows belonging to nested layout tables."""
    rows = [r for r in table.xpath(".//tr")
            if r.xpath("ancestor::table[1]")[0] is table]
    grid = {}
    for r, row in enumerate(rows):
        c = 0
        for cell in row.xpath("./th | ./td"):
            while (r, c) in grid:
                c += 1
            value = re.sub(r"\s+", " ", " ".join(cell.itertext())).strip()
            rs = int(cell.get("rowspan", "1"))
            cs = int(cell.get("colspan", "1"))
            rs = len(rows) - r if rs == 0 else rs
            if not (1 <= rs <= len(rows) and 1 <= cs <= 16384):
                raise ValueError("Unsupported HTML table span.")
            for dr in range(rs):
                for dc in range(cs):
                    if (r + dr, c + dc) in grid:
                        raise ValueError("Overlapping merged cells in HTML table.")
                    grid[r + dr, c + dc] = value
            c += cs
    width = max((c for _, c in grid), default=-1) + 1
    return [[grid.get((r, c), "") for c in range(width)]
            for r in range(len(rows))]


def extract_tables(body):
    """Find the requested headers anywhere in the body, regardless of order."""
    if not body or not body.strip():
        raise ValueError("Email has no HTML body; check Outlook synchronization.")
    document = html.document_fromstring(body)
    wanted = [normalize(c) for c in COLUMNS]
    matches = []
    for table in document.xpath("//table"):
        # Ignore unrelated layout tables before expanding their cells.
        cell_labels = {normalize(" ".join(cell.itertext()))
                       for cell in table.xpath(".//th | .//td")}
        if not set(wanted).issubset(cell_labels):
            continue
        grid = table_grid(table)
        for header_row, row in enumerate(grid):
            labels = [normalize(v) for v in row]
            if not set(wanted).issubset(labels):
                continue
            if any(labels.count(key) != 1 for key in wanted):
                raise ValueError("A table has duplicate requested column headers.")
            positions = [labels.index(key) for key in wanted]
            records = []
            for values in grid[header_row + 1:]:
                selected = [values[p] for p in positions]
                if not any(selected):
                    continue
                if [normalize(v) for v in selected] == wanted:
                    continue  # Repeated header, not a trade.
                records.append(selected)
            matches.append((table, pd.DataFrame(records, columns=COLUMNS)))
            break
    if not matches:
        raise ValueError("No HTML table has all four requested headers. "
                         "Image tables and attachments are not supported.")
    # Avoid reading the same table through a surrounding HTML layout table.
    parents = {a for table, _ in matches for a in table.iterancestors("table")}
    frames = [frame for table, frame in matches if table not in parents]
    result = pd.concat(frames, ignore_index=True)
    if SOURCE_DATE_FORMAT:
        for column in ["EffectiveDate", "MaturityDate"]:
            result[column] = result[column].map(
                lambda value: datetime.strptime(value, SOURCE_DATE_FORMAT).date()
                if value else None
            )
    return result, len(frames)


# %% Outlook access (Windows with classic Outlook only)
def walk_folders(folder):
    yield folder
    if INCLUDE_SUBFOLDERS:
        for i in range(1, folder.Folders.Count + 1):
            yield from walk_folders(folder.Folders.Item(i))


def collect_messages(namespace, days):
    if MAILBOX_NAME:
        root = namespace.Folders.Item(MAILBOX_NAME)
        inbox = root.Store.GetDefaultFolder(6)  # olFolderInbox
    else:
        inbox = namespace.GetDefaultFolder(6)
    for name in FOLDER_PATH:
        inbox = inbox.Folders.Item(name)

    expected = {subject_for(d).casefold(): d for d in days}
    subjects = [subject_for(d) for d in days]
    latest, counts, seen = {}, {}, set()
    for folder in walk_folders(inbox):
        print(f"Searching {folder.FolderPath}", flush=True)
        # Batch exact subject queries. No received-date cutoff: delayed emails
        # still belong to the report date written in their subject.
        for offset in range(0, len(subjects), 25):
            batch = subjects[offset:offset + 25]
            query = " OR ".join("[Subject] = '" + s.replace("'", "''") + "'"
                                for s in batch)
            items = folder.Items.Restrict(query)
            for i in range(1, items.Count + 1):
                message = items.Item(i)
                if message.Class != 43:  # olMail
                    continue
                subject = str(message.Subject or "").strip()
                day = expected.get(subject.casefold())
                if day is None:
                    continue  # Excludes RE:/FW: subjects and unrelated mail.
                key = (str(folder.StoreID), str(message.EntryID))
                if key in seen:
                    continue
                seen.add(key)
                received = message.ReceivedTime
                received_key = received.timestamp()
                counts[day] = counts.get(day, 0) + 1
                if day not in latest or received_key > latest[day]["sort_time"]:
                    latest[day] = {
                        "message": message,
                        "sort_time": received_key,
                        "received": received.isoformat(),
                        "folder": str(folder.FolderPath),
                    }
    return latest, counts


def assemble_report(days, latest, counts):
    frames, log = [], []
    next_excel_row = 2
    for day in days:
        record = {"ReportDate": day, "Subject": subject_for(day),
                  "EmailsFound": counts.get(day, 0), "Status": "Missing email",
                  "Rows": 0, "Tables": 0, "ExcelFirstRow": None,
                  "ExcelLastRow": None, "ReceivedTime": "", "Folder": "",
                  "Details": ""}
        source = latest.get(day)
        if source:
            record.update(ReceivedTime=source["received"], Folder=source["folder"])
            try:
                frame, table_count = extract_tables(source["message"].HTMLBody)
                record.update(Rows=len(frame), Tables=table_count,
                              Status="Extracted" if len(frame) else "Empty table")
                if counts[day] > 1:
                    record["Details"] = "Latest received matching email selected."
                if len(frame):
                    record.update(ExcelFirstRow=next_excel_row,
                                  ExcelLastRow=next_excel_row + len(frame) - 1)
                    next_excel_row += len(frame)
                if INCLUDE_REPORT_DATE:
                    frame.insert(0, "ReportDate", day)
                frames.append(frame)
            except Exception as exc:
                record.update(Status="Extraction error", Details=str(exc))
        log.append(record)
    columns = (["ReportDate"] if INCLUDE_REPORT_DATE else []) + COLUMNS
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    return data, pd.DataFrame(log)


# %% Excel export and execution
def write_excel(data, log, output):
    if len(data) > 1_048_575:
        raise ValueError("Data exceeds Excel's single-sheet row limit.")
    with pd.ExcelWriter(output, engine="openpyxl", date_format="dd-mmm-yyyy") as writer:
        data.to_excel(writer, sheet_name="Data", index=False)
        log.to_excel(writer, sheet_name="ExtractionLog", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="17365D")
            for cells in sheet.columns:
                width = min(65, max(16, max(len(str(c.value or "")) for c in cells) + 2))
                sheet.column_dimensions[cells[0].column_letter].width = width
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    # Treat email content literally, including values starting '='.
                    if isinstance(cell.value, str):
                        cell.data_type = "s"
                    elif isinstance(cell.value, (date, datetime)):
                        cell.number_format = "dd-mmm-yyyy"


def run_export():
    if sys.platform != "win32":
        raise RuntimeError("Run this notebook on Windows with classic Outlook. "
                           "New Outlook, Outlook Web, and Mac require another connector.")
    if START_DATE > END_DATE:
        raise ValueError("START_DATE is after END_DATE.")
    import pythoncom
    import win32com.client

    days = [START_DATE + timedelta(days=i)
            for i in range((END_DATE - START_DATE).days + 1)]
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        latest, counts = collect_messages(namespace, days)
        data, log = assemble_report(days, latest, counts)
        latest.clear()  # Release saved message objects before COM cleanup.
        namespace = outlook = None
    finally:
        pythoncom.CoUninitialize()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output = OUTPUT_DIR / f"Trapped_Cash_{START_DATE:%Y%m%d}_{END_DATE:%Y%m%d}_{stamp}.xlsx"
    write_excel(data, log, output)
    print(f"\nSaved {len(data):,} rows to {output.resolve()}")
    print(log["Status"].value_counts().to_string())
    print("Review ExtractionLog for missing dates, duplicates, and errors.")
    return data, log, output


if __name__ == "__main__":
    data, extraction_log, output_file = run_export()
