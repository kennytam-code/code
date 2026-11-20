# NOMURA OUTLOOK DIAGNOSTIC — paste this entire script into ONE Jupyter cell.
# Windows + classic Outlook only. Needs pywin32 (%pip install pywin32).
# READ ONLY: does not delete, move, send, or alter email.
# Focuses on a KNOWN example first, instead of slowly processing all of April-now.

import sys
import re
import traceback
from pathlib import Path
from datetime import date, datetime, timedelta
from tempfile import TemporaryDirectory

# ------- EDIT ONLY IF YOU WANT TO CHECK A DIFFERENT KNOWN DATE -------
CHECK_REPORT_DATE = date(2026, 11, 18)
# Report received around the subject date. Increase if it was delivered much later.
DAYS_BEFORE = 5
DAYS_AFTER = 5
# Outlook date filters can silently produce zero. Try direct scans of Inbox folders.
MAX_FALLBACK_MESSAGES_PER_INBOX = 15000
MAX_INBOX_FOLDERS_TO_FALLBACK = 12
# ---------------------------------------------------------------------

if sys.platform != "win32":
    raise RuntimeError("Run on Windows in Jupyter with classic Outlook installed.")
try:
    import win32com.client as win32
except ImportError as exc:
    raise RuntimeError("Install once in Jupyter using: %pip install pywin32") from exc

subject_regex = re.compile(
    r"(?:Yuanta\s+)?Futures\s+Nomura\s+International\s+Plc\s+Summary\s+Report\s+(\d{4}-\d{2}-\d{2})",
    flags=re.IGNORECASE,
)
file_regex = re.compile(r"^Nomura_Summary_Report_(\d{8})\.(xlsx|xlsm|xls|xlsb)$", re.I)
start_day = CHECK_REPORT_DATE - timedelta(days=DAYS_BEFORE)
end_day = min(date.today() + timedelta(days=2), CHECK_REPORT_DATE + timedelta(days=DAYS_AFTER + 1))
if end_day <= start_day:
    end_day = CHECK_REPORT_DATE + timedelta(days=DAYS_AFTER + 1)
log_file = Path.cwd() / f"Nomura_Outlook_DEBUG_{datetime.now():%Y%m%d_%H%M%S}.txt"
log_lines = []


def log(message=""):
    text = str(message)
    print(text, flush=True)
    log_lines.append(text)


def err(label, exc):
    log(f"[ERROR] {label}: {type(exc).__name__}: {exc}")
    log_lines.append(traceback.format_exc(limit=5))


def safe(obj, prop, fallback="?"):
    try:
        value = getattr(obj, prop)
        return str(value) if value is not None else fallback
    except Exception:
        return fallback


def label(v):
    return re.sub(r"\s+", " ", str(v or "").replace("\xa0", " ")).strip().casefold()


def mail_date(msg):
    try:
        return msg.ReceivedTime.date()
    except Exception:
        return None


