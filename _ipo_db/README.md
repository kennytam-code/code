# HK IPO Database + Comps Screener + Dashboard

**514 Hong Kong Main Board IPOs, Jan 2021 – Sep 2026, plus the live pipeline.**

Run everything through one command:

```
python ipo.py refresh    # update the whole database (resumable)
python ipo.py build      # rebuild workbook + dashboard
python ipo.py check      # validation gate
python ipo.py status     # coverage at a glance
python ipo.py newdeal 1234
```

Deliverables in `out/` — both work as plain downloaded files, no installs, no network:

| File | What it is |
|---|---|
| `HK_IPO_Database_v1.xlsx` | **NEW DEAL tab is the daily tool** — type a live deal's terms, get comps, implied multiples vs peers, and the day-1 analog. Pure formulas: no Bloomberg, no macros needed. Screener tab = pure Excel-2016 formulas (INDEX/MATCH/LARGE, no XLOOKUP/dynamic arrays), so it works with macros disabled and no add-ins. AH tab carries live Bloomberg `BDP` formulas with manual-override cells (live values only on a terminal). |
| `hk_ipo_dashboard.html` | Self-contained dashboard, 199 KB. Double-click to open. Verified to make **zero external requests**. Light/dark theme. |
| `screener_macros.bas` | OPTIONAL VBA (Re-rank, Snapshot-BBG). The workbook is fully functional without it. Alt+F11 → File → Import. Unblock the file first if Windows flags it as an internet download. |

## Conventions

- Money = HK$ millions. Percentages in percent units (12.5 = 12.5%). Day-1 `+` = closed above offer. A/H `+` = H rich vs A.
- **Market cap at IPO = ALL share classes × the H offer price** — the multiple an H buyer actually
  pays, so P/E and P/S stay comparable across the book. For an A+H issuer the prospectus states a
  different number on a MIXED basis (A shares at a 5-day average A price, H at the offer): Luxshare
  is HK$487bn ours vs HK$590,584m stated. Both are recorded; the gap is the A/H discount itself.
  The separate **A-line mkt cap now** column is today's whole-company value off the A line — the
  column to read when an H tranche looks deceptively small (Luxshare's tranche is HK$24bn; the
  company is ~HK$490bn).
- **Subscription level uses the filing convention**: 10x = ten times the shares available (nine times *over*-subscribed). AAStocks figures were shifted +1 onto this basis.
- Cell fills: **blue = your input**, grey = derived, green = cross-checked, amber = single-source/judgment/estimated, orange = sources conflicted.
- Comps are **subsector-first**: a same-subsector deal always outranks a same-sector-different-subsector one (LLM never comps to data-center). Weights live on the README tab and are editable.

## Verification status

- Screener scoring is **three-way identical** across Excel, the dashboard JS, and the Python reference. `test_screener_formulas.py` builds a miniature workbook and *evaluates the real formula chain* with the `formulas` engine (openpyxl only writes formulas, it never proves they compute).
- Offer prices reproduce exactly for six landmark deals (Kuaishou 115.00, CATL 263.00, Midea 54.80, Horizon Robotics 3.99, Mixue 202.50, Tianqi 82.00) — see the Verification tab.
- Per-year counts and proceeds reconcile against HKEX Annual Market Statistics / Fact Book (2021–2024 published; 2025–26 not yet available and left **null**, never estimated).
- `checks.py` is the gate; `data/scorer_fixture.json` locks the ranking so a weight change surfaces as a warning.

## Known gaps — read before quoting

Coverage figures below are measured on the current book (514 deals), not aspirational.

- **Sponsors: English legal names on 74% of rows; a displayable sponsor on 99%** — the display
  column falls back to the AAStocks 保薦人 (Chinese) name on 132 rows whose full prospectus body
  was never filed as one machine-readable document, and says so. Bookrunners: 72% English lists,
  same fallback logic in the display column.
- **Cornerstone names 72%, cornerstone % 89%** — final allocations from the allotment table where
  published, else the prospectus estimate. Many deals genuinely had no cornerstone tranche.
