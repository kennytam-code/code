"""Read daily Trapped Cash HTML tables from classic Outlook on Windows.

Jupyter: install pandas lxml openpyxl pywin32, then run this file or its notebook.
Mail is read only. Re-running creates a fresh Excel export, not an append.
Supports direct emails and emails forwarded as attachments (.msg, .eml, embedded items).
"""

# %% Settings
from datetime import date, datetime, timedelta
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
import re
import shutil
import sys
import tempfile

import pandas as pd
from lxml import html
from openpyxl.styles import Font, PatternFill

START_DATE = date(2026, 4, 1)
END_DATE = date.today()  # Inclusive; uses the Jupyter computer's local date.
MAILBOX_NAME = None  # None = default mailbox; otherwise its Outlook display name.
FOLDER_PATH = []  # Relative to Inbox, e.g. ["Reports", "Trapped Cash"].
INCLUDE_SUBFOLDERS = True
INCLUDE_REPORT_DATE = False  # True adds ReportDate before the four requested columns.
READ_EMAIL_ATTACHMENTS = True  # Also read forwarded-as-attachment emails (.msg/.eml).
ATTACHMENT_LOOKBACK_DAYS = 7  # Scan outer emails received since START_DATE - N days (None = all).
MAX_ATTACHMENT_DEPTH = 3  # Maximum nesting depth for attached emails.
OUTPUT_DIR = Path.cwd()

# Keep source values as text by default, including leading zeros and date formats.
# Optional: set the exact source format, e.g. "%d/%m/%Y", to create Excel dates.
SOURCE_DATE_FORMAT = None

COLUMNS = ["Trading Book", "Notional", "EffectiveDate", "MaturityDate"]
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

OL_MAIL_CLASS = 43
OL_BY_VALUE = 1
OL_EMBEDDED_ITEM = 5
OL_DISCARD = 1


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
                         "Image tables and non-email file attachments are not supported.")
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


# %% Outlook and attachment helpers (Windows with classic Outlook only)
def valid_mail_datetime(dt):
    """Filter out Outlook's 4501-01-01 sentinel value for unset dates."""
    if dt is None or getattr(dt, "year", 4501) >= 4500:
        return None
    return dt


def parse_eml_datetime(eml_msg, fallback_dt):
    raw_date = eml_msg.get("Date")
    if raw_date:
        try:
            dt = parsedate_to_datetime(raw_date)
            if valid_mail_datetime(dt) is not None:
                return dt
        except Exception:
            pass
    return fallback_dt


def record_candidate(day, html_body, received_dt, folder_path, dedup_key,
                     latest, counts, seen, source_note=""):
    if dedup_key in seen:
        return
    seen.add(dedup_key)
    try:
        frame, table_count = extract_tables(html_body)
        error = None
        has_table = True
    except Exception as exc:
        frame, table_count = None, 0
        error = exc
        has_table = False

    rank = (has_table, received_dt.timestamp())
    counts[day] = counts.get(day, 0) + 1
    if day not in latest or rank > latest[day]["rank"]:
        latest[day] = {
            "frame": frame,
            "table_count": table_count,
            "error": error,
            "rank": rank,
            "received": received_dt.isoformat(),
            "folder": folder_path,
            "source_note": source_note,
        }


def inspect_eml_message(eml_msg, outer_received, folder_path, base_key,
                        outer_subject, expected, latest, counts, seen, depth):
    if depth > MAX_ATTACHMENT_DEPTH:
        return
    eml_dt = parse_eml_datetime(eml_msg, outer_received)
    subject = str(eml_msg.get("Subject", "") or "").strip()
    day = expected.get(subject.casefold())
    if day is not None and base_key not in seen:
        part = eml_msg.get_body(preferencelist=("html",))
        html_body = part.get_content() if part is not None else ""
        record_candidate(
            day=day,
            html_body=str(html_body or ""),
            received_dt=eml_dt,
            folder_path=folder_path,
            dedup_key=base_key,
            latest=latest,
            counts=counts,
            seen=seen,
            source_note=f"Attached in '{outer_subject}'",
        )

    if depth >= MAX_ATTACHMENT_DEPTH:
        return

    for idx, part in enumerate(eml_msg.iter_attachments(), start=1):
        ctype = part.get_content_type()
        fname = str(part.get_filename() or "").lower()
        child_key = base_key + (f"eml:{idx}",)
        try:
            if ctype == "message/rfc822":
                nested = part.get_content()
                if isinstance(nested, list) and nested:
                    nested = nested[0]
                if nested is not None:
                    inspect_eml_message(
                        nested, eml_dt, folder_path, child_key,
                        outer_subject, expected, latest, counts, seen, depth + 1
                    )
            elif fname.endswith(".eml"):
                raw = part.get_payload(decode=True)
                if raw:
                    nested = BytesParser(policy=policy.default).parsebytes(raw)
                    inspect_eml_message(
                        nested, eml_dt, folder_path, child_key,
                        outer_subject, expected, latest, counts, seen, depth + 1
                    )
        except Exception as exc:
            print(f"Warning: skipped nested .eml attachment in {folder_path}: {exc}",
                  flush=True)


