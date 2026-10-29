# A/H Bloomberg horizon repair — 29 October 2026

User confirmed the missing 1D/7D/1M values occur in Bloomberg mode.
This is a formula/request-scope repair, not a market-data refresh.

## Findings and changes

- Existing BDH anchors were ordinary single-cell formula records, despite
  downstream references expecting date-and-price arrays. Responses now have
  explicit two-column native array ranges. Each short request reserves 65 rows
  for a 55-calendar-day window including headers; ascending numeric dates are
  requested. The 648 scalar lookup scans also have native array metadata so
  older Excel can evaluate their array arithmetic without manual CSE entry.
- The prior quote-date converter interpreted numeric YYYYMMDD as an Excel
  serial. It now accepts serial dates, numeric/text YYYYMMDD and date strings.
- A missing-history fixture exposed arithmetic on blank date cells. Availability
  checks now safely return No history. Outer visible formulas preserve status
  text rather than hiding all failures as blanks. Missing is never zero.
- All three horizons share dated H/A/FX history. Reference targets are anchored
  to the H quote date: prior H session, seven calendar days, one calendar month.
  A and FX are observed on/before the H reference date. Existing A/H entitlement
  factors and stale-observation guards are preserved. Outputs are percentage
  point changes in premium, not share-price returns.
- Current A/H prices use one scalar BDP LAST_PRICE each. The current FX quote
  is shared. AH E4 controls Quotes and the independent IPO-price checker; H4
  controls long chart history. Both default Stored. Live quotes with stored
  charts do not start the 16 full-history BDH formula occurrences.
- There are still 145 short-history BDH occurrences: two per pair and one FX.
  They are needed for historical premium comparisons; scalar last prices alone
  cannot reconstruct the prior premium. Historical range references in AH Delta
  fell from 11,304 to 4,536; expression text fell from 549,947 to 358,746 chars.
  These are structural counts, not measured terminal requests or RAM savings.

## Validation and limits

45 response-fixture checks exercise emitted formulas: date representations,
headers/padding/error replies, differing A/H calendars, unavailable history,
recent listings, missing dates, zero/negative saved premiums, signed changes and
independent corporate-action dates. Tests also cover every request range,
guard/control, native array metadata and patch idempotence. All 72 pair caches,
the 100 group-summary formulas and ten native chart parts retain their source
observations. The other 62 package parts are byte-identical, including Database,
Screener valuations, workbook names, styles and charts.

The final file opened in native Mac Excel without a repair prompt. Quotes and
Charts controls, the Stored table and the premium/A-share/CSI panels were
reviewed, then the workbook was closed without saving. Excel is view-only here;
no Bloomberg add-in/terminal execution or interactive live mode was certified.
The failures above are reproducible structural/formula paths, not proof of the
exact terminal response received on the user's computer. Formula statuses make
any remaining entitlement/response problems visible for terminal diagnosis.

Primary Bloomberg references:

- [Core Developer Guide, Excel BDP and BDH](https://data.bloomberglp.com/professional/sites/4/BLPAPI-Core-Developer-Guide.pdf)
- [Bloomberg Excel Desktop Guide, university-hosted vendor document](https://www.wu.ac.at/fileadmin/wu/s/library/databases_info_image/bloomberg_excel_desktopguide.pdf)
- [Bloomberg technical note showing LAST_UPDATE_DT as Date Of Last Update](https://data.bloomberglp.com/professional/sites/10/IBOR-Fallbacks-Technical-Note-08-11-2020.pdf)

The last source establishes the field mnemonic, not entitlement/availability
for every equity. No prices or dates were inferred from those documents.