- **Market cap 512/514, P/S 93%, P/E 56%.** P/E is blank wherever the company lost money — that is
  an answer ("n/m"), not a gap. Two deals (0314, 3636) have no share count, offer-% of capital or
  published cap in ANY source, AAStocks included; their rows say so rather than carrying a number.
  The cap comes from a five-rung ladder, and every row says which rung produced it in the
  **Mkt cap basis** column: filed share count × offer price → offer proceeds ÷ offer-% of enlarged
  capital → issuer-stated cap → AAStocks 上市市值 → for A+H names only, the A line's total share
  capital × the H offer price.
- **There is no indicative price FLOOR in HK filings.** A prospectus prints a maximum offer
  price only, so "priced in range" is not computable; `priced_at_cap` and `pct_of_cap` are
  the honest equivalents (pct_of_cap now 100%).
- **Revenue 96% / net income 93%** — prospectus summary tables by column position, plus
  hand-verified press figures for machine-unreadable rows (each carries its source).
  Validated against Mixue, CATL, Horizon and Laopu Gold; the raw series is kept in `deals.json`.
- **Day-1 returns 514/514, re-measured on the local session list** (Yahoo misses debut bars —
  2155 and 2496 are missing their entire first session there); every return re-derives from the
  deal's own daily path against the offer price, with splits and entitlement issues handled and
  the convention stated on affected rows.
- **Stabilising manager on 378 rows, end-of-stabilisation notice linked on 347** — two-pass
  extraction (allotment announcement, then the prospectus definitions glossary), never inferred
  from the sponsor; a filed "no stabilising manager will be appointed" is recorded as fact.
  Deals inside their 30-day window cannot have an end notice yet and say so.
- **Offer-share counts rejected as implausible for 48 deals**; those sizes fall back to net
  proceeds, always labelled in the **Size basis** column (currently 220 stated-gross, 240
  price × shares, 50 net proceeds). Net proceeds are read from the deal's own sentence in the
  allotment announcement — NOT the greenshoe's "additional net proceeds" and not a
  use-of-proceeds bucket, both of which the parser used to confuse with the deal.
- **Sector/subsector are analyst judgment** (amber), assigned from each deal's own prospectus
  overview. Edit `scrape/classify.py` and re-run to reclassify.
- Underwriting fee splits are not public per deal — out of scope.

## The regime caveat that matters for trading

Day-1 returns now cover **all listed deals** (v1 had only 2024-2026, which flattered everything).
Across the full history the market's base rate moved enormously: 2021 median 0.0% with 44% of
deals closing up, 2022 0.0% / 34%, versus 2025 +12.5% / 70% and 2026 +21.9% / 74%. Read any
analog against the tape it came from — the Analogs tab breaks every bucket down by year.

## Running it

```
python ipo.py setup      # once: create .venv + install the 6 common deps
python ipo.py refresh    # update everything (resumable, per-stage caching)
python ipo.py build      # rebuild workbook + dashboard
python ipo.py check      # validation gate
python ipo.py status     # coverage at a glance
python ipo.py newdeal 1234
python ipo.py refresh --skip hkex     # if a source is blocked, run the rest
```

Layout: `ipo.py` is the only entry point; all pipeline modules live in `ipo_lib/`;
`requirements.txt` holds six common packages (requests, beautifulsoup4, lxml,
openpyxl, pypdf, yfinance). `requirements-dev.txt` (formulas, playwright) is only
for the verification suite — not needed to run the pipeline or open the outputs.

## Inclusion rule

"IPO" = Main Board listing with a public offering (an Allotment Results announcement
exists on HKEXnews). Listings by introduction, GEM listings/transfers, SPACs and
de-SPACs are excluded by design — which is why book counts sit slightly below HKEX's
"new listings" totals (reconciled on the Verification tab).

## Source hierarchy

HKEX filings (prospectus / allotment PDFs, parsed by script) > AAStocks aggregator >
verified press > analyst judgment (sector tags). Every key number in `deals.json`
carries `_prov` with its source and status. The Bloomberg mnemonics on the AH tab are
standard `BDP ... PX_LAST` calls but are flagged **await-terminal-verify** until you
confirm one row on the desk.