def inspect_outlook_attachments(namespace, mail_item, outer_received, folder_path,
                                base_key, outer_subject, expected, latest, counts,
                                seen, temp_dir, file_counter, depth=1):
    if depth > MAX_ATTACHMENT_DEPTH:
        return
    try:
        attachments = mail_item.Attachments
        att_count = attachments.Count
    except Exception:
        return

    for idx in range(1, att_count + 1):
        embedded = None
        temp_path = None
        try:
            att = attachments.Item(idx)
            att_type = getattr(att, "Type", None)
            filename = str(getattr(att, "FileName", "") or "").lower()
            if att_type == OL_BY_VALUE:
                if not (filename.endswith(".msg") or filename.endswith(".eml")):
                    continue
            elif att_type != OL_EMBEDDED_ITEM:
                continue

            file_counter[0] += 1
            ext = ".eml" if (att_type == OL_BY_VALUE and filename.endswith(".eml")) else ".msg"
            temp_path = Path(temp_dir) / f"att_{file_counter[0]}{ext}"
            att.SaveAsFile(str(temp_path))
            child_key = base_key + (idx,)

            if ext == ".eml":
                raw = temp_path.read_bytes()
                eml_msg = BytesParser(policy=policy.default).parsebytes(raw)
                inspect_eml_message(
                    eml_msg, outer_received, folder_path, child_key,
                    outer_subject, expected, latest, counts, seen, depth
                )
            else:
                embedded = namespace.OpenSharedItem(str(temp_path))
                if getattr(embedded, "Class", None) == OL_MAIL_CLASS:
                    emb_dt = (
                        valid_mail_datetime(getattr(embedded, "ReceivedTime", None))
                        or valid_mail_datetime(getattr(embedded, "SentOn", None))
                        or outer_received
                    )
                    emb_subject = str(getattr(embedded, "Subject", "") or "").strip()
                    day = expected.get(emb_subject.casefold())
                    if day is not None and child_key not in seen:
                        html_body = str(getattr(embedded, "HTMLBody", "") or "")
                        record_candidate(
                            day=day,
                            html_body=html_body,
                            received_dt=emb_dt,
                            folder_path=folder_path,
                            dedup_key=child_key,
                            latest=latest,
                            counts=counts,
                            seen=seen,
                            source_note=f"Attached in '{outer_subject}'",
                        )
                    if depth < MAX_ATTACHMENT_DEPTH:
                        inspect_outlook_attachments(
                            namespace, embedded, emb_dt, folder_path, child_key,
                            outer_subject, expected, latest, counts, seen,
                            temp_dir, file_counter, depth + 1
                        )
        except Exception as exc:
            print(f"Warning: skipped attachment #{idx} in '{outer_subject}' "
                  f"({folder_path}): {exc}", flush=True)
        finally:
            if embedded is not None:
                try:
                    embedded.Close(OL_DISCARD)
                except Exception:
                    pass
                embedded = None
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except OSError:
                    pass


def walk_folders(folder):
    yield folder
    if INCLUDE_SUBFOLDERS:
        for i in range(1, folder.Folders.Count + 1):
            yield from walk_folders(folder.Folders.Item(i))


