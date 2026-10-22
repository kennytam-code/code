# Extract CPR M23 values

This Python script searches `G:\FIN_COMM\DeltaOne\Kenny\a` and its subfolders
for Excel files named `457276 CPR YYYYMMDD`, such as
`457276 CPR 20260918.xlsx`. It supports `.xlsx`, `.xlsm`, `.xls`, and `.xlsb`.

It saves **CPR_M23_summary.xlsx in your Downloads folder**, with exactly two
columns: `YYYYMMDD` and `M23`. The first row contains headers. Each following
row represents one matching source file, sorted from oldest to newest.
Dates are stored as real Excel dates and displayed as eight digits.

## Install and run

Use Python 3.10 or later. Open a terminal in the folder containing these files:

```powershell
python -m pip install -r cpr_requirements.txt
python extract_cpr_m23.py
```

The script reads cell **M23 on the first worksheet**. To select a named worksheet:

```powershell
python extract_cpr_m23.py --sheet "Summary"
```

To use another source folder:

```powershell
python extract_cpr_m23.py --folder "G:\another\folder"
```

The output always goes to Downloads when run from the command line. On Windows,
the script resolves the configured Downloads location, including redirected
folders. Existing reports are preserved by adding `_2`, `_3`, etc. to the name.

## Reading behavior

- One row is retained per file, including files with duplicate dates.
- Source files are read without modifying them; Excel is not required to run.
- Formula cells use their saved results. The script does not recalculate formulas
  or refresh links. Recalculate and save source files in Excel first if needed.
- M23 is copied as its underlying number: a percentage of 5% becomes `0.05`.
  Numeric zero is retained. Text, Boolean values, errors, and blank cells stop the
  run with the source filename, rather than producing a partial report.
- Excel temporary files and names with extra suffixes are ignored. Folder links
  and junctions are skipped. Invalid dates and unreadable folders stop the run.

The main `.xlsx` extraction and output behavior is covered by the included
tests. Run them with `python -m unittest discover -s tests -v` after installing
the dependencies. Windows Downloads resolution requires validation on Windows.

API references: [openpyxl saved values](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html),
[xlrd](https://xlrd.readthedocs.io/en/latest/api.html),
[pyxlsb](https://github.com/willtrnr/pyxlsb),
[Windows known folders](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath).
