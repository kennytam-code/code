# Paste this entire block into ONE Jupyter cell (Windows + classic Outlook + Excel).
# If needed, install once in Jupyter: %pip install pywin32

from pathlib import Path
from datetime import date, datetime, timedelta
from collections import defaultdict
from tempfile import TemporaryDirectory
import csv
import io
import re
import sys

try:
    import win32com.client as win32
except ImportError as exc:
    raise RuntimeError("pywin32 is missing. Run %pip install pywin32 in Jupyter first.") from exc

# ============== SETTINGS ==============
START_DATE = date(2026, 4, 1)
END_DATE = date.today()
SEARCH_WHOLE_MAILBOX = True  # True: Inbox plus other folders in your default mailbox
INCLUDE_WEEKDAYS_WITH_NO_EMAIL = True
OUTPUT_DIR = Path.cwd()
# ======================================

NOMURA_SUBJECT = re.compile(
    r"^\s*(?:(?:RE|FW|FWD)\s*:\s*)*Futures Nomura International Plc Summary Report\s+(\d{4}-\d{2}-\d{2})\s*$",
    re.IGNORECASE,
)
SINOPAC_SUBJECT = re.compile(
    r"^\s*(?:(?:RE|FW|FWD)\s*:\s*)*(\d{1,2})/(\d{1,2})\s+Nomura Daily Statement\s*\(From SinoPac Futures\)\s*$",
    re.IGNORECASE,
)
SINOPAC_FILE = re.compile(r"^1263583_(\d{8})\.csv$", re.IGNORECASE)
EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb"}


def report_date_from_subject(subject, received_date):
    m = NOMURA_SUBJECT.fullmatch(subject)
    if m:
        try:
            return "Nomura", date.fromisoformat(m.group(1))
        except ValueError:
            return None, None
    m = SINOPAC_SUBJECT.fullmatch(subject)
    if m:
        month, day = map(int, m.groups())
        possible = []
        for yr in (received_date.year - 1, received_date.year, received_date.year + 1):
            try:
                possible.append(date(yr, month, day))
            except ValueError:
                pass
        if possible:
            closest = min(possible, key=lambda x: abs((x - received_date).days))
            return "SinoPac", closest
    return None, None


def folders_under(root):
    yield root
    try:
        children = list(root.Folders)
    except Exception as exc:
        print(f"Cannot list subfolders of {root.Name}: {exc}")
        return
    for child in children:
        yield from folders_under(child)


def fast_items(folder):
    # Outlook first filters on subject, so we avoid reading unrelated messages.
    subject_sql = (
        '@SQL=("urn:schemas:httpmail:subject" LIKE '
        "'%Futures Nomura International Plc Summary Report%' OR "
        '"urn:schemas:httpmail:subject" LIKE '
        "'%Nomura Daily Statement%')"
    )
    try:
        return folder.Items.Restrict(subject_sql)
    except Exception:
        # Fallback for Outlook stores that cannot run this subject restriction.
        from_date = (START_DATE - timedelta(days=7)).strftime("%m/%d/%Y %I:%M %p")
        try:
            return folder.Items.Restrict(f"[ReceivedTime] >= '{from_date}'")
        except Exception:
            return folder.Items


def norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def clean_number(value):
    if value is None or isinstance(value, (int, float)):
        return value
    s = str(value).strip()
    if not s or s in {"-", "--"}:
        return None
    cleaned = s.replace(",", "").replace("$", "").replace(" ", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return float(cleaned)
    except ValueError:
        return s


def read_nomura(mail, excel, temp_dir):
    attached = [a for a in mail.Attachments
                if Path(str(a.FileName)).suffix.lower() in EXCEL_EXTENSIONS]
    if not attached:
        raise ValueError("No Excel attachment (.xls/.xlsx/.xlsm/.xlsb)")
    last_error = None
    for ix, attachment in enumerate(attached, 1):
        filename = str(attachment.FileName)
        saved = Path(temp_dir) / f"nomura_{ix}{Path(filename).suffix.lower()}"
        attachment.SaveAsFile(str(saved))
        wb = None
        try:
            wb = excel.Workbooks.Open(str(saved), UpdateLinks=0, ReadOnly=True)
            for sheet in wb.Worksheets:
                last_row = sheet.Cells(sheet.Rows.Count, 1).End(-4162).Row  # xlUp
                first_col = sheet.Range(f"A1:A{last_row}").Value2
                values = [first_col] if last_row == 1 else [row[0] for row in first_col]
                for row_num, label in enumerate(values, start=1):
                    if norm(label) == "equity":
                        result = [sheet.Cells(row_num, c).Value2 for c in (8, 10, 12)]
                        return [clean_number(v) for v in result], filename, f"Sheet: {sheet.Name}; row: {row_num}"
            last_error = "'Equity' not found in column A of any worksheet"
        except Exception as exc:
            last_error = str(exc)
        finally:
            if wb is not None:
                wb.Close(SaveChanges=False)
    raise ValueError(last_error or "Could not read Excel attachment")


def decode_csv(raw):
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp950", "big5", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def read_sinopac(mail, report_day, temp_dir):
    options = []
    for attachment in mail.Attachments:
        filename = str(attachment.FileName)
        m = SINOPAC_FILE.fullmatch(filename.strip())
        if m:
            options.append((m.group(1), attachment, filename))
    if not options:
        raise ValueError("Attachment 1263583_MMDDYYYY.csv not found")
    next_day = (report_day + timedelta(days=1)).strftime("%m%d%Y")
    matching = [o for o in options if o[0] == next_day]
    if matching:
        chosen = matching[0]
    elif len(options) == 1:
        chosen = options[0]  # Still accept it if the filename date differs.
    else:
        raise ValueError("Multiple 1263583 CSV files; none dated next day")

    _, attachment, filename = chosen
    saved = Path(temp_dir) / "sinopac_statement.csv"
    attachment.SaveAsFile(str(saved))
    content = decode_csv(saved.read_bytes())
    try:
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(content, newline=""), dialect)
    for row_number, row in enumerate(reader, 1):
        if len(row) >= 8 and norm(row[1]) == "account equity":
            return [clean_number(row[c]) for c in (3, 5, 7)], filename, f"CSV row: {row_number}"
    raise ValueError("'Account Equity' not found in CSV column B")


def excel_rgb(r, g, b):
    return r + (g << 8) + (b << 16)


def format_worksheet(sheet, width_count):
    last_row = max(1, sheet.UsedRange.Rows.Count)
    last_col = chr(ord("A") + width_count - 1)
    rng = sheet.Range(f"A1:{last_col}{last_row}")
    rng.Font.Name = "Times New Roman"
    rng.Font.Size = 11
    hdr = sheet.Range(f"A1:{last_col}1")
    hdr.Font.Bold = True
    hdr.Font.Color = excel_rgb(255, 255, 255)
    hdr.Interior.Color = excel_rgb(30, 50, 85)
    hdr.RowHeight = 24
    sheet.Columns(f"A:{last_col}").AutoFit()
    sheet.Range(f"A1:{last_col}{last_row}").AutoFilter()


# --- Connect to desktop Outlook and Excel ---
if sys.platform != "win32":
    raise RuntimeError("Run this Jupyter cell on Windows with classic Outlook and Excel installed.")

outlook = win32.Dispatch("Outlook.Application").GetNamespace("MAPI")
inbox = outlook.GetDefaultFolder(6)  # 6 = olFolderInbox
root = inbox.Parent if SEARCH_WHOLE_MAILBOX else inbox
excel = win32.DispatchEx("Excel.Application")
excel.Visible = False
excel.DisplayAlerts = False
excel.ScreenUpdating = False
try:
    excel.AutomationSecurity = 3  # Disable macros in downloaded workbooks
except Exception:
    pass

