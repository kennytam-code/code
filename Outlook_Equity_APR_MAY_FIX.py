# Outlook equity extractor — SAFE indexed-search edition.
# Paste this whole script into ONE Jupyter cell on Windows with classic Outlook.
# Install once if needed: %pip install pywin32 openpyxl
# READ ONLY in Outlook: never sends, moves, or deletes mail.

from __future__ import annotations

import csv
import io
import re
import sys
import traceback
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import mkdtemp
import gc
import shutil
import time
from uuid import uuid4

# -------------- CONFIG --------------
START_DATE = date(2026, 4, 1)
END_DATE = date.today()
# Switch to date(2026, 11, 16) to prove one known report before checking April-now.
TEST_ONLY_DATE = None  # IMPORTANT: must stay None to include April and May
# Check archive / historical mail folders ONLY if Apr-May results are incomplete.
# Folder names are enumerated, NOT email messages; mailbox-wide message scans remain disabled.
SEARCH_ARCHIVES_IF_APR_MAY_MISSING = True
MAX_ADDITIONAL_FOLDERS = 24  # caps extra indexed folder searches for Outlook responsiveness
# If Outlook Instant Search is unavailable, STOP rather than scan thousands of emails.
NEVER_SCAN_ENTIRE_INBOX = True
# Search default Inbox + each visible store's Inbox + currently selected Inbox.
# Does NOT recursively scan folders or count every email.
OUTPUT_DIR = Path.cwd()
# ------------------------------------

if sys.platform != 'win32':
    raise RuntimeError('Run on Windows with classic Outlook (not New Outlook).')
try:
    import win32com.client as win32
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError as exc:
    raise RuntimeError('Install packages in Jupyter: %pip install pywin32 openpyxl') from exc

NOMURA_RE = re.compile(r'\bNomura\s+International\s+Plc\s+Summary\s+Report\s*[:\-–]?\s*(\d{4}-\d{2}-\d{2})(?=\s|$)', re.I)
SINOPAC_RE = re.compile(r'\b(\d{1,2})/(\d{1,2})\s+Nomura\s+Daily\s+Statement\s*\(From\s+SinoPac\s+Futures\)', re.I)
NOMURA_ATTACHMENT_RE = re.compile(r'^Nomura_Summary_Report_(\d{8})\.(xlsx|xlsm)$', re.I)
SINOPAC_ATTACHMENT_RE = re.compile(r'^1263583_(\d{8})\.csv$', re.I)
SEARCHES = {
    'Nomura': 'Nomura International Plc Summary Report',
    'SinoPac': 'Nomura Daily Statement',
}

logs = []
def log(line):
    line = str(line)
    logs.append(line)
    print(line, flush=True)


def norm(v):
    return re.sub(r'\s+', ' ', str(v or '').replace('\xa0', ' ')).strip().casefold()


def number(v):
    if v is None or isinstance(v, (float, int)):
        return v
    raw = str(v).strip()
    if raw in ('', '-', '--'):
        return None
    s = raw.replace(',', '').replace('$', '').replace(' ', '')
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return raw


def date_from_subject(kind, subject, received_date):
    if kind == 'Nomura':
        m = NOMURA_RE.search(subject)
        return date.fromisoformat(m.group(1)) if m else None
    m = SINOPAC_RE.search(subject)
    if not m:
        return None
    mm, dd = int(m.group(1)), int(m.group(2))
    candidates = []
    for yy in (received_date.year - 1, received_date.year, received_date.year + 1):
        try:
            candidates.append(date(yy, mm, dd))
        except ValueError:
            pass
    return min(candidates, key=lambda d: abs((d-received_date).days)) if candidates else None


