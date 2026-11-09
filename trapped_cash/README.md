# Trapped Cash Outlook export

[Open the Jupyter notebook](../trapped_cash_export.ipynb) · [Download notebook](https://github.com/kennytam-code/code/raw/refs/heads/main/trapped_cash_export.ipynb) · [Python source](../trapped_cash_export.py) · [Automated checks](https://github.com/kennytam-code/code/actions/workflows/trapped-cash-validation.yml)

Extract `Trading Book`, `Notional`, `EffectiveDate`, and `MaturityDate` from daily HTML email tables into one Excel workbook, starting **1 April 2026** and ending on the computer's current date when the settings cell runs.

## Run in Jupyter

1. Use Jupyter locally on **Windows with classic Outlook installed and signed in**. Remote Jupyter, Colab, new Outlook, and Outlook for Mac cannot use this COM connector.
2. Open Outlook and synchronize the history back to April 2026.
3. Download the notebook and open it in Jupyter. Run the installation cell once, then run all remaining cells in order.
4. Check the `Settings` cell: the default is your default mailbox's **Inbox and all its subfolders**. Use `MAILBOX_NAME` for another mailbox by its exact Outlook display name and `FOLDER_PATH = ["Reports", "Trapped Cash"]` for a folder beneath its Inbox. Archive folders and other stores are not searched automatically.
5. The result is a fresh, timestamped `.xlsx` in Jupyter's current working directory. The notebook prints its full path.

Alternatively, install dependencies and run the script from a terminal:

```powershell
python -m pip install -r trapped_cash/requirements.txt
python trapped_cash_export.py
```

To inspect mailbox display names in a notebook on Windows:

```python
import win32com.client
namespace = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
[namespace.Folders.Item(i).Name for i in range(1, namespace.Folders.Count + 1)]
```

## Matching and export behavior

- The subject is `Trapped Cash (DD-Mon-YY to DD-Mon-YY)`; the second date is the following calendar day, including month/year boundaries. For example, `Trapped Cash (30-Apr-26 to 01-May-26)`.
- The reporting date comes from the subject, so a delayed delivery is still included. Matching uses the exact subject; `RE:`, `FW:`, and extra subject suffixes are excluded.
- If the same date has multiple matching messages, only the latest received message is used. The duplicate count is logged. A parsing failure in that newest message is reported rather than silently substituting an older report.
- All body tables containing the four requested headers are included. Column order, whitespace, case, ordinary merged cells, and repeated headers are handled. Duplicate data rows and any source totals remain present.
- `Data` has exactly the four requested columns by default. `ExtractionLog` has one row per expected date, with the status, email count, selected folder/received time, table/row counts, and the original first/last Excel row for that date.
- Set `INCLUDE_REPORT_DATE = True` to add a fifth column if the report date should stay with each data row after sorting.
- Source values remain text to preserve identifiers, notional precision, and date formats. Set `SOURCE_DATE_FORMAT` to the exact source date format to create typed Excel dates. Notional values remain text; no totals or calculations are generated.
- Missing emails, empty tables, and extraction failures have separate log statuses. Missing dates include weekends and holidays. Folder access/search failures stop the run instead of falsely reporting complete coverage.
- Every run rebuilds the date range into a new workbook; it does not append duplicates or create a daily scheduled job. Generated workbooks contain mailbox data and are ignored by Git.

The code reads messages without setting read flags, moving mail, or sending mail. Screenshot tables, attachment-only reports, and unavailable/encrypted HTML bodies require a different extraction method.

## Validation

```text
python -m unittest discover -s trapped_cash/tests -v
```

The checks cover calendar boundaries, nested/merged HTML tables, missing headers, empty results, duplicate rows/messages, latest-message selection, extraction logs, source-value preservation, literal Excel cell text, notebook/script consistency, and the full export workflow with a simulated Outlook connection. GitHub Actions runs these checks on Windows and Linux.

**Live mailbox access is not certified by these tests.** Running the notebook against the intended Outlook profile is still required to verify that mailbox's permissions, synchronization, and actual HTML layout. The GitHub runner does not contain or access your Outlook mailbox.

Microsoft references: [Outlook filtering](https://learn.microsoft.com/en-us/office/vba/api/outlook.items.restrict), [HTMLBody](https://learn.microsoft.com/en-us/office/vba/api/outlook.mailitem.htmlbody), and [classic/new Outlook feature support](https://support.microsoft.com/en-gb/outlook/getstarted/feature-comparison-between-new-outlook-and-classic-outlook).