try:
    hits = {"Nomura": defaultdict(list), "SinoPac": defaultdict(list)}
    checked_folders = 0
    matched_emails = 0

    print(f"Searching Outlook: {START_DATE} through {END_DATE} ...", flush=True)
    for folder in folders_under(root):
        try:
            if folder.DefaultItemType != 0:  # mail folders only
                continue
            checked_folders += 1
            items = fast_items(folder)
            for mail in items:
                try:
                    if mail.Class != 43:  # 43 = MailItem
                        continue
                    subject = str(mail.Subject or "")
                    received = mail.ReceivedTime.replace(tzinfo=None)
                    kind, day = report_date_from_subject(subject, received.date())
                    if kind and day and START_DATE <= day <= END_DATE:
                        hits[kind][day].append({
                            "entry": str(mail.EntryID),
                            "store": str(folder.StoreID),
                            "received": received,
                            "subject": subject,
                            "folder": str(folder.FolderPath),
                        })
                        matched_emails += 1
                except Exception:
                    continue
        except Exception as exc:
            print(f"Skipping folder {folder.Name}: {exc}")

    print(f"Searched {checked_folders} mail folders; found {matched_emails} matching emails.", flush=True)

    extracted = {"Nomura": {}, "SinoPac": {}}
    with TemporaryDirectory(prefix="outlook_report_") as tmp:
        for kind in ("Nomura", "SinoPac"):
            for day, candidates in sorted(hits[kind].items()):
                errors = []
                successful = None
                for item in sorted(candidates, key=lambda x: x["received"], reverse=True):
                    try:
                        mail = outlook.GetItemFromID(item["entry"], item["store"])
                        if kind == "Nomura":
                            nums, filename, detail = read_nomura(mail, excel, tmp)
                        else:
                            nums, filename, detail = read_sinopac(mail, day, tmp)
                        successful = dict(values=nums, status="OK", subject=item["subject"],
                                          attachment=filename, folder=item["folder"],
                                          received=item["received"], detail=detail)
                        break
                    except Exception as exc:
                        errors.append(str(exc))
                if successful is None:
                    last = candidates[0]
                    successful = dict(values=[None] * 3, status="ERROR", subject=last["subject"],
                                      attachment="", folder=last["folder"],
                                      received=last["received"], detail=" | ".join(errors[:3]))
                extracted[kind][day] = successful

    all_days = set(extracted["Nomura"]) | set(extracted["SinoPac"])
    if INCLUDE_WEEKDAYS_WITH_NO_EMAIL:
        day = START_DATE
        while day <= END_DATE:
            if day.weekday() < 5:
                all_days.add(day)
            day += timedelta(days=1)

    summary = [["Report Date", "Nomura H", "Nomura J", "Nomura L",
                "SinoPac D", "SinoPac F", "SinoPac H", "Nomura Status", "SinoPac Status"]]
    audit = [["Report Date", "Source", "Status", "Subject", "Attachment",
              "Outlook Folder", "Received Time", "Details"]]
    for day in sorted(all_days):
        n = extracted["Nomura"].get(day)
        s = extracted["SinoPac"].get(day)
        summary.append([day.isoformat(), *(n["values"] if n else [None] * 3),
                        *(s["values"] if s else [None] * 3),
                        n["status"] if n else "NOT FOUND", s["status"] if s else "NOT FOUND"])
        for kind, info in (("Nomura", n), ("SinoPac", s)):
            audit.append([day.isoformat(), kind, info["status"] if info else "NOT FOUND",
                          info["subject"] if info else "", info["attachment"] if info else "",
                          info["folder"] if info else "",
                          info["received"].strftime("%Y-%m-%d %H:%M") if info else "",
                          info["detail"] if info else "No matching email found"])

    workbook = excel.Workbooks.Add(-4167)  # Create exactly one worksheet
    try:
        main = workbook.Worksheets(1)
        main.Name = "Daily Summary"
        main.Columns("A").NumberFormat = "@"  # keep ISO dates as text
        main.Range(f"A1:I{len(summary)}").Value = tuple(tuple(r) for r in summary)
        format_worksheet(main, 9)
        main.Range(f"B2:G{len(summary)}").NumberFormat = "#,##0.00########;[Red](#,##0.00########)"
        main.Columns("A").ColumnWidth = 15
        main.Columns("H:I").ColumnWidth = 18

        detail_sheet = workbook.Worksheets.Add(After=main)
        detail_sheet.Name = "Audit"
        detail_sheet.Columns("A").NumberFormat = "@"
        detail_sheet.Range(f"A1:H{len(audit)}").Value = tuple(tuple(r) for r in audit)
        format_worksheet(detail_sheet, 8)
        detail_sheet.Columns("D").ColumnWidth = 57
        detail_sheet.Columns("F").ColumnWidth = 40
        detail_sheet.Columns("H").ColumnWidth = 65

        main.Activate()
        try:
            excel.ActiveWindow.SplitRow = 1
            excel.ActiveWindow.FreezePanes = True
        except Exception:
            pass

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"Outlook_Equity_{START_DATE:%Y%m%d}_to_{END_DATE:%Y%m%d}"
        output = OUTPUT_DIR / (filename + ".xlsx")
        i = 2
        while output.exists():
            output = OUTPUT_DIR / f"{filename}_{i}.xlsx"
            i += 1
        workbook.SaveAs(str(output), FileFormat=51)  # .xlsx
    finally:
        workbook.Close(SaveChanges=False)

    n_ok = sum(x["status"] == "OK" for x in extracted["Nomura"].values())
    s_ok = sum(x["status"] == "OK" for x in extracted["SinoPac"].values())
    print(f"Nomura extracted: {n_ok} days")
    print(f"SinoPac extracted: {s_ok} days")
    print(f"Saved Excel summary to:\n{output}")
except Exception:
    raise
finally:
    excel.Quit()