def get_inboxes(session):
    found, seen = [], set()
    def add(folder, why):
        if folder is None:
            return
        try:
            key = (str(folder.StoreID), str(folder.EntryID))
            if key in seen:
                return
            seen.add(key)
            found.append(folder)
            log(f'[FOLDER] {folder.FolderPath}  ({why})')
        except Exception as exc:
            log(f'[FOLDER ERROR] {why}: {type(exc).__name__}: {exc}')

    try:
        explorer = session.Application.ActiveExplorer()
        if explorer:
            current = explorer.CurrentFolder
            if 'inbox' in norm(current.Name) or norm(current.Name) == '收件箱':
                add(current, 'Outlook selected Inbox')
    except Exception as exc:
        log(f'[INFO] Cannot read selected Outlook folder: {exc}')
    try:
        add(session.GetDefaultFolder(6), 'default Inbox')
    except Exception as exc:
        log(f'[FOLDER ERROR] Default Inbox: {exc}')

    for store in session.Stores:
        try:
            inbox = store.GetDefaultFolder(6)   # olFolderInbox
            add(inbox, f'store {store.DisplayName}')
            # Optional explicit 'Big Inbox' directly under the Inbox.
            for child in inbox.Folders:
                if norm(child.Name) == 'big inbox':
                    add(child, 'Big Inbox under Inbox')
        except Exception as exc:
            log(f'[FOLDER SKIP] {store.DisplayName}: {type(exc).__name__}: {exc}')
    return found



def get_historical_folders(session, current_folders):
    """Find likely archive folders by FOLDER NAMES only, never by enumerating messages.

    Restrict to explicit archive/2026 folders. Do not recurse through the 90k Inbox.
    A small cap prevents unexpected shared mailboxes from causing runaway searches.
    """
    result = []
    seen = set()
    for f in current_folders:
        try:
            seen.add((str(f.StoreID), str(f.EntryID)))
        except Exception:
            pass

    def add(folder, why):
        if len(result) >= MAX_ADDITIONAL_FOLDERS:
            return
        try:
            key = (str(folder.StoreID), str(folder.EntryID))
            if key not in seen:
                seen.add(key)
                result.append(folder)
                log(f'[HISTORY FOLDER] {folder.FolderPath} ({why})')
        except Exception as exc:
            log(f'[HISTORY FOLDER ERROR] {why}: {exc}')

    def is_history_name(name):
        s = norm(name)
        return any(t in s for t in ('archive', 'archived', 'big inbox', '2026', 'futures',
                                    'nomura', 'reports', '封存', '封存郵件', '歷史', '归档', '存檔'))

    def visit(folder, depth, why):
        if len(result) >= MAX_ADDITIONAL_FOLDERS:
            return
        add(folder, why)
        if depth <= 0:
            return
        try:
            children = folder.Folders  # ONLY folder metadata; never folder.Items
            for child in children:
                if len(result) >= MAX_ADDITIONAL_FOLDERS:
                    break
                visit(child, depth - 1, why)
        except Exception as exc:
            log(f'[HISTORY FOLDER WARNING] {folder.FolderPath}: {exc}')

    for store in session.Stores:
        if len(result) >= MAX_ADDITIONAL_FOLDERS:
            break
        try:
            is_archive_store = any(t in norm(store.DisplayName)
                                   for t in ('archive', '封存', '歷史', '归档'))
            root = store.GetRootFolder()
            # Only root folder metadata and a few selected subfolder branches.
            for top in root.Folders:
                if len(result) >= MAX_ADDITIONAL_FOLDERS:
                    break
                top_name = norm(top.Name)
                if is_archive_store or is_history_name(top_name):
                    visit(top, 2, 'archive or historic folder')
                elif top_name in ('inbox', '收件箱'):
                    for child in top.Folders:
                        if is_history_name(child.Name):
                            visit(child, 2, 'historic folder under Inbox')
        except Exception as exc:
            log(f'[HISTORY SCAN WARNING] {getattr(store, "DisplayName", "store")}: {exc}')

    if len(result) >= MAX_ADDITIONAL_FOLDERS:
        log(f'[HISTORY LIMIT] At most {MAX_ADDITIONAL_FOLDERS} additional folders will be searched.')
    log(f'[HISTORY FOLDER COUNT] {len(result)} (no email enumeration)')
    return result