def get_folders(session):
    roots, folder_rows, seen = [], [], set()
    try:
        roots = list(session.Folders)  # All mailbox roots visible in current Outlook profile
    except Exception as exc:
        err("Cannot enumerate Outlook mailbox roots", exc)
    if not roots:
        try:
            roots = [session.GetDefaultFolder(6).Parent]
        except Exception as exc:
            err("Cannot access default Inbox", exc)
    log("[MAILBOX ROOTS] " + (" | ".join(safe(r, "Name") for r in roots) or "NONE"))
    try:
        log("[DEFAULT INBOX] " + str(session.GetDefaultFolder(6).FolderPath))
    except Exception as exc:
        err("Cannot read default Inbox path", exc)

    for root in roots:
        pending = [root]
        while pending:
            f = pending.pop()
            path = safe(f, "FolderPath", safe(f, "Name"))
            try:
                key = (safe(f, "EntryID"), safe(f, "StoreID"))
                if key in seen:
                    continue
                seen.add(key)
            except Exception:
                pass
            try:
                pending.extend(list(f.Folders))
            except Exception as exc:
                err(f"Cannot enumerate subfolders of {path}", exc)
            try:
                if int(f.DefaultItemType) == 0:  # 0 = Mail folder
                    folder_rows.append((f, path))
            except Exception as exc:
                err(f"Cannot inspect folder type: {path}", exc)

    folder_rows.sort(key=lambda p: (not any(x in p[1].casefold() for x in ("big inbox", "inbox", "收件箱")), p[1].casefold()))
    inbox_paths = [p for _, p in folder_rows if any(x in p.casefold() for x in ("big inbox", "inbox", "收件箱"))]
    log(f"[FOLDERS] {len(folder_rows)} mail folders visible; {len(inbox_paths)} Inbox-like folders")
    for p in inbox_paths[:35]:
        log("  Inbox candidate: " + p)
    if len(inbox_paths) > 35:
        log(f"  ... plus {len(inbox_paths) - 35} more Inbox-like folders")
    return folder_rows


def read_attachment(mail, session_excel, tmpdir):
    expected_date = CHECK_REPORT_DATE.strftime("%Y%m%d")
    try:
        attachments = list(mail.Attachments)
    except Exception as exc:
        err("Cannot list matched message attachments", exc)
        return False
    names = [safe(a, "FileName") for a in attachments]
    log(f"  [ATTACHMENTS] {names if names else '(none)'}")
    named = []
    for a, filename in zip(attachments, names):
        m = file_regex.fullmatch(filename.strip())
        if m:
            named.append((a, filename, m.group(1)))
    chosen = [(a, fn) for a, fn, d in named if d == expected_date]
    if not chosen:
        log(f"  [FAIL: ATTACHMENT] Expected Nomura_Summary_Report_{expected_date}.xlsx (same date as subject).")
        if named:
            log("  [FAIL: DATE] Nomura files found with DIFFERENT dates: " + ", ".join(f"{fn} ({d})" for _, fn, d in named))
        else:
            log("  [FAIL: NAME] None of the filenames matches Nomura_Summary_Report_YYYYMMDD.xlsx")
        return False

    a, filename = chosen[0]
    path = Path(tmpdir) / filename
    try:
        a.SaveAsFile(str(path))
        log(f"  [SAVE OK] Attachment saved temporarily: {filename} ({path.stat().st_size:,} bytes)")
    except Exception as exc:
        err(f"Cannot save attachment {filename}", exc)
        return False

    wb = None
    try:
        wb = session_excel.Workbooks.Open(str(path.resolve()), UpdateLinks=0, ReadOnly=True)
        log(f"  [EXCEL OPEN OK] Worksheets: {', '.join(str(ws.Name) for ws in wb.Worksheets)}")
        for ws in wb.Worksheets:
            try:
                last_row = int(ws.Cells(ws.Rows.Count, 1).End(-4162).Row)  # xlUp
                values = ws.Range(f"A1:A{last_row}").Value2
                if last_row == 1:
                    first_col = [values[0][0] if isinstance(values, tuple) and isinstance(values[0], tuple) else values]
                else:
                    first_col = [r[0] if isinstance(r, (list, tuple)) else r for r in values]
                equity_rows = [i for i, v in enumerate(first_col, 1) if label(v) == "equity"]
                log(f"  [SHEET] {ws.Name}: A has {last_row} used rows; Equity matches at rows {equity_rows[:12]}")
                if equity_rows:
                    row = equity_rows[0]
                    nums = [ws.Cells(row, c).Value2 for c in (8, 10, 12)]
                    log(f"  [SUCCESS] Nomura date {CHECK_REPORT_DATE}; sheet={ws.Name}; row={row}; H={nums[0]!r}; J={nums[1]!r}; L={nums[2]!r}")
                    return True
            except Exception as exc:
                err(f"Reading worksheet {safe(ws, 'Name')}", exc)
        log("  [FAIL: ROW] No exact 'Equity' label was found in column A of any readable worksheet")
        return False
    except Exception as exc:
        err(f"Opening Excel attachment {filename}", exc)
        return False
    finally:
        if wb is not None:
            try:
                wb.Close(SaveChanges=False)
            except Exception as exc:
                err("Closing temporary Excel workbook", exc)