def collect_messages(namespace, days, temp_dir):
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
    scanned_containers = set()
    file_counter = [0]
    cutoff = (START_DATE - timedelta(days=ATTACHMENT_LOOKBACK_DAYS)
              if ATTACHMENT_LOOKBACK_DAYS is not None else None)

    for folder in walk_folders(inbox):
        folder_path = str(folder.FolderPath)
        store_id = str(folder.StoreID)
        print(f"Searching {folder_path}", flush=True)

        # Pass 1: Fast exact subject queries for direct emails.
        for offset in range(0, len(subjects), 25):
            batch = subjects[offset:offset + 25]
            query = " OR ".join("[Subject] = '" + s.replace("'", "''") + "'"
                                for s in batch)
            items = folder.Items.Restrict(query)
            for i in range(1, items.Count + 1):
                message = items.Item(i)
                if getattr(message, "Class", None) != OL_MAIL_CLASS:
                    continue
                subject = str(message.Subject or "").strip()
                day = expected.get(subject.casefold())
                if day is None:
                    continue  # Excludes RE:/FW: subjects and unrelated mail.
                key = (store_id, str(message.EntryID), ())
                if key in seen:
                    continue
                received = (valid_mail_datetime(getattr(message, "ReceivedTime", None))
                            or valid_mail_datetime(getattr(message, "SentOn", None))
                            or datetime.now())
                record_candidate(
                    day=day,
                    html_body=str(message.HTMLBody or ""),
                    received_dt=received,
                    folder_path=folder_path,
                    dedup_key=key,
                    latest=latest,
                    counts=counts,
                    seen=seen,
                )

        # Pass 2: Inspect attached emails (.msg, .eml, Outlook embedded items).
        if not READ_EMAIL_ATTACHMENTS:
            continue
        try:
            att_items = folder.Items.Restrict(
                '@SQL="urn:schemas:httpmail:hasattachment" = 1'
            )
        except Exception:
            att_items = folder.Items

        sorted_desc = False
        try:
            att_items.Sort("[ReceivedTime]", True)
            sorted_desc = True
        except Exception:
            pass

        for i in range(1, att_items.Count + 1):
            message = att_items.Item(i)
            if getattr(message, "Class", None) != OL_MAIL_CLASS:
                continue
            raw_received = valid_mail_datetime(getattr(message, "ReceivedTime", None))
            if cutoff is not None and raw_received is not None:
                if raw_received.date() < cutoff:
                    if sorted_desc:
                        break
                    continue
            container_key = (store_id, str(message.EntryID))
            if container_key in scanned_containers:
                continue
            scanned_containers.add(container_key)
            outer_received = (
                raw_received
                or valid_mail_datetime(getattr(message, "SentOn", None))
                or datetime.now()
            )
            outer_subject = str(getattr(message, "Subject", "") or "").strip()
            inspect_outlook_attachments(
                namespace=namespace,
                mail_item=message,
                outer_received=outer_received,
                folder_path=folder_path,
                base_key=container_key,
                outer_subject=outer_subject,
                expected=expected,
                latest=latest,
                counts=counts,
                seen=seen,
                temp_dir=temp_dir,
                file_counter=file_counter,
            )

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
            if source["error"] is None:
                frame = source["frame"].copy()
                table_count = source["table_count"]
                details = []
                if source["source_note"]:
                    details.append(source["source_note"] + ".")
                if counts[day] > 1:
                    details.append("Latest received matching email selected.")
                record.update(Rows=len(frame), Tables=table_count,
                              Status="Extracted" if len(frame) else "Empty table",
                              Details=" ".join(details))
                if len(frame):
                    record.update(ExcelFirstRow=next_excel_row,
                                  ExcelLastRow=next_excel_row + len(frame) - 1)
                    next_excel_row += len(frame)
                if INCLUDE_REPORT_DATE:
                    frame.insert(0, "ReportDate", day)
                frames.append(frame)
            else:
                prefix = f"{source['source_note']}; " if source["source_note"] else ""
                record.update(Status="Extraction error",
                              Details=f"{prefix}{source['error']}")
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
    temp_dir = tempfile.mkdtemp(prefix="trapped_cash_")
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        latest, counts = collect_messages(namespace, days, temp_dir)
        data, log = assemble_report(days, latest, counts)
        latest.clear()
        namespace = outlook = None
    finally:
        pythoncom.CoUninitialize()
        shutil.rmtree(temp_dir, ignore_errors=True)

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