def get_matches(folder, kind):
    '''Indexed subject search. No unrestricted Items or recursive mailbox scans.'''
    phrase = SEARCHES[kind]
    try:
        indexed = bool(folder.Store.IsInstantSearchEnabled)
    except Exception:
        indexed = False
    log(f'[SEARCH] {kind} | {folder.FolderPath} | InstantSearch={indexed}')
    if not indexed and NEVER_SCAN_ENTIRE_INBOX:
        log(f'[SEARCH BLOCKED] No Instant Search indexing in this store; not scanning the full Inbox.')
        return [], 'SEARCH BLOCKED: Outlook Instant Search disabled'
    prop = '"urn:schemas:httpmail:subject"'
    safe_phrase = phrase.replace("'", "''")
    if indexed:
        dasl = f"@SQL={prop} ci_phrasematch '{safe_phrase}'"
    else:
        dasl = f"@SQL={prop} LIKE '%{safe_phrase}%'"
    try:
        table = folder.GetTable(dasl)
    except Exception as exc:
        log(f'[SEARCH ERROR] {kind} | {folder.FolderPath} | {type(exc).__name__}: {exc}')
        return [], f'SEARCH ERROR: {exc}'

    found = []
    MAX_MATCH_ROWS = 1500  # safety valve if filter is ignored by the mail store
    try:
        while not table.EndOfTable:
            if len(found) >= MAX_MATCH_ROWS:
                log(f'[SEARCH STOPPED] >={MAX_MATCH_ROWS} matches; filter may not be selective')
                return found, 'TOO MANY MATCHES (safety stop)'
            row = table.GetNextRow()
            subject = str(row.Item('Subject') or '')
            if (NOMURA_RE if kind == 'Nomura' else SINOPAC_RE).search(subject) is None:
                continue
            entry_id = str(row.Item('EntryID'))
            found.append((entry_id, str(folder.StoreID), subject, str(folder.FolderPath)))
    except Exception as exc:
        log(f'[TABLE ERROR] {kind} | {folder.FolderPath} | {type(exc).__name__}: {exc}')
        return found, f'TABLE ERROR: {exc}'
    log(f'[SEARCH RESULT] {kind} | {folder.FolderPath} | subject-matches={len(found)}')
    return found, None


def nomura_values(message, day, tmpdir):
    # Read XLSX into BytesIO, not directly from a temporary disk file.
    # In read_only mode a suspended row iterator can otherwise retain a ZIP
    # stream and lock the .xlsx on Windows even when wb.close() is called.
    attachments = list(message.Attachments)
    names = [str(a.FileName) for a in attachments]
    expected = day.strftime('%Y%m%d')
    matches = [(a, str(a.FileName)) for a in attachments
               if (m := NOMURA_ATTACHMENT_RE.fullmatch(str(a.FileName).strip())) and m.group(1) == expected]
    if not matches:
        raise ValueError(f'ATTACHMENT NOT FOUND: expected Nomura_Summary_Report_{expected}.xlsx; actual={names}')
    errors = []
    for idx, (a, filename) in enumerate(matches):
        # Unique name prevents collisions across multiple emails from same day.
        target = Path(tmpdir) / f'nomura_{expected}_{idx}_{uuid4().hex[:8]}{Path(filename).suffix.lower()}'
        try:
            a.SaveAsFile(str(target))
            with io.BytesIO(target.read_bytes()) as memory_file:
                wb = load_workbook(memory_file, data_only=True, read_only=True)
                try:
                    for ws in wb.worksheets:
                        for row_idx, values in enumerate(ws.iter_rows(min_col=1, max_col=12, values_only=True), 1):
                            if norm(values[0]) == 'equity':
                                nums = [number(values[j]) for j in (7, 9, 11)]
                                if nums == [None, None, None]:
                                    raise ValueError(f'EXCEL VALUES EMPTY: {ws.title} row {row_idx}, columns H/J/L. Values may be uncalculated formulas.')
                                return nums, filename, f'{ws.title} row {row_idx}'
                finally:
                    wb.close()
            errors.append(f'EXCEL ROW NOT FOUND: Equity not in column A of {filename}')
        except Exception as exc:
            errors.append(f'{type(exc).__name__}: {exc}')
    raise ValueError(' | '.join(errors))

def decode_csv(content):
    if content.startswith((b'\xff\xfe', b'\xfe\xff')):
        return content.decode('utf-16')
    for enc in ('utf-8-sig', 'cp950', 'big5', 'cp1252'):
        try:
            return content.decode(enc)
        except UnicodeError:
            continue
    return content.decode('utf-8', 'replace')