stats = {"folders": 0, "window_items": 0, "nomura_subjects": 0, "target_subjects": 0,
         "attachments_ok": 0, "filter_errors": 0, "fallback_folders": 0, "message_errors": 0}
near_misses = []
found_keys = set()
folders_with_mail = []
excel = None
outlook = None

try:
    log(f"NOMURA OUTLOOK DEBUG — known report date {CHECK_REPORT_DATE}")
    log(f"[WINDOW] Searching by email ReceivedTime: {start_day} to {end_day} (end exclusive)")
    log("[SUBJECT] Accepts Yuanta Futures ... Summary Report YYYY-MM-DD plus any trailing KYC code")
    outlook = win32.Dispatch("Outlook.Application").GetNamespace("MAPI")
    folders = get_folders(outlook)
    if not folders:
        log("[STOP] No readable Outlook mail folders. Check classic Outlook profile / permission.")

    def examine(msg, folder_path, source, tmpdir):
        try:
            if int(msg.Class) != 43:  # 43=MailItem
                return False
            subject = safe(msg, "Subject", "")
            m = subject_regex.search(subject)
            if not m:
                if len(near_misses) < 25 and ("yuanta" in subject.casefold() or "nomura international" in subject.casefold()):
                    near_misses.append((folder_path, subject[:220]))
                return False
            stats["nomura_subjects"] += 1
            subject_date = date.fromisoformat(m.group(1))
            log(f"  [SUBJECT MATCH] {subject[:220]} | parsed={subject_date} | source={source} | folder={folder_path}")
            if subject_date != CHECK_REPORT_DATE:
                return False
            stats["target_subjects"] += 1
            entry_id = safe(msg, "EntryID", "")
            duplicate_key = (entry_id, safe(msg, "ReceivedTime"))
            if entry_id and duplicate_key in found_keys:
                return True
            found_keys.add(duplicate_key)
            if excel is None:
                # Created by outer scope before scanning.
                log("  [ERROR] Excel object was not initialized")
                return True
            if read_attachment(msg, excel, tmpdir):
                stats["attachments_ok"] += 1
            return True
        except Exception as exc:
            stats["message_errors"] += 1
            if stats["message_errors"] <= 20:
                err(f"Reading message in {folder_path}", exc)
            return False

    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        try:
            excel.AutomationSecurity = 3
        except Exception:
            pass
        log("[EXCEL] Desktop Excel automation available")
    except Exception as exc:
        err("Cannot start Excel desktop automation", exc)
        log("[EXCEL] Mail search will proceed, but extracting H/J/L is unavailable")

    with TemporaryDirectory(prefix="nomura_debug_") as tmpdir:
        # Scan only the relevant received-date range. Do not rely on an unreliable subject LIKE filter.
        for f, folder_path in folders:
            stats["folders"] += 1
            try:
                items = f.Items
                total = int(items.Count)
            except Exception as exc:
                err(f"Cannot read mail items in {folder_path}", exc)
                continue
            if total == 0:
                continue

            restriction = (f"[ReceivedTime] >= '{start_day:%m/%d/%Y} 12:00 AM' "
                           f"AND [ReceivedTime] < '{end_day:%m/%d/%Y} 12:00 AM'")
            subset = None
            count = None
            try:
                subset = items.Restrict(restriction)
                count = int(subset.Count)
            except Exception as exc:
                stats["filter_errors"] += 1
                err(f"Outlook ReceivedTime restriction failed: {folder_path} | {restriction}", exc)

            if count is not None and count > 0:
                folders_with_mail.append((folder_path, count, total))
                stats["window_items"] += count
                log(f"[SCAN] {folder_path} | all={total:,}; date-window={count:,}")
                try:
                    for msg in subset:
                        examine(msg, folder_path, "date-filter", tmpdir)
                except Exception as exc:
                    err(f"Iteration of filtered messages stopped in {folder_path}", exc)
            elif count == 0 and any(x in folder_path.casefold() for x in ("big inbox", "inbox", "收件箱")):
                log(f"[FILTER ZERO] {folder_path} | all={total:,}, but date-filter returned 0")

        # If no target subject, independently test Inbox-like folders without Restrict.
        # This helps catch silent false-zero Outlook restrictions.
        if stats["target_subjects"] == 0:
            log("[FALLBACK] No target subject in date-filter results. Scanning recent messages in Inbox-like folders without Restrict...")
            inbox_folders = [(f, p) for f, p in folders if any(x in p.casefold() for x in ("big inbox", "inbox", "收件箱"))]
            for f, folder_path in inbox_folders[:MAX_INBOX_FOLDERS_TO_FALLBACK]:
                stats["fallback_folders"] += 1
                try:
                    items = f.Items
                    items.Sort("[ReceivedTime]", True)
                    msg = items.GetFirst()
                    scanned = 0
                    while msg is not None and scanned < MAX_FALLBACK_MESSAGES_PER_INBOX:
                        scanned += 1
                        recv = mail_date(msg)
                        if recv is not None and recv < start_day:
                            break
                        if recv is None or recv < end_day:
                            examine(msg, folder_path, "fallback-no-filter", tmpdir)
                        if stats["attachments_ok"] > 0:
                            break
                        msg = items.GetNext()
                    log(f"[FALLBACK SCAN] {folder_path}: examined {scanned:,} newest messages")
                    if scanned >= MAX_FALLBACK_MESSAGES_PER_INBOX:
                        log("  [LIMIT] Fallback reached its safety limit; increase MAX_FALLBACK_MESSAGES_PER_INBOX if needed")
                    if stats["attachments_ok"] > 0:
                        break
                except Exception as exc:
                    err(f"Fallback scan failed: {folder_path}", exc)

    log("\n========== DIAGNOSTIC RESULT ==========")
    for key, value in stats.items():
        log(f"{key}: {value}")
    if near_misses:
        log("[NEAR-MISS SUBJECTS] These were visible but did not match the expected subject pattern:")
        for folder_path, subject in near_misses[:15]:
            log(f"  {folder_path} | {subject}")
    if stats["attachments_ok"]:
        log("[CONCLUSION] Outlook search, attachment access, and Equity extraction WORK for this example.")
        log("If your main April-now code still says 0, the error is in its search/filter logic.")
    elif stats["target_subjects"]:
        log("[CONCLUSION] Outlook CAN FIND the Yuanta mail. See the attachment / Excel errors above.")
    elif stats["window_items"]:
        log("[CONCLUSION] Outlook search CAN READ email, but this particular subject was NOT found in the visible folders/time window.")
        log("Check that your Big Inbox mailbox is listed and that the report email's ReceivedTime falls in this window.")
    else:
        log("[CONCLUSION] The date-filter returned no readable messages. Check mailbox roots, folder access and FILTER ZERO / ERROR messages.")
    log("=======================================")
except Exception as exc:
    err("FATAL: cannot complete Outlook diagnostic", exc)
finally:
    if excel is not None:
        try:
            excel.Quit()
        except Exception as exc:
            err("Closing Excel", exc)
    try:
        log_file.write_text("\n".join(log_lines) + "\n", encoding="utf-8-sig")
        print(f"\nFull diagnostic saved to: {log_file}", flush=True)
    except Exception as exc:
        print(f"Could not write diagnostic file: {exc}", flush=True)

# Security: the .txt log contains mailbox paths, message subjects, and possibly identifiers.
# Remove confidential details before sharing it outside your organization.