def sinopac_values(message, day, tmpdir):
    candidates = []
    attachment_names = []
    for a in message.Attachments:
        fn = str(a.FileName)
        attachment_names.append(fn)
        match = SINOPAC_ATTACHMENT_RE.fullmatch(fn.strip())
        if match:
            candidates.append((match.group(1), a, fn))
    if not candidates:
        raise ValueError(f'ATTACHMENT NOT FOUND: 1263583_MMDDYYYY.csv; actual={attachment_names}')
    next_day = (day + timedelta(days=1)).strftime('%m%d%Y')
    priority = [x for x in candidates if x[0] == next_day]
    if not priority and len(candidates) == 1:
        priority = candidates
    if not priority:
        raise ValueError(f'ATTACHMENT DATE MISMATCH: subject={day}, CSV files={[x[2] for x in candidates]}')
    _, attachment, filename = priority[0]
    csvpath = Path(tmpdir) / f'sinopac_{day:%Y%m%d}_{uuid4().hex[:8]}.csv'
    attachment.SaveAsFile(str(csvpath))
    content = decode_csv(csvpath.read_bytes())
    try:
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=',;\t|')
    except csv.Error:
        dialect = csv.excel
    for line, values in enumerate(csv.reader(io.StringIO(content, newline=''), dialect), 1):
        if len(values) >= 8 and norm(values[1]) == 'account equity':
            return [number(values[i]) for i in (3,5,7)], filename, f'CSV row {line}'
    raise ValueError(f'CSV ROW NOT FOUND: Account Equity not in column B of {filename}')


def save_output(records, audits, monthly_stats):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Daily Summary'
    headers = ['Report Date', 'Nomura H', 'Nomura J', 'Nomura L',
               'SinoPac D', 'SinoPac F', 'SinoPac H', 'Nomura Status', 'SinoPac Status']
    ws.append(headers)
    if TEST_ONLY_DATE:
        days = [TEST_ONLY_DATE]
    else:
        days = []
        cursor = START_DATE
        while cursor <= END_DATE:
            if cursor.weekday() < 5 or cursor in records['Nomura'] or cursor in records['SinoPac']:
                days.append(cursor)
            cursor += timedelta(days=1)
    for day in days:
        n = records['Nomura'].get(day)
        s = records['SinoPac'].get(day)
        ws.append([day, *((n['nums'] if n else [None]*3)), *((s['nums'] if s else [None]*3)),
                   n['status'] if n else 'NOT FOUND', s['status'] if s else 'NOT FOUND'])
        ws.cell(ws.max_row, 1).number_format = 'yyyy-mm-dd'
    audit_sheet = wb.create_sheet('Audit')
    audit_sheet.append(['Source', 'Report Date', 'Status', 'Subject', 'Attachment', 'Folder', 'Info'])
    for item in sorted(audits, key=lambda i: (str(i[1]), i[0])):
        audit_sheet.append(item)
    monthly_sheet = wb.create_sheet('Monthly Coverage')
    monthly_sheet.append(['Month', 'Nomura Emails Found', 'Nomura Extracted',
                          'SinoPac Emails Found', 'SinoPac Extracted'])
    for month_row in monthly_stats:
        monthly_sheet.append(month_row)

    for sheet in wb.worksheets:
        sheet.freeze_panes = 'B2'
        sheet.auto_filter.ref = sheet.dimensions
        sheet.row_dimensions[1].height = 26
        for cell in sheet[1]:
            cell.fill = PatternFill('solid', fgColor='1F3555')
            cell.font = Font(name='Times New Roman', size=11, bold=True, color='FFFFFF')
            cell.alignment = Alignment(horizontal='center', vertical='center')
        width = ([17, 18, 18, 18, 18, 18, 18, 18, 18] if sheet == ws else
                 [15, 23, 20, 24, 20] if sheet == monthly_sheet else
                 [14, 17, 24, 70, 42, 38, 70])
        for idx, col_width in enumerate(width, 1):
            sheet.column_dimensions[get_column_letter(idx)].width = col_width
        for cells in sheet.iter_rows(min_row=2):
            for cell in cells:
                cell.font = Font(name='Times New Roman', size=11)
                if sheet == ws and cell.column in range(2,8):
                    cell.number_format = '#,##0.########;[Red](#,##0.########)'
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / f'Outlook_Equity_APR_MAY_FIX_{datetime.now():%Y%m%d_%H%M%S}.xlsx'
    wb.save(filepath)
    return filepath


def main():
    if TEST_ONLY_DATE and not (START_DATE <= TEST_ONLY_DATE <= END_DATE):
        raise ValueError(f'TEST_ONLY_DATE {TEST_ONLY_DATE} is outside {START_DATE}..{END_DATE}')
    if TEST_ONLY_DATE:
        log(f'FAST TEST: one report date {TEST_ONLY_DATE}')
    else:
        log(f'FAST SEARCH: report subjects dated {START_DATE} to {END_DATE}')
    log('Indexed email queries only. Archive FOLDER-NAME discovery may run if Apr-May are missing. No Inbox email enumeration.')
    records = {'Nomura': {}, 'SinoPac': {}}
    audits = []
    errors = []
    session = win32.Dispatch('Outlook.Application').GetNamespace('MAPI')
    folders = get_inboxes(session)
    log(f'[INBOX COUNT] {len(folders)} (NOT enumerating their emails)')
    if not folders:
        raise RuntimeError('No Inbox could be opened; check Outlook profile')
    hits = {'Nomura': defaultdict(list), 'SinoPac': defaultdict(list)}
    seen = set()
    scanned_folders = set()
    tmp = mkdtemp(prefix='outlook_fast_equity_')
    try:
        def collect_from_folder(folder, kinds):
            # Always perform indexed searches ONLY; absolutely no full Inbox scan.
            folder_key = (str(folder.StoreID), str(folder.EntryID))
            for kind in kinds:
                search_key = (folder_key, kind)
                if search_key in scanned_folders:
                    continue
                scanned_folders.add(search_key)
                matches, search_error = get_matches(folder, kind)
                if search_error:
                    errors.append((kind, folder.FolderPath, search_error))
                    audits.append([kind, '', 'SEARCH ERROR', '', '', folder.FolderPath, search_error])
                for entryid, storeid, subject, path in matches:
                    key = (entryid, storeid)
                    if key in seen:
                        continue
                    seen.add(key)
                    if kind == 'Nomura':
                        day = date_from_subject(kind, subject, END_DATE)
                        if day is None or day < START_DATE or day > END_DATE or (TEST_ONLY_DATE and day != TEST_ONLY_DATE):
                            continue
                    try:
                        mail = session.GetItemFromID(entryid, storeid)
                        received = mail.ReceivedTime.date()
                        day = date_from_subject(kind, subject, received)
                        if day is None or day < START_DATE or day > END_DATE or (TEST_ONLY_DATE and day != TEST_ONLY_DATE):
                            continue
                        hits[kind][day].append((mail, subject, path, received))
                    except Exception as exc:
                        reason = f'MAIL OPEN ERROR: {type(exc).__name__}: {exc}'
                        log(f'[ERROR] {kind} {subject[:100]} => {reason}')
                        errors.append((kind, path, reason))
                        audits.append([kind, '', 'MAIL OPEN ERROR', subject, '', path, reason])

        for folder in folders:
            collect_from_folder(folder, ('Nomura', 'SinoPac'))

        def month_count(kind, month):
            return sum(len(v) for d, v in hits[kind].items() if d.year == 2026 and d.month == month)

        for kind in ('Nomura', 'SinoPac'):
            log(f'[APR-MAY INITIAL] {kind}: April={month_count(kind, 4)} subject-matches, '
                f'May={month_count(kind, 5)} subject-matches')

        # Even with holidays, a normal working month usually has >10 daily reports.
        # If either source has <10 April/May matches, inspect only named archive
        # folders. This avoids another scan of the enormous Inbox.
        missing_kinds = [kind for kind in ('Nomura', 'SinoPac')
                         if month_count(kind, 4) < 10 or month_count(kind, 5) < 10]
        if SEARCH_ARCHIVES_IF_APR_MAY_MISSING and not TEST_ONLY_DATE and missing_kinds:
            log(f'[HISTORY SEARCH] Low April/May coverage for: {missing_kinds}. '
                'Checking archive folder names, NOT scanning all messages.')
            for historical_folder in get_historical_folders(session, folders):
                collect_from_folder(historical_folder, missing_kinds)
            for kind in missing_kinds:
                log(f'[APR-MAY AFTER HISTORY] {kind}: April={month_count(kind, 4)}, '
                    f'May={month_count(kind, 5)} matched emails')

        for kind in ('Nomura', 'SinoPac'):
            count = sum(len(xs) for xs in hits[kind].values())
            log(f'[FOUND] {kind}: {count} relevant emails / {len(hits[kind])} report dates')
            for day, candidates in sorted(hits[kind].items()):
                candidates.sort(key=lambda item: item[3], reverse=True)
                last_error = ''
                for mail, subject, path, received in candidates:
                    try:
                        if kind == 'Nomura':
                            nums, attachment, detail = nomura_values(mail, day, tmp)
                        else:
                            nums, attachment, detail = sinopac_values(mail, day, tmp)
                        records[kind][day] = dict(nums=nums, status='OK')
                        audits.append([kind, day.isoformat(), 'OK', subject, attachment, path, detail])
                        if kind == 'Nomura' or TEST_ONLY_DATE:
                            log(f'[EXTRACT OK] {kind} {day}: {nums} ({detail}; {attachment})')
                        break
                    except Exception as exc:
                        last_error = f'{type(exc).__name__}: {exc}'
                        log(f'[EXTRACT ERROR] {kind} {day}: {last_error}')
                        audits.append([kind, day.isoformat(), 'EXTRACT ERROR', subject, '', path, last_error])
                if day not in records[kind]:
                    records[kind][day] = dict(nums=[None]*3, status='ERROR: see Audit')
        # Diagnose monthly completeness: exact counts of matched and successfully read reports.
        monthly_stats = []
        month_cursor = date(START_DATE.year, START_DATE.month, 1)
        while month_cursor <= END_DATE:
            yyyy, mm = month_cursor.year, month_cursor.month
            row = [f'{yyyy}-{mm:02d}']
            for kind in ('Nomura', 'SinoPac'):
                matched = sum(len(v) for d, v in hits[kind].items() if d.year == yyyy and d.month == mm)
                extracted = sum(v['status'] == 'OK' for d, v in records[kind].items()
                                if d.year == yyyy and d.month == mm)
                row.extend((matched, extracted))
            monthly_stats.append(row)
            log(f'[MONTH {yyyy}-{mm:02d}] Nomura matched={row[1]}, extracted={row[2]} '
                f'| SinoPac matched={row[3]}, extracted={row[4]}')
            month_cursor = date(yyyy + (mm == 12), mm % 12 + 1, 1)
        # Data exists even if one source failed; save summary with error rows.
        output = save_output(records, audits, monthly_stats)
        log('[OUTPUT] ' + str(output))
        for kind in ('Nomura', 'SinoPac'):
            good = sum(v['status'] == 'OK' for v in records[kind].values())
            log(f'[FINAL] {kind}: {good} report dates successfully extracted')
        if not hits['Nomura']:
            log('[DIAGNOSIS] No Nomura subject returned. Check the [FOLDER]/[SEARCH] lines; attachment reading was never reached.')
        elif not any(v['status'] == 'OK' for v in records['Nomura'].values()):
            log('[DIAGNOSIS] Nomura emails FOUND but attachment or Excel extraction failed. Read [EXTRACT ERROR] lines.')
        for kind in ('Nomura', 'SinoPac'):
            for mm in (4, 5):
                month_hits = sum(len(v) for d, v in hits[kind].items() if d.year == 2026 and d.month == mm)
                if month_hits == 0:
                    log(f'[MISSING MONTH] {kind} 2026-{mm:02d}: ZERO matching subjects in searched folders. '
                        'Check where these emails are stored, whether older subjects differ, and Outlook indexing.')
        if errors:
            log(f'[WARNING] {len(errors)} search / mail-open problems. Check the log and Audit sheet.')
    finally:
        # Cleanup must NEVER turn a successful extraction into a fatal failure.
        gc.collect()
        for attempt in range(3):
            try:
                shutil.rmtree(tmp)
                break
            except OSError as exc:
                if attempt == 2:
                    log(f'[CLEANUP WARNING] Temporary attachments could not be deleted: {exc}')
                    log(f'[CLEANUP WARNING] Folder left on disk: {tmp}')
                    log('[CLEANUP WARNING] Delete this temp folder after the file lock is released.')
                else:
                    time.sleep(0.3)
    return output


try:
    output = main()
except Exception as exc:
    log(f'[FATAL ERROR] {type(exc).__name__}: {exc}')
    for line in traceback.format_exc(limit=8).splitlines():
        log(line)
    raise
finally:
    # Save a log even if extraction fails; no actual attachment contents in this log.
    try:
        log_path = OUTPUT_DIR / f'Outlook_Equity_FAST_LOG_{datetime.now():%Y%m%d_%H%M%S}.txt'
        log_path.write_text('\n'.join(logs), encoding='utf-8')
        print('[LOG] ' + str(log_path), flush=True)
    except Exception:
        pass
