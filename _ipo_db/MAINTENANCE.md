# HK IPO Database — MAINTENANCE RUNBOOK

Written for two readers: the analyst (Kenny, on the Nomura desk) and a future
Claude session on this Mac that is asked to "update the database". Everything a
refresh needs to know lives here. **Patch, never rebuild** — the data caches in
`data/batches/` and `scrape/` are weeks of accumulated work.

## The two machines

| | This Mac (build machine) | Nomura desk |
|---|---|---|
| Full refresh incl. AAStocks/Tencent/playwright | ✅ | ❌ (no playwright; some sites blocked) |
| Scripted refresh (HKEX, Yahoo, Tencent) | ✅ | ✅ `%run hk_ipo.py refresh` |
| Rebuild .xlsx / .html / .ipynb | ✅ `python ipo.py build` | ✅ `%run hk_ipo.py build` |
| Bloomberg columns compute | ❌ | ✅ (BBG Verify tab, BDH/BDP) |
| AI relabelling (subsectors, press sizes) | ✅ (a Claude session) | ❌ |

## Update cadence

**Weekly (desk or Mac):** `refresh` → `build`. That is all. Every stage is
resumable and staleness-aware:
- new allotment filings arrive → new deals appear end-to-end (roster → filings
  → parse → merge);
- a PHIP that has LISTED graduates out of the Pipeline automatically (it enters
  the listed roster; the pipeline dedupes by first word of the name);
- young deals' 1w/1m/3m fill in as their windows elapse, and `since IPO`
  refreshes, because `fetch_prices.py` re-fetches any cached code whose
  `last_date` is >7 days old or whose elapsed horizon is still blank
  (the `stale()` rule — do not remove it);
- stabilisation outcomes resolve as END-OF-STABILISATION notices get filed
  (only unresolved deals are re-searched).

**Monthly (Mac, ~30-60 min):** the enrichment stages that need playwright /
unblocked networks, then re-export to the desk:
```
python ipo.py refresh              # includes aastocks-deal + planned + prices
python ipo_lib/fetch_aastocks.py financials   # P&L for any NEW no-NI deals
python ipo_lib/fetch_ah_paths.py   # extends young A/H pairs toward day 92
python ipo_lib/audit_returns.py    # independent recompute; investigate any mismatch
python ipo.py export               # regenerates TO_NOMURA/ (5 files)
```
Carry `TO_NOMURA/` to `G:\FIN_COMM\DeltaOne\Kenny\ECM\`.

**When a new PHIP appears (needs an AI session):**
1. `refresh` already parsed it (financials, A-share venue, OC-announcement
   banks) and gave it a PROVISIONAL keyword subsector (amber, ~49% exact).
2. Ask Claude to: confirm/fix the subsector in `PIPELINE_LABELS`
   (`ipo_lib/fetch_phip.py`) — the analyst-label override map;
3. and refresh `data/batches/press_sizes.json` (expected size + source +
   confidence) — sizes there are ESTIMATES and are always displayed with their
   basis; empty is better than invented.

**When a pipeline deal LISTS:** nothing manual. Next refresh pulls its
allotment filing; it enters the Database with the full column set; the
first-word dedupe drops it from the Pipeline tab. Hand it a proper subsector in
`ipo_lib/classify.py` (`GROUPS`) at the next AI session — until then it wears
the amber keyword label.

## THE ROUTINE — run this whenever asked to "update everything" (v12)

The one sequence that graduates listed pipeline deals into the Database, pulls
any new pipeline, refreshes every return, and checks itself. Order matters.

```
# 1. everything HKEX + AAStocks + PHIP + offering-window prospectuses
python ipo.py refresh

# 2. prices (returns incl. ex-pop family), daily H paths, A/H daily paths
python ipo_lib/fetch_prices.py
python ipo_lib/fetch_h_paths.py
python ipo_lib/fetch_ah_paths.py

# 3. canonical merge (consumes bbg_desk + press_figures too)
python ipo_lib/merge_batches.py

# 4. THE GATE BATTERY — one command, and export refuses while any gate is red
python ipo.py check
#   = coverage floors + data identities/explained blanks + PRICES & RETURNS
#     (every deal, three ways) + formula bindings + Bloomberg lint +
#     Excel-computes parity + the visual gate (label overlaps, hidden scroll,
#     NaN, tooltip-less truncation — light AND dark).
# If prices were refetched, run the corporate-action sweep first — it is a
# refresh stage but worth knowing by name:
python ipo_lib/detect_splits.py     # writes data/auto_splits.json
# Monthly extras (network-heavy, not in the battery):
python ipo_lib/audit_returns.py              # independent recompute of returns
python ipo_lib/audit_opens.py 8 --horizons   # two-source day-1+1w/1m/3m (1/8 sample; full monthly)

# 5. rebuild + ship
python ipo.py export                         # TO_NOMURA/ → G:\FIN_COMM\DeltaOne\Kenny\ECM\

# 6. publish the two viewable files to GitHub (github.com/kennytam-code/code)
#    — TO_NOMURA/ is gitignored EXCEPT these two (whitelisted in _ipo_db/.gitignore)
git add _ipo_db/.gitignore _ipo_db/TO_NOMURA/HK_IPO_Database_v1.xlsx _ipo_db/TO_NOMURA/hk_ipo_dashboard.html
git commit -m "HK IPO database: refresh"
git push origin main
```

What to eyeball after: the Pipeline tab holds only unlisted names; the newest
listings show day-1 but blank 1m/3m (windows not elapsed — correct); checks.py
prints `0 failures`; the parity test prints `subsec gate … [OK]`.

**Bloomberg desk paste (bbg.xlsx):** on the terminal, open the workbook's BBG
Verify tab, let the BDP/BDH formulas resolve, paste-values into `bbg.xlsx`
(one sheet, headers on row 4 — the ingest reads columns by position), drop it
at `REPO/code/bbg.xlsx`, then `python ipo_lib/ingest_bbg.py` and re-merge.
Retail/instl subscription OVERRIDE the scrape (CP036/CP037 are the record);
`Mkt cap at listing (BBG)` is deliberately ignored — that desk formula is
wrong. P/E-at-listing lands in its own column beside the scraped multiple.

**`press_figures.json` is research, not scrape** — hand-verified numbers with
sources for rows no machine can read. Append to it; never regenerate it.

## v13 — what changed, and what the desk can now do alone

**One command on the Nomura machine.** `%run hk_ipo.py update` runs the whole
chain — fetch → parse → prices → chart batches → merge → gates → rebuild both
files — and ends with a VERDICT block that says plainly whether the output can
be trusted. Skip any blocked group and it still finishes on what it can reach:
`%run hk_ipo.py update --skip aastocks`. Verified end-to-end from a clean
folder: the desk's `data/deals.json` came out **cell-for-cell identical** to the
Mac's, and both output files rebuilt.

Bugs this exposed and fixed (all of them would have bitten on the desk):
- **`build` could delete everything.** `_unpack()` returns the SCRIPT'S OWN
  folder once `data/` exists beside it, and both build paths then called
  `shutil.rmtree(datadir)`. Running `build` a second time would have wiped
  hk_ipo.py, the data and both outputs. Every rmtree is now guarded with
  `if Path(datadir).resolve() != BUNDLE_ROOT`.
- **The bundle ran fewer stages than the Mac** — no offering-window prospectus
  parse, no A-premium-at-IPO leg, no chart batches. `audit_formulas.py` now
  fails if the two STAGES lists diverge (playwright-only `aastocks-deal`
  excepted), so this cannot drift again.
- **`ipo.py refresh` itself never ran the chart batches** — h-paths/ah-paths were
  hand-run. They are stages now.
- **merge crashed with a TypeError** when a base batch was missing; it now says
  which file, and what to run.
- **merge could not import its own helpers** on the desk (`clean_names`): the
  unpacked lib dir was not on `sys.path`.
- The bundle embeds **40 data files** (was 10) — every batch merge consumes — so
  a desk with NO network can still re-merge after a Bloomberg paste and rebuild.

**What still needs this Mac (be honest about it):**
- `aastocks-deal` (sponsors, full syndicate, market cap at listing, the
  institutional book) needs playwright. Without it those columns simply keep
  their last values; nothing breaks.
- Hand-labelled subsectors (`classify.py`) and `press_sizes.json` /
  `press_figures.json` are research, not scraping. New deals get a provisional
  keyword subsector (amber) until someone labels them.
- If HKEX/AAStocks/Yahoo/Tencent are blocked at the bank, those stages fail
  LOUDLY and the previous data stays. The files remain usable and correctly
  dated; they just do not gain that stage's update.

## v14 — real opens everywhere, open-to-open charts, amber means judgment

- **Tencent kline row[1] IS the open** — v13 threw it away and then had to
  withhold "Day-1 open→close" for every Tencent-sourced deal. `tencent_kline`
  now returns (date, close, open); the split-fix and no-Yahoo branches build
  real Open columns; `fetch_ah_paths` stores each pair's `h_open0`/`a_open0`;
  `fetch_h_paths` stores `open0`. Coverage: day-1 open pop and open→close are
  511/511. OmniVision cross-check: open 108.0 vs offer 104.8 = +3.05% pop.
- **Open-to-open convention (charts)**: every EX-POP panel rebases BOTH legs on
  their own day-0 opening print (A's open converted at the day-0 FX recovered
  from the series itself), and the premium-at-the-opens overlay uses
  (A open × FX) ÷ H open on day 0. The at-IPO premium panel starts at the level
  struck at pricing via the @offer lead-in dot.
- **A-share pane spans the listing**: month before → month after, split by the
  "H LISTS" rule, headline carries both legs (+17.0% → +29.6% style).
- **Scoring engine is text-proof**: Bloomberg-fallback TEXT in pe/size cells
  scores 0 via N() instead of poisoning LOG10 with #VALUE! (this broke the comp
  table for ANY target that carried a P/E — the parity fixture never had one,
  so the new "P/E target" probe in test_screener_formulas re-solves with
  C13=30 and asserts zero error cells). The A-share filter tests
  `is_h_share="Y"`, not `a_share_code<>""` — the fallback text made every deal
  count as an A/H pair.
- **Comp table adds**: "HSAHP @IPO" (Hang Seng AH Premium index on the listing
  day, BBG Verify col R → Database mirror `_hsahp_bbg`, desk-live BDH) sits
  next to IPO date; "Day-1 O→C" joins the return block. Probe letters in the
  parity test are now COMPUTED from COMP_COLS — never hardcode them again.
- **BBG Verify mktcap**: CUR_MKT_CAP arrives already in millions — the /1e6 is
  gone (desk-verified formula).
- **Amber now means judgment/soft-parse only** (3,122 → ~1,600 cells):
  deterministic derivations (NI sign, mktcap÷NI, stated caps, fixed-price caps)
  are plain "single"; 191 heuristic listing dates were auto-VERIFIED against
  the first traded bar (the exchange's own record) and turned green; the ~35
  that disagree stay amber on purpose — the bar date is probably righter than
  the heuristic. What stays amber: single-source PDF financials, prose-parsed
  subscriptions, amount-derived cornerstone %, keyword subsectors.
- **Explorer colour modes are all real** (sector / year / A-H / size bucket /
  up-down) with a live legend; the cornerstone cell's expander is one "+N all ▾"
  chip (the old grey +N doubled it into "+23+23").

## v15 — sources named, the screener mirrors the Database, new PHIP flow proven

- **What "Tencent" is**: web.ifzq.gtimg.cn/appstock/app/fqkline/get — the public
  market-data API behind gu.qq.com (Tencent Finance, one of mainland China's
  largest retail quote services). Its bare `day` series is RAW exchange prints,
  no split adjustment — the right series to compare against an offer price.
  `audit_opens.py` now cross-checks day-1 OPEN and CLOSE for every deal against
  Yahoo (fresh pulls, no cache) and classifies every row: agree ±0.5% /
  split-adjusted-Yahoo (disagreement EXPECTED, raw is the record) / Yahoo-blind
  recycled codes / UNEXPLAINED (gate fails if any). Graph-level proof: SICC's
  eight pane numbers (h0/a0 opens+closes, day-1, open-pop, prem[0], open-prem)
  reproduce from fresh raw pulls with independent code, to the tick.
- **The comp table is now GENERATED from DB_COLS** ("the screener should have
  whatever we got in database"): same headers, formats, bands and widths as the
  Database, minus links/prose/identity-dupes (COMP_SKIP), plus the scoring
  block. A new Database column lands in the screener automatically, and
  audit_formulas checks both against the same source.
- **P/E blanks are now a closed list**: 193 loss-makers (n/m on BOTH sources —
  Bloomberg prints #N/A for them too, that is the field working, not failing),
  29 no-NI + BBG blank, 10 withheld by the plausibility gate (2 of which BBG
  "confirms" only at 1,597–2,073x — past the 1,000x ceiling, stays out), 7 no
  mktcap + BBG blank. Sane BBG values now PROMOTE into the main column with a
  basis note (270/511 filled).
- **lint_bbg.py** walks all ~5,700 Bloomberg formulas: parens/quotes balance,
  mnemonics against the desk-proven set (values that actually came back in
  bbg.xlsx), BDH dates anchored on the Database, IFERROR guards. It caught 123
  unguarded AH-tab BDP cells that printed #NAME? off-terminal — fixed.
  "HSAHP Index" is flagged AWAIT-VERIFY until one cell is confirmed on the desk.
- **New-PHIP flow, exercised for real**: Medcaptain Medical (PHIP 2026-08)
  arrived via `fetch_phip`, financials parsed (rev RMB1.78bn), hand-labelled
  "Medical devices" in PIPELINE_LABELS, now the 11th pipeline card everywhere.
  The fetch also caught a v14 REGRESSION: series_from's new 3-tuple broke the
  2-tuple unpacking in fetch_phip/fetch_newlistings — every PHIP financial
  parse was dying silently ("too many values to unpack"). Fixed both callers;
  when you change a shared helper's signature, grep EVERY caller.

- **The opens audit's first full run paid for itself**: 474 deals agree to
  ±0.5% on both open AND close; 10 are Yahoo-blind recycled codes (Tencent
  only); 26 disagree by exactly their split factor (the book already uses raw —
  expected); and ONE real error surfaced: REGO (2422) — Yahoo carries a hidden
  x1.194 capital-action adjustment WITH NO SPLIT ROW, so the split-guard never
  fired and the book's day-1 read +76.7% instead of the true +110.9%. Fixed,
  and generalised: `data/force_raw_codes.json` — the audit auto-appends any
  uniform-factor code, `fetch_prices` force-drops Yahoo for codes on the list,
  and the list ships in the desk bundle.

## v16 — visibility as a gate, horizons in the audit

- **"Visible" now has a machine definition and a scanner**: no element may hide
  content behind a horizontal scroller, and no text may ellipsize without BOTH
  a hover tooltip and (where it matters) a click-through. The clip-scanner
  found the A/H pane row hiding two panes behind 380px of scroll on every
  screen — the six panes are now a 3×2 grid, all visible, taller. The deal
  table was 242px wider than the viewport: P/S dropped (it lives in the
  screener), subsector display names shortened with the full name on hover
  ("Smart hw / cons. elec."), dates compacted to yy-mm-dd with full date on
  hover, cornerstone cell shows the TOP HOLDER + "+N all ▾". The table now
  fits 1440 with zero hidden pixels. Excel: all headers wrap inside their
  30px header row — zero truncations.
- **audit_opens --horizons** extends the two-source check to the 1w/1m/3m
  closes (offsets 5/21/63) — the REGO class of hidden adjustment is now
  screened across the whole first three months, and uniform-factor codes
  auto-join force_raw_codes.json.

## v17 — the review IS the battery now

"Check everything again" is a command, not a conversation:
`python ipo.py check` runs the six gates and `python ipo.py export` REFUSES
while any is red (`--force` exists and announces itself). Every gate began as
a manual check that caught a real error: coverage floors, arithmetic
identities + the explained-absence contract, formula-binding audit (the c_sub
class), Bloomberg lint (the 123 unguarded AH cells), Excel-computes parity
(the P/E-target probe), and the visual gate (the hidden A/H panes, the CATL
label collision — light and dark). audit_visual skips gracefully where
playwright is absent, so the desk bundle can run the battery too.

Tidiness rules locked in this pass: the Analogs machine keys live in a HIDDEN
helper column (a visible wall of "Biotech 18A|10-100x" is clutter, and the
lookups follow the defined names); stale change-notes do not belong in UI copy
("P/E proximity now outranks profitability" said nothing to a first-time
reader); the peer-median day-1 tile is the PRIMARY tile, and Day-1/1-month are
key-columns in the comp table — the numbers a position is sized off carry the
visual weight.

## v18 — every orange adjudicated; the brief reads like a trade

- **Zero conflict-orange cells.** Every source disagreement is now RESOLVED by
  evidence, three ways: (1) quality adjudication — a clean researched list
  beats a damaged-table parse ("Subtotal", "upon Listing Top", address bleed
  all score as garbage; the research batch also stored its lists as STRINGS,
  which lost every comparison until coerced); (2) cross-check repair — a
  cornerstone % that fails the AAStocks-institutional-total check by 20pp+ is
  a placing-table bleed, REPLACED by the filed aggregate amount (CALB 93%→58.7%,
  MTT 100%→24.8%); a cap below the struck price is popped, not shown;
  (3) hand rulings in data/batches/conflict_rulings.json (append-only, carries
  the reason; supports value overrides — GigaDevice's SPV names swapped for the
  press-corroborated managers). cornerstone_n is now derived from the final
  list, never merged. A Bloomberg/press winner marks the cell RESOLVED, and a
  later low-rank disagreement can no longer repaint an authoritative winner.
- **Deal Brief = the four medians a position is sized off**: DAY-1 POP
  (primary tile) then 1-week / 1-month / 3-month EX-POP, coloured by sign,
  plus the base rate and the worst-peer downside. Shared CS appears in the
  top-5 table only when a comp actually shares an investor.
- Lesson recorded: an inserted helper landed at column 0 INSIDE main() and
  silently ended the function — the merge "ran" green while skipping half its
  body. After structural edits, assert the function's statement count/span
  (ast), not just that the file parses.

## Conventions the desk relies on (do not flip back)

- **A-premium, not H-discount** (v12): every premium in the book is
  `A over H − 1`, + = A trades above H. Columns: `A prem vs H at IPO`
  (A close the day before listing ÷ H offer − 1) and `A premium (today)`.
  The AH tab's live formula, the dashboard, the notebook and the screener all
  use this one direction. If a number looks flipped, check it is not being
  read as the old H/A convention.
- **The FX chain, end to end** (asked and verified 2026-08-21). Every A-leg is
  converted with the CNYHKD rate of ITS OWN session, never a flat 1.10:
  `a_close_cny x cnyhkd = a_close_hkd` (CATL: 260.00 x 1.0838 = HK$281.80), and
  the daily path multiplies each day's A close by that day's FX before forming
  the premium. The at-IPO anchor and the daily series therefore join exactly —
  verified by identity on all 59 pairs:
  `(1+prem[0]) == (1+prem@IPO) x (A0/A_prev) / (1+day1)`. The visible step at
  day 0 is the day-1 pop offset by the A line's own overnight move, nothing else.
  `a_premium_now` comes from a DIFFERENT source (the AAStocks snapshot, today)
  and legitimately differs from the daily series' last point (~day 92) — median
  14pp apart, because they are different dates, not different maths.
- **One field runs the other way, on purpose and labelled**: the pipeline's
  `h_cap_vs_a_pct` is H-cap over A (that is how an offering is quoted). Its
  A-over-H twin `a_prem_vs_hcap_pct` is derived beside it so the pipeline row is
  comparable with the Database's A-premium columns; the dashboard tile shows the
  A-over-H number and states the H-over-A read in its own label.
- **Ex-pop family** (v12): `1w/1m/3m ex-pop` start at the day-1 CLOSE;
  `Alpha 1m ex-pop` nets the index over the identical day-1-close window;
  `Day-1 open→close` is the intraday move after the opening print (withheld
  for Tencent-sourced series — a raw close line has no true open). Ex-pop
  columns wear TEAL headers; with-pop columns navy. The dashboard uses the
  same tint on chart backgrounds.
- **Tencent kline `n` must be ≤1500** — the endpoint answers 200-with-empty
  above that (it blanked an entire fetch on 2026-08-20). It also throttles
  bursts by answering empty; the helper retries with backoff, keep ≥0.6s
  sleeps in loops.
- **Extreme multiples**: >300x is withheld UNLESS Bloomberg independently
  prints the same level (±25%, and ≤1000x) — CALB's 549x is real and stays;
  DRCB's 9,514x "bank P/E" is a shared artifact and stays out.
- **`audit_formulas.py` is the guard against the class of bug that hid longest.**
  It resolves every `Database!$X$n` in the Screener and Calc sheets back to a
  FIELD NAME and compares it against what the cell's own header says it pulls,
  checks each per-deal formula references its own row, and asserts the card's
  labels still sit beside the cells the engine reads. Run it after any layout
  change; a moved row now fails loudly instead of silently ranking on the wrong
  column. Its inputs (`COMP_COLS` / `COMP_PULL`) are module-level in
  build_xlsx.py on purpose — one definition, shared by builder and auditor.
- **A silent fallback is a bug, not a safety net.** The split-correction (raw
  Tencent instead of Yahoo's split-adjusted line) failed quietly when the
  endpoint rejected `n=3000`, and 26 deals silently reverted to a 1,360% day-1.
  The engine now sets `split_uncorrected` + a loud `price_note` when the
  correction cannot be applied. If you ever see that flag, refetch — do not ship.
- **Charts vs columns, the two anchors**: chart panels labelled EX-POP rebase on
  the day-1 OPEN (what you could actually buy). The ex-pop COLUMNS keep the
  day-1-CLOSE basis (the standard aftermarket definition the index alpha is
  matched to). Both are stated on the panels and on the Notes tab.
- **The A-premium series starts at the level struck at pricing.** It is drawn as
  a dot at `@offer` LEFT of day 0 with a dashed lead-in, because stacking it at
  x=0 turned every line's drop into one vertical bar and crushed the scale.
- **Excel and HTML carry the same field set**, enforced by audit_formulas step 6.
  Adding a Database column without adding it to `build_dashboard.KEEP` (or vice
  versa) now fails the gate.
- **Two singleton subsectors are deliberate**: SF REIT and SANXUN (sole REIT,
  sole developer) can never fire the subsector gate — they fall back to
  sector scoring honestly rather than being force-paired.

## What each stage writes (ipo.py STAGES, in order)

| Stage | Output batch | Notes |
|---|---|---|
| roster-aastocks / roster-hkex | hkex_allotments.json | the deal universe (Allotment Results = every IPO) |
| filings-* / parse-* | prospectus/allotment parses | full-text caches in `scrape/text_cache/` |
| classify / classify-auto | subsectors | hand labels in classify.py ALWAYS win |
| pipeline-phip | phip_pipeline.json | PHIP parse + OC-announcement banks (PHIP covers redact them) |
| names-cn | names_cn.json | HKEX bilingual feeds |
| stabilisation | stabilization.json | end-of-stabilisation outcomes, resumable |
| aastocks-deal | aastocks_deal.json | 保薦人/包銷商/上市市值/機構性投資者 — playwright, Mac only |
| ah-snapshot | (premium today) | uncached by design |
| prices | prices.json | Yahoo + Tencent fallback; staleness-aware |
| ah-at-ipo | ah_ipo.json | A close before listing × CNYHKD, twice-sourced |
| merge | **data/deals.json** | THE canonical file; all adjudication rules live in merge_batches.py |

| offering-window | newlistings.json | www2 New Listings table; FULL prospectus parse of deals still open for subscription (expected P/E at range, cornerstone, timetable) — desk-safe |

Not in STAGES (run monthly on the Mac): `fetch_aastocks.py english` (EN names for
sponsors/underwriters/cornerstones — the DISPLAYED set), `fetch_aastocks.py financials`,
`fetch_aastocks.py planned`, `fetch_ah_paths.py` (incl. each pair's A-share month
BEFORE the H listing), `audit_returns.py`, and the A+H-universe diff
(ah_universe.json — proves no missed A-share codes).

## Gates — run before every export

```
python ipo_lib/checks.py                 # 0 failures required (floors inside)
python ipo_lib/test_screener_formulas.py # PARITY MATCH + 0 error cells required
```
The build itself refuses to save a workbook with unbalanced formulas.

## Known caveats (learned the hard way — keep them true)

- **Dashboard CSS: sticky belongs only to tables inside their own scroll
  container.** The generic `table.tbl th` was once viewport-sticky — the
  side-by-side matrix header detached from its columns and slid under the page
  nav. Only `.tbl.deals` (own scroll box) keeps a sticky header. And when two
  rules tie on specificity (`.labtbl thead th` vs `table.tbl th`), the LATER
  one in the sheet wins — the matrix header alignment rules are written as
  `table.labtbl thead th` so they out-rank the generic left-align regardless
  of order.
- **Helper ranges never share a sheet OR A COLUMN with anything else.** The
  cornerstone-split scratch once sat in Calc J1:J5 — the same column as the
  score — and silently killed every comp formula. Scratch lives in Calc T:Y.
- **Helper ranges never share a sheet with a growing table.** The screener
  pick-list lives on the Calc sheet (cols K:Q) because twice a widened table
  overwrote hidden helpers and silently corrupted everything to its right.
- Yahoo lies twice: it back-adjusts for splits (undo with the per-bar factor)
  and returns current quotes for codes it has no history for (the DEBUT_LAG
  guard + Tencent fallback exist for this — 0300/0501/0917 class).
- The PHIP cover REDACTS bank names; the same-day OC Announcement carries them.
- AAStocks 機構性投資者 is a SUPERSET of cornerstones (anchors included) — its
  total being larger than the prospectus % is expected, not a conflict.
- `oversub_intl_mult` values <1 on a deal priced at cap with a hot retail book
  are percentage-misreads: flagged orange, resolved on the desk via CP037.
- P/E is only for profitable issuers (n/m otherwise); market cap carries its
  derivation basis in `mktcap_basis`.
- EastMoney is IP-blocked from this network; Tencent (`web.ifzq.gtimg.cn`) is
  the working CN source for HK/A-share/FX history.
- The `formulas` test library cannot resolve BDP/BDH — Bloomberg cells are
  excluded from parity by design and only compute on the desk.
- Cornerstone SIMILARITY matches on `cornerstone_keys` (normalized first-token
  names, derived in merge via clean_names.investor_key) — never on raw names.
- The dashboard build ASSERTS embed key-coverage for ah_paths (fetched fields
  must reach the page); extend the same guard when embedding a new batch.

## v19 (2026-08-24) — cornerstone league, effective free float, filter leak

- **CS League** (Excel sheet + HTML "Cornerstones" tab): one row per investor,
  grouped on the Screener's normalized key (`clean_names.investor_key`), with
  n deals, day-1 hit rate, and average day-1 pop / 1w / 1m / 3m ex-pop.
  Aggregation lives in ONE place — `clean_names.cs_league` — imported by both
  builders, so the two deliverables cannot disagree.
- **Eff. free float (% of cap)** = deal size × (1 − cornerstone%) ÷ market
  cap — the slice that can actually trade on day 1 (cornerstones locked 6
  months). Derived in merge, identity-checked in audit_identities, blank only
  with `eff_ff_note`. No-cornerstone deals use cs=0 (the whole offer floats);
  a deal with a list but no % stays blank rather than pretending.
- **A-share filter leak (user-caught)**: comp rows come from
  `LARGE(score_rng, k+1)`; with a hard filter on, most scores are −999999 and
  the tail slots rendered those gated rows as phantom comps. Every comp-row
  formula now blanks when the k-th LARGE ≤ −900000. Probe in
  test_screener_formulas sets the filter and asserts no non-A name renders.
- **Index column names**: "Index 1m ex-pop" was nonsense (an index has no pop
  to strip). Renamed to state the window: "Index, IPO→1m" (bench_1m_pct) and
  "Index, d1→1m" (bench_1m_expop_pct — same window as the 1m ex-pop leg).
- **Cornerstone press round 2** (all in press_figures.json, append-only):
  2531 Carlink = ONE cornerstone (Huizhou Guohuilian; the "ZH-tendency Inc"
  garbage was the LOCK-UP shareholders table, not cornerstones); 2714 Muyuan =
  14 houses at exactly 50.0%; 9981 Woer = 16 entities incl. three OTC-swap
  rows (parse had deduped to 11 and included a placee); 3881 CIDI = the five
  parsed names were the prospectus's own short forms (only an RMB amount had
  glued on); 2566 Jiuyuan = 7 real names (Fosun/Alibaba Health/Jointown...)
  at 49.66% post-clawback. Lesson: a cornerstone table that parses "clean"
  can still be the WRONG TABLE — lock-up undertakings and placee lists sit
  pages away and look identical.
- **Cleaner v2**: trailing subscription amounts ("… RMB70,000,000"), leading
  "Shareholder(s)"/"Offering Relationship" bleed, embedded "Subtotal", "…
  Top" tails, "Hong Kong Limited"-class orphans; within-ONE-deal truncation
  fold (RIME ⊂ RIME Capital) — across deals that fold stays off (unsafe).
- **cornerstone_pct upper-bound fill**: deals with a list but no % take
  AAStocks institutional-total ÷ deal size, capped at 100, note says "upper
  bound — table can include non-cornerstone orders". Remaining gaps carry a
  "% not stated" note.
- **ipo.py refresh hang (2026-08-24)**: the stage runner sat 35 min at 0.08s
  CPU with zero output (cause not found — first network call inside the
  runner never returned). Workaround that works every time: run the stages
  directly (`run_stages.py`-style driver, per-stage timeout, merge last).
  If refresh hangs again, don't wait — drive the stages.
- **data/manual_splits.json** (CIDI 3881, 1→10): Yahoo split rows are
  discarded by design (the Zhida double-record lesson) and raw Tencent
  prints carry subdivisions UNADJUSTED — CIDI's "3m −91% / since −93%" was
  the subdivision, not a crash (true: −11.8% / −28.0%). The file multiplies
  raw-print bars on/after each date by the ratio, in fetch_prices (both
  branches) AND fetch_h_paths. Two rules: (1) every entry needs a filing
  (HKSCC circular) as evidence; (2) use the DEALING date, not the circular's
  "effective" date — prints divide when dealing in subdivided shares starts
  (CIDI: effective 02-20, dealing 03-02; the kline series proves which).
  Note: prices.json caches for 7 days — after editing this file, pop the
  code from prices.json + h_paths.json and re-run both fetchers.
- **A-share filter root cause (v19)**: the Database `a_share_code` cell is a
  BBG-fallback FORMULA whose off-terminal text ("not filed — run on
  terminal") is non-empty for EVERY deal — `<>""` passed the whole book.
  The gate now tests `is_h_share="Y"` (values, not formulas). This is the
  v14 lesson re-learned: NEVER gate on text non-emptiness of a cell that
  can hold fallback text; gate on the dedicated flag.
- **League verification lessons (v19)**: (1) two spellings of one investor
  inside ONE deal double-counted the deal (TAL China Focus "2 deals" was
  one) — cs_league dedupes keys per deal, and an assertion in review is
  "no investor counts one deal twice"; (2) bare Chinese surnames folded
  different PEOPLE into one row ("Yang Xiaojie" held 6 Yangs) — surnames
  are in the keep-two-tokens set now; (3) same house split across rows
  (HHLRA/HHLR, Schroders/Schroder, Southern-AM, MSIP/Morgan Stanley) —
  folded by a narrow rule (≥4-char key prefix + ≤1 extra char or one
  generic token) plus a curated `_ALIASES` map that requires book-internal
  evidence; near-misses (Al-Rayyan vs All View, Da Cheng vs Dajia) proved
  the rule must stay narrow.

## v20 (2026-08-25) — split sweep, price arbiter, zero orange

- **Corporate actions were unadjusted across the WHOLE raw-print class, not
  just CIDI.** Any deal whose Yahoo series reports a split is rebuilt from
  RAW Tencent prints — and raw prints carry subdivisions/consolidations
  unadjusted. `ipo_lib/detect_splits.py` now sweeps every raw-print deal:
  Yahoo split rows are CANDIDATES, and each is confirmed against a real
  scale change in the raw series before it is applied (unverified candidates
  are listed and left alone — WELLCELL's second row failed and was skipped).
  26 deals corrected; the effect is large (NOAH −95% → −50% since IPO, HESAI
  −91% → −7%, ZHIDA −85% → −23%, NUOBIKAN −86% → +29%). Re-run it whenever
  prices are refetched; output is `data/auto_splits.json`, hand-curated
  `data/manual_splits.json` still wins per code. Both directions work:
  ratio 10 = subdivision (multiply later prints by 10), 0.1 = consolidation.
- **The day-1 close is the ARBITER for a disputed offer price.** Research
  found the filing-PDF parse wrong 6 times out of 6 against AAStocks
  (BAIGE's "price" was the LISTING EXPENSES line, HK$54,382,183; HESAI
  154.99 vs the true 212.80; PONY 252.25 vs 139.00 …), so priority alone was
  picking the loser. merge now computes `close ÷ (1 + reported day-1 %)` and
  keeps whichever candidate that implies, before any priority rule. Plus two
  band guards: an offer price must sit in [0.05, 3000] and a market cap
  under HK$3tn — both are gate-checked, and a cap that fails is recomputed
  from shares × price or emptied with a reason.
- **Zero orange cells.** Sponsor conflicts were mostly press short forms vs
  filing legal entities ("CICC" vs "China International Capital Corporation
  Hong Kong Securities Limited") — they now compare on the normalized house
  key and CONFIRM each other. Two were genuine: ANKER's list was the
  PARTIES-INVOLVED table (compliance adviser, receiving bank), JOYSON was
  missing CICC; both press-ruled. Midea's subscription disagreement is a
  documented basis difference (both figures named in the note), and an
  institutional-sub reading we can prove wrong is now EMPTIED with the
  rejected value in the note rather than published as orange.
- **investor_key: never key a house to one generic word.** CICC's legal
  name reduced to a bare "china" (every token is a dropped generic), which
  both missed its own short form and risked colliding with any other
  China-named house. The all-generic path now keeps two tokens, and a small
  evidence-backed `_ALIASES` map covers initialisms (msip→morgan,
  cicc→china-international, gtja→guotai).
- **SHEIN appeared TWICE in the pipeline** — a curated watch-list row and
  the live offering-window row — so the tabs disagreed on its sector.
  `ipo_lib/pipeline_dedupe.py` (used by BOTH builders) keeps one row per
  company: the coded live record wins on facts, the curated HAND
  classification wins over a scraped industry string, and the filing's own
  industry stays visible with a `classification_note`.
- **Prose is clipped on a boundary, never mid-word** (`ipo_lib/textclip.py`):
  descriptions end on a SENTENCE, proceeds buckets on a word, PDF glyph
  artefacts ("/H1118") and tables-read-as-prose ("2023 2024 2025 118 250")
  are cut away. The pipeline card's 4-line clamp is a DISPLAY choice, so it
  now ships with a more/less toggle — a clamp with no way to expand reads
  as truncated data.
- **League verification round 2**: the "their deals" chip was clipped away
  by the inherited `td.csx` ellipsis (names truncate, the chip must not);
  min-deals is a typed number; WITH-POP (day-1/1w/1m/3m vs offer) sits
  beside EX-POP under grouped headers; a long list scrolls inside its cell.

## v21 (2026-08-25) — every price and return, checked three ways

`ipo_lib/audit_prices.py` is now a RED gate. It runs network-free on the
batches already on disk and answers the three questions that matter: was the
right thing extracted, is the arithmetic right, and was a corporate action
missed. It found four real defects, all now fixed.

- **33 deals carried a SATURDAY listing date** (plus one on a HK public
  holiday). HK allotment results are often published on a Saturday with
  dealings starting the next business day, and the HKEX-derived field is
  literally named `ipo_date_est`. A wrong listing date makes the two price
  sources pick DIFFERENT debut sessions — Morimatsu's day-1 read +213.7% off
  session two instead of +258.9% off session one. AAStocks' "Listing Date"
  (dealings commenced) now wins outright, and a weekend listing date is a
  gate failure.
- **Yahoo's HK history has HOLES.** Both STARPLUS and KEEP are missing the
  2023-07-17 session; a missing session shifts every trading-bar horizon by
  one day (up to 15pp on a volatile debut), and Yahoo can miss the DEBUT
  itself. Returns are therefore measured on the LOCAL kline session list —
  the same series the dashboard's charts draw — so the return columns and
  the chart can no longer disagree. 5 day-1 and 48 horizon values changed;
  all 511 now recompute exactly from the raw prints.
- **16 deals published a "gross" smaller than their own net proceeds**
  (YesAsia: gross HK$4.5m vs net HK$91.0m) and deal_size took that figure —
  a HK$117m deal shown as HK$4.5m. Gross < net is arithmetically impossible,
  so the stated gross is now rejected and the size falls through to
  shares x price, then to net, with the rejection stated in the note.
- **Two more "maximum offer price" extractions** (XUANWU 6.91 vs the true
  6.24, JENSCARE 28.80 vs 27.80 — both exactly the stated maximum, the same
  bad anchor that was wrong 6/6 in v20). Ruled in conflict_rulings.json on
  local evidence: the independently ingested day-1 is consistent only with
  the aggregator's price, and Jenscare's record also parsed gross < net.
- **Derived legs are re-derived LAST.** alpha = ret − bench and the ex-pop
  legs are now recomputed after every source has landed; computing alpha
  beside the return that produced it left one deal stale when a later batch
  refreshed its benchmark.
- Two audit checks were deliberately narrowed after producing explained
  signals: the two sources are compared only on the SAME session (where
  Yahoo lacks the debut, a price difference is expected, not evidence), and
  a round-factor jump is reported only when the sources also DISAGREE over
  the window containing it — a hot small cap doubling in a session looks
  identical to a 1:2 action, and MANYCORE/QIYUNSHAN/HUASHI were real moves.
- Greenshoe tolerance: shares x price may exceed the stated gross by up to
  15% (an exercised over-allotment against a base-offering gross) before it
  counts as a mismatch.

## v22 (2026-08-25) — cross-checked against news, and the typhoon lesson

Every value v20/v21 changed was put to independent sources. Two findings
came back, one confirming and one refuting.

- **All 8 corporate actions CONFIRMED** against HKEX primary filings —
  ratio and date both, for HESAI (1→8, 2026-07-10), NOAH (1→10,
  2023-10-30), ZHIDA (1→5, 2026-03-03), NUOBIKAN (1→10, 2026-03-11),
  GOGOX (10→1, 2025-04-25), FLOWING CLOUD (20→1, 2025-12-05), JOINN
  (three 4-for-10 bonus issues, ex-dates 2021-06-23 / 2022-07-28 /
  2023-06-20) and CIDI (1→10). Two things worth keeping: for splits and
  consolidations the effective date and the dealings-start date are the
  SAME day — the ~2-week gaps in those timetables are parallel-trading and
  certificate mechanics, not price-scale events; for BONUS issues the price
  re-scales on the EX-DATE while the bonus shares only become dealable
  4–6 weeks later. CIDI's effective date was POSTPONED from 2026-02-20 to
  2026-03-02 (Mainland holiday delayed certificate exchange), which is why
  the kline series changes scale on 03-02.
- **The Saturday fix over-corrected ONE deal, and finding out why exposed a
  real defect.** New Media Lab (1284) was moved to 2023-07-17 — but HKEX was
  shut all day for Typhoon Talim, so dealings began 07-18 and the original
  reading (+1.09%) was right. The general cause: **the kline feed inserts a
  PLACEHOLDER bar on days the exchange never opened**, repeating every
  stock's prior close. Counting one as a session shifted horizons by a day
  (which is what the v21 note misread as "Yahoo has holes" — Yahoo was
  right to omit those days), and a listing scheduled into a closed day gets
  a placeholder bar at the offer price that reads as a flat debut.
  `ipo_lib/sessions.py` derives the real trading calendar from the book
  itself: on a closed day EVERY stock's bar repeats its prior close, so a
  date with several bars and none of them moving was not a session. It found
  all three 2023 closures unaided (Talim 07-17, Saola 09-01, the 09-08 black
  rainstorm). merge measures on the filtered list and moves a listing off a
  closed day with a stated reason. Morimatsu (+258.9%) and YZYBIO (0.00%)
  survive this — both independently confirmed by listing-day press.
- **`Verify (BBG)` workbook tab** — the whole change-list on one screen for
  the terminal: our value, a BDP/BDH call for Bloomberg's, and a VERDICT
  cell that reads MATCH or CHECK by itself. Four sections: listing date +
  day-1 close, offer prices ruled against the filing parse, corporate
  actions (our day-1 close ÷ the cumulative factor must equal Bloomberg's
  adjusted print for that day), and the rebuilt deal sizes. Two mnemonics
  are new and flagged AWAITING VERIFY: `EQY_INIT_PO_SH_PRC`, `EQY_SH_OUT`.
- lint_bbg's BDH rule was widened from "must reference the Database" to
  "must reference a CELL, never a literal date" — the intent was always to
  forbid frozen dates, and the Verify tab anchors on its own date column
  because corporate-action dates are not in the Database.

## v23 (2026-08-25) — multiples everywhere, force-include, live P/S

- **P/E & P/S basis is ONE thing, stated everywhere: TRAILING.** Market cap
  at the final offer price ÷ the last FULL pre-IPO fiscal year's net income
  (P/E) or revenue (P/S), as filed. Pipeline expected multiples use the same
  definition at the range, so SHEIN (12.4–13.0x P/E, 0.61–0.64x P/S at
  US$25.7–26.8bn) compares with the listed book. Never forward.
- **No deal is blank on both multiples any more.** 36 deals lacked revenue —
  press/filing research filled every one (Baidu, XPeng, Li Auto, Trip.com,
  Autohome, 360 DigiTech, FWD, Hesai, Wuxi Lead, MiniMax, Merdeka…). The 11
  that remain number-less are the true zero-revenue biotechs, and their
  cells now READ "n/m" (loss-maker) and "pre-rev" (the filed P&L has no
  revenue line) — an answer, not a blank. Three research caveats recorded:
  FWD's "revenue" is IFRS-17 insurance revenue (no total-revenue line
  exists); MiniMax's loss is FY2025-basis so FY2025 revenue matches it
  (never mix the prospectus FY2024 revenue with that loss); Merdeka is
  pre-production (its US$0.13m "revenue" is rental income).
- **Pre-revenue is a fact about the revenue line, not a biotech label** —
  the prerev exception now also catches rev < HK$10m (Merdeka-class).
- **Financials are exempt from the NI>revenue wipe**: a PE firm's
  equity-method gains legitimately put NI above total income (Tian Tu
  FY2022: income RMB423m, NI RMB749m → P/E 7.6x, with the why in the note).
- **EKH's offering was WITHDRAWN 2026-07-08** and still showed OFFERING NOW —
  the roster keeps a pulled prospectus forever. `data/batches/withdrawn.json`
  (append-only, needs the HKEX announcement) re-labels such rows via the
  shared pipeline dedupe. Its FY2025 NI was also wrong (HK$81m, not 15).
- **P/S now (live)** joined P/E now in the comp table: BDP PX_TO_SALES_RATIO
  (the desk's own formula, quote-fixed), IFERROR-wrapped, falls back to the
  at-IPO P/S off-terminal. Mnemonic AWAITS first terminal verify.
- **Force-include**: Screener **C17 label / D17 input** (comma-separated
  codes) and the dashboard's "force-include a comp" box pin deals to the top
  of the comps PAST every filter; the gate probe pushes a non-A deal through
  an active A-share filter. Two lessons, both found by double-checking the
  SHIPPED file rather than the source: (1) it was first written to B19 —
  which is the comp table's BAND row — and was silently overwritten, while
  the gate still passed because the test SETS that cell; a control must be
  read back from a rebuilt workbook, and `audit_formulas.CARD_EXPECT` now
  asserts the "Force-include" label so the collision cannot come back.
  (2) JS: a `const` used by a hoisted function must be declared before the
  first render call — the TDZ error killed the whole page once.
- **Strip labels were distorted, not just small**: text inside a
  `preserveAspectRatio:none` SVG stretches with the container. Labels moved
  to HTML (`.saxrow`); the two sticky league header rows now stack at 0 and
  24px with OPAQUE backgrounds (transparent tints let data bleed through).

## v24 (2026-08-26) — the terminal verdict, entitlement issues, A/H drivers

- **The desk ran the Verify (BBG) tab: 79/90 dates and 24/26 actions MATCH.**
  Every non-match decoded: (1) HK tickers must be built WITHOUT leading
  zeros — "0606 HK Equity" is Invalid Security, "606 HK Equity" resolves;
  the Verify tab now strips them. (2) EQY_INIT_PO_SH_PRC and
  EQUITY_OFFERINGS-as-BDP are Invalid Fields — removed; the offer price is
  tied down by the verified day-1 close + day-1 % consistency instead.
  (3) Section A now compares on BLOOMBERG'S basis (raw ÷ cumulative action
  factor) for deals with later corporate actions — BBG's history is
  back-adjusted, ours is the true print; both are right on their own basis.
- **Entitlement issues are a THIRD adjustment class**
  (`data/entitlement_adjustments.json`): rights/open offers never re-scale
  the raw print, but Bloomberg back-adjusts by the TERP factor. Four cases
  reproduced BBG to 4dp from HKEX prospectuses (MTT 2-for-5 rights ×1.2460;
  Howkingtech/MemeStrategy 1-for-2 ×1.22414; Sanergy 1-for-2 pre-
  consolidation ×1.195431; Many Idea open offer ×1.13235 THEN 6-for-1
  rights ×1.09705). CONVENTION: our return columns are simple price returns
  vs offer and EXCLUDE entitlement value — stated per deal in ret_note; the
  factors feed only the Verify tab's BBG-basis comparison. REGO's ×1.1936
  is the same class but the announcement is not yet located (basis-only).
- **WellCell 2477 was a real miss the terminal caught**: its 2026-04-21
  event is a genuine 1→4 SUBDIVISION (raw prints re-scale 27.82 → 6.97)
  that detect_splits rejected because the stock CRASHED the same session
  (close-to-close ≈ ÷5.5, outside tolerance). Lesson: verify a split
  candidate against the ex-date OPEN, not close-to-close, when the day's
  move is violent. Since-IPO corrected −75% → −6%.
- **A/H premium drivers panel** (A/H tab) + the study's conclusions:
  size is the story (corr −0.71 with log mktcap; megas +25% median vs
  mid-caps +109%; CATL/Montage/GigaDevice trade A BELOW H); venue gaps
  collapse when size is held; P/E shows no relationship (+0.08); high
  premiums cluster in domestic-theme subsectors (solar/chemicals/18A ~
  +101–117%) and low in globally-priced ones (consumer electronics +35%,
  F&B +34%). Mechanism (researched, sourced): Southbound fast-entry
  (~10 trading days for top-10% IPOs; ~1 month for A+H names) vs the
  HK$5bn floor that keeps small H-lines out; A-share borrow is dead for
  EVERYONE since the relending shutdown (zeroed 2024-09-30, ~0.7% of the
  margin book in 2026) so borrow does NOT explain the cross-section; A/H
  are non-fungible, so the premium is a segmentation price.
- Explorer gained the greenshoe/no-greenshoe colour mode; the Excel comp
  table now carries a Code column beside Name.

## v25 (2026-09-01) — the A-line fixes market cap, Ingenic lands, three new deals

- **The market-cap complaint was real, and the fix is the A line.** Five deals
  carried NO cap at all (Luxshare, SG Micro, CCTC, Ingenic, PRU) because the
  prospectus parse found neither a share count nor a stated cap, and seven more
  carried a cap derived from a misread offer-% — Anker was published at
  HK$386bn against a true ~HK$58bn. Both classes are now caught by one
  independent yardstick: **the A line's TOTAL share capital × the H offer
  price**. `fetch_ah_snapshot` reads Tencent quote field 45 (总市值) and field 44
  (float cap) for every A/H pair and divides by the A price to recover the
  share count. Field-45 semantics are VERIFIED, not assumed: on ICBC it implies
  356.4bn shares = the full A+H capital, not the 269.6bn A-only float. The
  count already includes the newly issued H shares — on Ingenic it gives
  514,948,196 against the allotment announcement's filed 514,951,667, 0.0007%
  apart.
  - New ladder rung (prio 45, below stated/AAStocks figures, above the
    midpoint estimate), restricted to **2025+ listings** so today's share count
    is never backdated across years of buybacks and placements.
  - New adjudication in pass 2: an existing cap more than **30%** from the
    A-line figure is REPLACED by it, with `mktcap_note` naming the old basis
    and the gap. Result on this run: 45 within 30%, 7 adjudicated (Anker
    386k→58k, Wuxi Lead 275k→77k, Novosense 116k→19k, Eastroc 122k→182k,
    Huaqin 73k→118k, Longcheer 26k→16k, Gon 11k→16k HK$m). P/E and P/S rederive
    off the corrected cap because the adjudication runs BEFORE them.
  - `a_mktcap_now_hkdm` (A-line company cap today, CNY→HKD at the snapshot FX)
    is now a Database column, a comp-table column, a Comps-Lab metric and an
    explorer axis. **This is the "Luxshare isn't that small" answer**: the H
    tranche is HK$24bn, the company is ~HK$490bn at the offer and ~HK$520bn
    today. Effective free float joined the explorer axes at the same time.
  - The AAStocks A/H table lags brand-new H listings by weeks, so the snapshot
    now unions in `ah_map.json` — those codes still get the A-side enrichment
    even before the pair appears in the published table.
  - PRU (2378) was the one non-A/H gap: 2,746,394,249 shares in issue at
    2021-10-04 from Prudential's own Total Voting Rights RNS/SEC 6-K, × HK$143.80
    = HK$394.9bn. **Market cap is now 512/512.**
  - **THE A-LINE COUNT IS A PROXY, NOT A SOURCE — and it is TODAY's count.**
    Verifying the seven adjudications against the filings found three issuers
    that ran a capitalisation issue AFTER listing: Huaqin 10-for-4, Eastroc
    10-for-3, Gon 10-for-4.8. Applying today's share count to the IPO price
    overstates those caps by 30–45%, and for Gon the pre-existing figure had
    been right all along. So the rule is now explicit in code: where a filing
    states the count upon listing, that count wins and the A-line only
    cross-checks; the A-line overrides ONLY an offer-%-derived or
    aggregator-midpoint estimate, which is the class that was actually broken.
    Filed "number of issued Shares upon Listing (before any exercise of the
    Over-allotment Option)" is now in `press_figures.json` for all ten A+H
    names — Luxshare 7,701,730,624 · CCTC 1,987,861,671 · Wuxi Lead
    1,673,821,434 · Huaqin 1,074,280,544 · SG Micro 675,015,824 · Anker
    582,909,162 · Eastroc 560,902,900 · Longcheer 522,590,644 · Ingenic
    514,951,667 · Gon 301,250,000 — each with its announcement URL. Where the
    proxy is still the only figure, `mktcap_note` says so and names the risk.
  - Convention confirmed, not changed: the book's cap is **all share classes ×
    the H offer price**, which is the multiple an H buyer actually pays. The
    prospectus "Global Offering Statistics" figure is a MIXED basis (A shares
    at a 5-day average A price, H at the offer), so the two legitimately differ
    — Luxshare HK$487bn ours vs HK$590,584m stated. Both are recorded.
- **Ingenic (3223) moved from placeholder to filed fact**, all from the HKEX
  allotment announcement (2026082401907.pdf) and prospectus (2026081700003.pdf):
  final price **HK$100.00** (the HK$102.80 in the roster was the CAP — priced
  below it), 31,287,300 H shares, gross HK$3,128.7m / net HK$3,054.6m, public
  **927.37×** on 141,851 applications, international **8.43×**, no clawback
  (10/90 held), cornerstones US$191.65m = 15,034,000 shares = **48.05%** of the
  offer locked to 2027-02-24, greenshoe 4,693,000 (15%) fully over-allocated
  with **no exercise announced** as of 2026-08-31 (stabilisation to 09-19,
  Guotai Junan), one-lot ballot 0.27%. Classified Tech/AI · AI chips & semis
  (fabless memory ~61% of FY25 revenue, computing 27%, analog 11%; automotive
  33.5%). Cap HK$51,495m; P/E 124.4× and P/S 9.9× trailing.
  `press_figures` now also carries `shares_outstanding`, `offer_shares`,
  `overallot_shares` and both subscription multiples — filing-verified
  structure, still below the Bloomberg desk paste (prio 95) for subs.
- **`audit_fresh` was wrong about flat debuts.** It failed any day-1 of exactly
  0.00%, but Ingenic really did open AND close at HK$100.00 on 2026-08-25 — on
  5.8m shares with a 100.40/97.10 range. A moving bar is a real session; the
  placeholder shape is a row with no listing-day bar behind it at all. The gate
  now tests for the bar, not the zero, and reads CLEAN.
- **The deal-size parser was reading the GREENSHOE's sentence.** Chasing the
  cap complaint turned up a second defect underneath it. An allotment
  announcement states "net proceeds ... HK$X million" three different ways —
  the deal itself ("are estimated to be approximately HK$24,113 million"), the
  over-allotment option ("**additional** net proceeds of approximately
  HK$3,632 million") and each use-of-proceeds bucket ("approximately 55% of
  the net proceeds, or approximately HK$13,262 million"). The old regex took
  whichever came first in the file **and** capped its search at 300 characters,
  which is shorter than the base sentence actually runs. JD Logistics was
  therefore published as a **HK$3,632m** deal against a real **HK$24,113m**.
  `parse_proceeds()` now ranks candidates instead of taking the first: the
  greenshoe and bucket sentences are rejected outright, an explicit "estimated
  to be" statement outranks a bare mention, and a document with only buckets
  can have its total recovered when two or more agree within 2%. Verified
  against four hand-read filings (JD Logistics 24,113 · Leapmotor 6,057.4 ·
  Tuhu 1,081.5 · Weibo 1,383.4). Deal size feeds effective free float AND the
  offer-% market-cap rung, so this was a cap error too.
  - Applied by `_model_scripts/patch_proceeds.py`, which re-parses ONLY the
    proceeds fields from `scrape/text_cache` (full document text, better than
    the 12-page window the original parse read). A full
    `extract_prospectus.py allotments` re-run re-reads 522 PDFs and times out
    past 900s; every other field in that batch was already correct.
  - Anchor-then-window, not one big regex: running a value pattern over a whole
    60KB announcement backtracks for ~2 seconds per deal because the documents
    are dense with digit-and-comma runs. Match the cheap literal first, then
    scan a 600-character window.
- **Stabilising manager extracted, and its own league tab** (`SM League` in
  Excel, `Stabilisers` in the HTML). Every allotment announcement carries the
  same cover sentence — "In connection with the Global Offering, *Guotai Junan
  Securities (Hong Kong) Limited* as stabilizing manager (the 'Stabilizing
  Manager')" — so `ipo_lib/extract_stabmgr.py` reads the name from the local
  text cache; nothing is inferred from the sponsor, and a deal with no
  over-allotment option correctly has none (its `shoe_note` already says so).
  Names are grouped by BANK FAMILY, so "Goldman Sachs (Asia) L.L.C." and
  "Goldman Sachs International" are one row.
  - The league is the exact mirror of CS League — same columns, same
    with-pop/ex-pop split, same shared aggregation (`clean_names.stab_league`
    beside `cs_league`) so Excel and HTML cannot disagree — **plus two columns
    only stabilisation has: shoe full % and shoe lapsed %**. That is the
    reading: a shoe exercised in full means the price never needed support;
    a lapsed shoe means the manager was buying stock back to hold the line.
  - Read it AGAINST the cornerstone league. One says who anchored the deal,
    the other who defended it — the same bank often does neither well at both.
- **Three deals added to the pipeline, each from its own prospectus:**
  - **Longsys 9976** (深圳市江波龍, A-line 301308.SZ) — maximum-price structure,
    no floor: "no more than HK$240.60". 26,077,800 H shares, gross max
    HK$6,274m, cap **HK$204,633.5m** as the prospectus itself states it (A shares
    at the 5-day RMB399.18 average). 15 cornerstones ~US$151.1m = 18.89% of the
    offer; greenshoe 15% PLUS a separate 15% offer-size adjustment option;
    stabilisation to 2026-10-03. FY2025 revenue RMB22.77bn, profit RMB1.50bn —
    but H1-2026 revenue RMB24.09bn and profit RMB10.72bn against RMB41.0m,
    i.e. the memory upcycle has already made the trailing multiple meaningless.
    Max price sits ~45% below the A line. Closes 09-03, lists 09-08.
  - **Excelland Robotics 3231** (優地機器人, brand Uditech) — **Chapter 18C**
    commercial company, HK$14.45–19.55, 45m shares, HK$650–880m gross, cap
    HK$6,016–8,140m on 416,368,421 shares. Cornerstones only **US$3m** total
    (SensePower/SenseTime US$2m + CYGG US$1m ≈ 3.1% of the offer, both close
    associates of existing holders); **no greenshoe and no stabilising manager**
    — the same structure the desk flagged on Medcaptain. FY2025 revenue
    RMB317.7m (+18.9%), loss RMB110.8m; 3M-2026 loss widened ~20% y/y. Sole
    sponsor is a boutique (Silver Nile). No P/E — loss-maker; P/S 17.2–23.3×.
    Closes 09-04, lists 09-09.
  - **Medcaptain 2041** was already loaded in v24's pass; unchanged.
  - EKH 2523 finally carries a sector (Industrials · Logistics) and its status
    reads WITHDRAWN rather than the roster's stale "OFFERING NOW".

## Data-quality rules that now run automatically

- **Cover-page bleed is scrubbed from every party list** (`clean_names.
  clean_party_element/_list`, applied in merge to `sponsors`, `sponsors_en`,
  `underwriters_en`, `bookrunners`, both display strings, and — via
  `clean_investor` — cornerstone cells). The five classes, all observed in the
  book (109 deals): the section heading "DIRECTORS AND PARTIES INVOLVED IN THE
  GLOBAL OFFERING/SHARE OFFER" with page-number fragments ("– 176 –", "–1 1 0–",
  en/em/minus dashes); role labels glued to the next name ("Managers CLSA
  Limited", "Sole Representative : …", "Sponsor-Overall Coor dinators …",
  "Joint Bookrunner, Capital Market Intermediary …"); the issuer's US address
  ("New York, NY 10179 United States of America UBS AG …"); footnote pointers
  ("Please refer to Note (1). No" — CAOCAO's whole cornerstone list was two of
  these); orphaned suffix halves ("Securities Limited" alone). Lesson that cost
  a debugging loop: **strip junk punctuation BEFORE each ^-anchored role pass**
  — "-Overall Coordinator X" hid the label behind a leading hyphen, so the
  strip ran but removed only the hyphen. Test any new pattern against the
  legit-name regression list in the unit block (The Hongkong and Shanghai
  Banking…, CMB International Capital…).
- **press_figures.json now also carries `cornerstone_investors` +
  `cornerstone_pct`** (prio 70, xchecked); the AAStocks cornerstone fill SKIPS
  deals whose provenance is press — hand research is never overwritten.
  CAOCAO 2643 is the precedent: the PDF allotment parse read footnote refs as
  names and 23%, press says six cornerstones (Mercedes-Benz Mobility, Mirae,
  Infini, Gotion, EVE, RoboSense), HK$951.6m = 22.6424m of 44.1786m offer
  shares = 51.3%.
- **Cornerstone spellings are canonicalised book-wide.** The same investor arrives
  from three sources with different spellings ("GIC Private Li" vs "GIC Private
  Limited", ALL-CAPS forms, "A及B" in one cell, footnote markers). merge collapses
  them to the most-filed full spelling; different vehicles of one house (CPE
  Investment XVI vs CPE Redwood) stay separate on purpose. Raw lists survive as
  `cornerstone_investors_raw` for audit.
- **Price vs range**: a struck price ABOVE the recorded cap means the CAP parse is
  wrong — the cap is flagged and % -of-cap withdrawn (SAIMO). A price BELOW the
  indicative low is legal in HK (Downward Offer Price Adjustment) and is annotated,
  not flagged (Global New Material).
- **Every column is a value or a stated reason.** merge writes *_note fields for
  each remaining blank; the Database's "Why anything is blank" column shows them.
- `price_asof` dates the since-IPO column (prices refresh weekly, so the number is
  never more than a few sessions old — this was the only "mismatch" left in the
  independent audit).
- **Financial plausibility gate (v11).** merge refuses to publish a multiple it
  cannot believe. Two internal checks, no thresholds pulled from the air:
  net income above revenue means the extracted PAIR is inconsistent, so both
  figures and both multiples are withheld; a derived P/E or P/S above 300x means
  the denominator is wrong, so the multiple goes and the suspect figure with it.
  A pre-revenue 18A issuer is the exception — its tiny revenue is real, so the
  revenue stands and only the meaningless P/S is withheld as `n/m`. Every case
  writes its own reason into `fin_check` / `pe_note` / `ps_note`, which surface in
  the Database's "Why anything is blank" column. This removed 92 impossible
  multiples (Li Auto read 307,800x P/S, Zijin Gold 39,145x P/E).
- **Three extraction bugs the gate exposed, now fixed at source:**
  a *year header row* under a "Revenue" label was being read as money
  (`[2017, 2018, 2019]`); a *narrative sentence* mentioning revenue was matched
  before the summary table, yielding page numbers and dates; and a table printed
  "(RMB in millions)" was divided by 1,000 again on the thousands assumption.
  `series_from` now scans every label occurrence instead of only the first,
  rejects year-shaped series, and reads the unit from the row's own header.
- **Cornerstone % must come from a cornerstone sentence.** "representing
  approximately X% of the Offer Shares" is also how the prospectus states the HK
  public-offer CLAWBACK, and that sentence can fall inside the cornerstone
  window — Sanhua's cornerstone tranche read 10.0% when 10.0% was the retail
  reallocation. A match is now accepted only when its own sentence mentions the
  Cornerstone Investors and is not a reallocation clause, and block selection
  weights the "aggregate amount of approximately US$Xm" sentence 100x (it is the
  one unambiguous marker of the real section). Sanhua now reads US$562.0m →
  47% of the deal, matching the filing and the press.
- **A NaN is never a number.** yfinance's newest row can be a stub with a NaN
  close before the session settles; that wrote NaN straight through to since-IPO
  and its alpha for 14 deals and rendered as "NaN%" in the dashboard. Prices now
  mark to the last bar that actually printed, and `bench_return` returns None
  rather than a non-finite reading.
- **Risk and tax boilerplate is not a business description.** "We are a PRC
  enterprise and we are subject to PRC tax…" and "We are a company incorporated
  under the laws of…" match the business-description patterns but describe no
  business; `RISKY` now rejects them, and offering-window deals are classified
  into the taxonomy instead of showing "sector not yet classified".

## Benchmarks and weights — measured, not assumed

- Materials/Energy was benchmarked against the Hang Seng UTILITIES sub-index, which
  holds power/gas distributors only. Miners, chemicals and energy producers sit in
  Commerce & Industry under the index's own methodology — corrected to ^HSNC.
- A pair test over 24,090 deal pairs asked which factors identify deals with SIMILAR
  day-1 outcomes: both-A+H +49%, subscription-within-2x +32%, same sector +4%, while
  subsector / size / P/E / cornerstone were no better than random. Subsector-first
  therefore stays as the VALUATION comparability gate (the user's design), and a
  "demand-similar first" rank mode was added for the outcome question. The numbers
  are printed on the Notes tab so the weights can be re-argued from evidence.

## v26 (2026-09-02) — SHEIN and Mech-Mind land, and four pipeline holes they exposed

Two listings on 2026-09-01 took the book from 512 to 514. Both were already in
the Pipeline tab, so graduating them exercised the whole path from roster to
deliverable — and it found four defects that would have bitten the desk on
every future listing, not just these two.

- **SHEIN (0625, SHEIN-W)** — final price **HK$48.56** against a HK$47.60–49.50
  range, so priced 1.9% below the cap and a shade above the mid. 279,992,500
  Class B shares, 100% primary, gross **HK$13,596.4m** / net HK$13,214.1m
  (279,992,500 × 48.56 = 13,596,437,800 — the identity holds to the dollar).
  Public tranche **5.63x** on 35,751 valid applications, international 2.59x on
  106 placees; below the 15x trigger, so **no clawback** and the split held at
  10/90. Seven cornerstones for US$383.0m = 22.1% of the offer but only 1.5% of
  issued capital. Greenshoe 41,998,500 (15.0%) **fully over-allocated**,
  stabilising manager Goldman Sachs (Asia) L.L.C. to 2026-09-26. Shares upon
  Listing 4,246,202,609 (Class A + B) × HK$48.56 = **HK$206.2bn** on the book's
  convention. Day 1: opened exactly at the offer, traded to HK$43.72 (**−10.0%**)
  and closed HK$48.50 — one tick under issue, inside a live stabilisation
  mandate. WVR regime from the short-name suffix, hand sector kept (Tech/AI ·
  internet platform) over the filing's Consumer/Apparel industry string.
- **Mech-Mind Robotics (9615)** — final price **HK$101.70**, which is the CAP of
  the HK$95.30–101.70 range. 23,140,590 H shares, gross **HK$2,353.4m** / net
  HK$2,200.2m. Public **3,835.36x** on 252,461 applications against international
  13.39x — **clawback triggered**, 3,471,090 shares reallocated, final split
  20/80 (from 5/95). Note the two nearly identical figures in that filing are
  genuinely different mechanics and neither is a typo: over-allocation is
  **3,471,060** shares, the clawback reallocation is **3,471,090**. Cornerstones
  US$186.0m = 62.02% of the offer. Greenshoe fully over-allocated, stabilising
  manager CLSA Limited. 125,011,050 shares upon Listing × HK$101.70 =
  **HK$12,713.6m**, which matches the prospectus's own stated expected cap
  exactly. Day 1 opened at the offer, low HK$97.00 (−4.6%), closed HK$99.80
  (**−1.87%**). One-lot ballot 3.00%.

**The four defects, all now fixed in the pipeline rather than by hand:**

1. **`patch_proceeds` and `patch_offer_shares` were one-off scripts, so the next
   plain `refresh` would have silently undone them.** They live in `ipo_lib/`
   now and run as the `patch-proceeds` / `patch-offer-shares` stages in BOTH
   `ipo.py` and the desk bundle, after every other writer of
   `extracted_allotments.json`. They re-read the FULL cached announcement text
   where `parse-allot` sees only the first 12 pages, and they never blank a
   value they cannot better. Leaving them outside the pipeline was worth 165
   corrected proceeds figures and 262 re-read share counts — i.e. the whole of
   the v25 deal-size repair, one refresh away from vanishing.
2. **Prices ran BEFORE the merge, so a brand-new listing was unpriced until the
   NEXT refresh.** `fetch_prices`, `fetch_h_paths` and `fetch_ah_paths` all take
   their code list from `deals.json`, which a listing parsed in the same run has
   not yet reached. A new `merge-pre-prices` stage sits ahead of them and the
   existing merge folds the prices back in. Without it SHEIN and Mech-Mind would
   have entered the book with no day-1 return at all, and the fix is general:
   every future listing now prices on its first refresh.
3. **The stabilising-manager regex could not span a name containing periods —
   and that quietly deleted the two biggest stabilisers from the v25 league.**
   The cover-sentence pattern used a `[^.;]` name class, which stops dead at the
   first dot, so a name like "Goldman Sachs (Asia) L.L.C." never reached the
   ", as the stabilizing manager" anchor. SHEIN was how it surfaced — unnamed
   against a filing that names one plainly — but SHEIN was 1 of **43**. Measured
   against the cached text of all 524 announcements, the widened pattern newly
   names:
   - **Goldman Sachs — 27 deals**, previously absent from the league ENTIRELY
   - **J.P. Morgan — 10 deals**, likewise entirely absent
   - Shenwan Hongyuan 5, China Galaxy 1
   Coverage goes 265 → **308 of 524 (58.8%)**. The v25 SM League therefore
   ranked HK stabilisers with Goldman and J.P. Morgan missing from the sample,
   which is enough to move any league conclusion drawn off it — treat the v25
   stabiliser read as superseded, not merely extended.
   The rule: a dot is kept when it is an abbreviation dot and dropped when it
   ends a sentence, on two signals — not followed by whitespace-then-capital, or
   straight after a lone initial. That second signal is exactly what "J.P.
   Morgan" needs, since its `P.` IS followed by " Morgan"; the naive fix would
   have fixed SHEIN while still losing all ten J.P. Morgan deals.
   Sentence-boundary safety is preserved, so the match can still never run
   backwards into a previous sentence.

4. **A brand-new code loses a race with itself, and its whole prospectus goes
   unparsed.** `fetch_newlistings` downloads the prospectus the day it posts
   (as `newlist_<code>_*.pdf`), while the roster-driven per-stock search in
   `fetch_hkex_filings prospectus` still cannot resolve a code that new and
   returns nothing — so the manifest carries no parts for a document already
   sitting in `scrape/pdf_cache/`. SHEIN was parsed from its allotment
   announcement but NOT from its prospectus for exactly this reason.
   **The tell was a false explanation, not a blank.** With no prospectus text,
   the merge labels missing sponsors *"sponsor not stated in the extractable
   filing text"* — which for SHEIN was untrue: Goldman Sachs (Asia) L.L.C.,
   Morgan Stanley Asia Limited and J.P. Morgan Securities (Far East) Limited
   are all in the document, in a file we had already downloaded. An explained
   blank is only worth anything if the explanation is true.
   Fixed in `fetch_hkex_filings.attach_cached_newlist()` — the MANIFEST
   builder — rather than in any one parser, because `extract_prospectus`,
   `extract_deep` (sponsors, bookrunners) and `extract_profiles` all read that
   single manifest and all skip a deal with no parts; fixing it once upstream
   fixes all three. It indexes the cache in one pass (globbing per deal over a
   3,300-file directory is ~200k stat calls for nothing) and prints what it
   recovered. Today: 468 → **469** deals with prospectus parts, the one
   recovery being SHEIN. The other 55 partless entries have no cached
   prospectus at all — the long-standing, genuinely explained "body never filed
   as one document" absence — but this is the race EVERY new listing hits, so
   it now self-heals.
   Note the AAStocks per-deal page lags a listing by weeks (both new codes came
   back null for sponsors, underwriters and cap), so for a fresh deal the
   prospectus is not a nice-to-have second source — it is the ONLY source.

**Two traps in these debut numbers, both worth knowing before anyone updates a
figure by hand.**

1. *Field order.* The Tencent kline row is `[date, OPEN, CLOSE, high, low,
   volume]` — open before close, the opposite of most feeds; the Sina HK quote
   is different again (`open, prevclose, high, low, last`). `fetch_prices.py`
   reads Tencent correctly (`row[2]` is the close). Both these deals opened at
   exactly their offer price, so a transposed read turns two deals that BROKE
   ISSUE into two that closed flat. A debut reporting a day-1 return of exactly
   0.00% is the signature of this mistake — check the field order before
   believing it.
2. *Press headlines are intraday, not closes.* SHEIN's debut was reported as a
   "10% plunge" (CNBC, The National) and simultaneously as "ends flat" (Forbes,
   The Information). Both are true of different moments: it traded to HK$43.72
   (−10.0%) early and closed HK$48.50 (−0.12%). Never lift a day-1 return from a
   headline written during the session.

Both closes were verified against six independent feeds — Tencent, Sina and
Eastmoney on the Chinese side, CNBC (exchange-sourced), Investing.com and
stockanalysis.com on the Western side — agreeing to the cent on OHLC and to the
share on volume, with Reuters stating the HK$48.50 close in prose. HKEX's own
Daily Quotations Sheet could not be retrieved (URL relocated), so the primary
exchange document is NOT among those six; if the desk wants one, that is the
gap to close on the terminal.

## v26.1 (2026-09-02) — the desk's read-through: stabilisers, floats, multiples

**A greenshoe implies a stabilising manager.** That is the desk's rule and it is
right: someone holds the option. Reading only the allotment announcement left
**110 deals with a greenshoe and no manager**, and Innolight (3308) is the proof
the announcement is not always enough — its allotment filing does not contain the
string "stabilis"/"stabiliz" ANYWHERE, while its prospectus glossary says plainly:

    "Stabilizing Manager"   Goldman Sachs (Asia) L.L.C.

So `extract_stabmgr` is now two passes. Pass 1 is the allotment announcement
(post-pricing, authoritative). Pass 2, only for deals pass 1 could not name,
reads the PROSPECTUS — the definitions glossary first, then the cover sentence
and parties table. The glossary is a flattened two-column term/definition list,
so the name runs from the closing quote of the term to the next opening quote;
curly quotes are what the PDF text actually carries. `src` records which
document and which pattern produced every name, so nothing is ever inferred
from the sponsor. Pass 2 reads whole parts rather than a head window (the
glossary sits deep in the definitions section) but skips any part whose text
does not contain "tabili" at all, which keeps that from costing anything.

One artefact worth knowing: PDF extraction splits a word after its first letter
often enough to matter — Yuen Meta came out `Y uen Meta` and keyed as `Y uen`.
A lone capital followed by a LOWERCASE continuation is always that artefact, so
`tidy()` rejoins it; a real initial is followed by a capital ("J P Morgan"), so
this cannot glue two genuine tokens together.

**Stabilisation notices were being dropped on their title.** The fetcher required
"stabilis|stabiliz|over-allot|lapse" in the TITLE, but Ingenic filed its notice as
plain `GLOBAL OFFERING OF INGENIC ...` — no stabilisation word at all — so it was
never opened and the deal carried no hyperlink. Three changes: the title match now
also accepts "global offering"/"share offer"/"over-alloc" (safe, because the search
window is already 15–75 days after the allotment announcement, where such a filing
is the stabilisation notice in practice); candidates are ranked so an explicit
stabilisation title is still tried first, and four are examined rather than two;
and, most importantly, **the notice's hyperlink is now recorded whenever the
document is genuinely about stabilisation, even when the outcome wording is one
the regexes cannot classify**. Withholding the link because the parse was
inconclusive left 74 deals that HAVE a greenshoe with nothing to click; the
outcome itself is still left blank rather than guessed, with a note saying so.

**The stabiliser league gained the day-1 session, which is the thing it should
have measured all along.** New columns, in Excel and HTML off the same shared
aggregation: `open vs issue` (the pop — where the stock opened against the price
the bank sold it at), `close vs issue` (the day-1 return), and `open→close`
(whether that open was HELD or given back). A negative open→close beside a
positive close is a bank that spent the session supporting a fading stock, which
a single "day-1 pop" number hides completely. On the current book CLSA opens
+46.5% and closes +40.9%, while China Securities opens +22.1% and *adds* to
+35.1%.

**Effective free float, three ways off one identity.** The formula was already
`deal size × (1 − cornerstone %)` — cornerstone % is a share OF THE OFFER, which
is what makes the subtraction valid — but it was only ever published as a
percentage of market cap, so the absolute number the desk actually wanted was
nowhere. Now `eff_free_float_hkdm` (money) and `eff_free_float_shares` (offer
shares × the same factor) sit beside `eff_free_float_pct`. The absolute pair
needs no market cap, so they survive the two rows whose cap is not derivable.
Not modelled: an over-allocated greenshoe puts MORE stock in the market on day 1
than the offer alone — the stabiliser is short it — so on a fully over-allocated
deal the true day-1 tradeable float is larger than this figure.

**Two P/E columns, and which one to trust.** They are both right on different
bases. `P/E at IPO` is ours — final market cap ÷ the last PRE-IPO fiscal-year net
income from the prospectus — computed identically for every row, with both inputs
visible as columns beside it. `P/E at IPO (BBG)` is Bloomberg's — price ÷
trailing-12m EPS at listing. They diverge most on 2021-23 vintages (median
BBG/ours ≈0.5) because earnings grew between the covered FY and listing and
Bloomberg uses weighted pre-deal shares. **Use ours to rank deals against each
other** (only one basis, and auditable); **use Bloomberg's when quoting a number
someone will check on a terminal.** The book already treats Bloomberg as referee:
where our multiple breaks the plausibility cap, a BBG print within 25% restores
it as real (CALB at ~549x), and agreement at an absurd level is read as a shared
artifact rather than a confirmation. This is now stated in the workbook's own
notes, not just here.

**Also added:** `P/S today (BBG)` in the Database FUNDAMENTALS band — no public
source exists for a live multiple, so every row resolves off BBG Verify col S on
the terminal and says "run on terminal" off it; `A-share mkt cap now (BBG)` as
BBG Verify col T (CUR_MKT_CAP on the A ticker), which the scraped A-line cap
column now falls back to wherever the Tencent snapshot had no figure; and the
Screener's `P/E now` / `P/S now` moved INTO the FUNDAMENTALS band next to
`P/E at IPO`, instead of being stranded beside Match/Score where they read as
scoring inputs.

**A self-inflicted lesson.** The prospectus-rescue in v26 appended a docs entry
with `file_link: None`, and the merge builds the Database hyperlink by
concatenating that onto the hkexnews host — so the whole 514-deal merge died with
`TypeError: can only concatenate str (not "NoneType") to str`, twice, silently,
while every expensive parse stage around it succeeded. Two fixes: the rescue now
takes the real path from the offering-window record (so the manifest is truthful
and SHEIN gets a working prospectus link), and the merge picks the first doc that
actually HAS a link rather than assuming `docs[0]` carries one. **Never append a
document record without its link.**

Market cap is **512/514**, not the 512/512 v25 claimed: Sipai Health (0314) and
Jinxun Resource (3636) have no share count, no offer-% of capital and no
published listing cap in any source, AAStocks included. Both say so in
`mktcap_note` rather than carrying a number.

## v26.2 (2026-09-02) — the full-book audit: every number re-derived, every reason visible

The instruction was "check everything — returns with corporate actions, market
cap, P/E, P/S, every field, every visual — spend as much time as possible".
This section records what was checked, what was found, and what changed.

**Returns, verified against the exchange's own prints.** The method: pull the
raw Tencent day-kline (unadjusted, as-traded) for a deal, index its sessions
locally, apply the DOCUMENTED corporate-action factors from
`data/auto_splits.json` / `entitlement_adjustments.json`, and rebuild
day-1/1w/1m/3m against the offer price — then diff the book. Results:

- 12 random non-split deals: **exact to the digit on every elapsed horizon**.
- 6 split-affected deals (Hesai, Nuobikan, Zhida, Nanhua, Gon, Huaqin):
  **day-1 and 1m exact**; the "since" differences were the live session.
- 4 deals where tonight's prices batch disagreed with the book (Morimatsu,
  YZYBIO, UJU, New Media Lab): the raw prints sided with the BOOK on three and
  with the batch on one — see the open0 fix below. Root cause of the batch
  side: **Yahoo permanently lacks the debut bar** for 2155 (starts 06-29,
  listed 06-28) and 2496 (starts 09-26, listed 09-25), so any Yahoo-based read
  calls day 2 the debut. The book is immune BY DESIGN: the merge re-measures
  every return on the local session list at priority 55, which beats the batch.
- 8 audit flags with no prior explanation (1497, 2129, 2185, 2252, 2431, 6090,
  6628, 9676): raw prints say **8/8 the book is right** — the auditor's Yahoo
  side mis-aligned sessions.

`audit_returns.py` itself ran under heavy Yahoo throttling and produced a
polluted table (2635's 3m "mismatch" is exactly the ×10 split factor its
throttled split-row fetch missed). No deliverable consumes that JSON — its
docstring's Verification-tab claim is outdated — but do not trust a run of it
made while Yahoo is limiting; the tell is hundreds of "since" flags at once.

**One real returns bug found and fixed: the day-1 OPEN of a postponed listing.**
h_paths cached "complete" records keyed on fetch-time listing dates, so New
Media Lab (1284) — typhoon-postponed from 2023-07-17 to 07-18 — kept the
exchange placeholder's open (0.92, the offer echoed back) frozen forever and
printed a day-1 open pop of exactly 0.0% against a real open of 0.88 (−4.35%).
Fixes: the h-paths cache invalidates when its stored listing date no longer
matches the book's; and the merge only trusts `open0` when the record's anchor
matches, otherwise it drops the open legs with the reason in `day1_oc_note`.
1284 now prints −4.35%. A debut open pop of exactly 0.00% remains the
signature of this class — Ingenic's genuine 0.0% day-1 CLOSE (open 100.00,
close 100.00, low 97.10, offer HK$100.00 — pinned at issue by the stabiliser)
was verified against the raw bar before being believed.

**Market cap / P/E / P/S: identities re-derived for the whole book, all clean.**
gross≥net (221 rows), shares×price=size where the basis says so (268),
price×shares-upon-listing=cap where the basis says so (175), P/E=cap/NI on
every derived row (284), P/S=cap/rev (480), the free-float trio (502),
since-IPO vs last close (514), A-premium convention (61), ranges and
structure (514). Zero failures. Comparability: P/S is single-basis 480/480;
P/E is single-basis on 284 rows plus 8 documented Bloomberg gap-fills — rows
where no FY NI or no cap exists — each carrying its basis in `pe_note` and its
provenance, with the same value visible in the `P/E at IPO (BBG)` column. That
v12 design stands: an explained basis-borrow on 8 rows beats 8 blanks.

**The syndicate lists were shipping office addresses glued to bank names.**
The Parties-Involved parse carried the previous entry's address tail onto the
next name — 192 rows like "Central, Hong Kong CLSA Limited" (originally
counted 171; the tighter counting found more). Fixed in
`clean_names.clean_party_element` (one choke point, so leagues, display
strings and raw lists all heal), anchored on the literal ", Hong Kong "
marker with head-must-look-like-an-address and tail-must-look-like-a-company
tests, because two REAL names had to survive: "Central China International
Capital Limited" (a genuine house) and "Deutsche Bank AG, Hong Kong Branch"
(a genuine suffix). The last holdout was "uSmart Securities" — a lowercase
brand — so the tail test accepts camel-case starts. Residual count: **0**.

**Stabilising managers, round three.** Two more filing shapes surfaced:
"NAME has been appointed as the Stabilising Manager" (Conant Optical names
Guotai Junan ONLY that way) and the filed absence "No stabilizing manager
will be appointed" (USAS Building, WITH a greenshoe — the desk's
greenshoe⇒manager rule has real, filed exceptions). Both parse now; a filed
absence is recorded as `stabilizing_manager_none` and its note states the
fact rather than an extraction shrug.

**Suspensions say so.** Many Idea Cloud (6696) last traded 2026-03-30; its
since-IPO print sat five months old with nothing explaining why. A price
frozen >30 days now writes `price_note` ("suspended or delisted; measured to
the final traded session").

**Every reason is now visible.** A sweep of `*_note` fields the merge writes
vs the workbook's NOTE_FIELDS found five that never rendered — `price_note`
itself, `eff_ff_note`, `eff_ff_shares_note`, `ipo_date_note` (the typhoon
note!), `stabilization_note` — "a blank with an unread reason is
indistinguishable from an unexplained blank". All render now.

**Freshness is a policy, not an accident.** 438 rows carry the Friday 08-28
close (inside the designed 7-day cache tolerance), 73 the Monday 08-31 close,
young listings are refetched on a 2-day leash, and `price_asof` states the
date on every row.

**Operational: this volume intermittently fails reads with TimeoutError
[Errno 60].** It killed one extraction run and one visual-gate run tonight —
the signature of Desktop-folder cloud eviction faulting files back in. A file
read once stays local, so every long stage now runs with up-to-3 retries
(`run_v26_final_chain.sh` pattern). If a stage dies mid-write with a timeout,
re-run it; the batches are regenerated whole, so a retry is always safe.

## THE WEEKLY EMAIL (v26.3) — one command, Monday morning

```
python ipo_lib/make_weekly_email.py            # 2-week lookback (default)
python ipo_lib/make_weekly_email.py --weeks 1  # last week only
```

Writes `out/weekly_ipo_email.html` and `.txt`. Open the HTML in a browser,
select-all, copy, paste into Outlook — the styling is inline, so it survives
the paste. The text version is there for anyone who prefers plain mail.

**Two sections, in the order the desk reads them.** *Coming up* is every deal
in its offering window or listing within ten days: terms, cornerstone %,
book-close and listing dates, then the line saying your notes are attached.
*Listed in the last N weeks* is one block per debut: the book (public/instl),
the day-1 open AND close, where it stands now against the offer, and the shoe.

**The shoe line is the point of the whole thing.** For a live deal it prints
who runs it and the filing's own stated expiry with a countdown — "Goldman
Sachs runs the shoe — support can run until Sat 26 Sep (22d left)". Once the
notice lands it prints the outcome instead (exercised in full = the price
never needed support; lapsed = stock was bought back to hold the line). That
date now comes from `stabilization_end_date`, parsed out of the allotment
announcement in three real-world shapes: "26 September 2026, being the 30th
day after…", the US order ("September 26, 2026" — Mech-Mind), and the
trailing parenthetical ("(which is Saturday, September 19, 2026)" — Ingenic;
SHEIN writes "which is expected to be"). Never inferred as listing+30.

**Colour is hand-written, never generated.** `data/weekly_email_notes.json`
holds one or two sentences per stock code; the generator prints them under
that deal and invents nothing. A code with no entry simply shows its numbers.
Append to it as you form views — that file IS the analyst layer of the email,
and it is what stops the note reading like a machine wrote it.

Sector falls back to the filing's own industry string for applicants the
taxonomy has not classified yet (Longsys listed as "Semiconductors &
Semiconductor Equipment"), because an empty sector cell in a client-facing
note reads as a mistake rather than as an absence.

**`stabilization_end_date` is a first-class column now** — "Shoe ends (filed)"
in the Database and the dashboard's deal brief, not just a line in the email.
Coverage went 32 → **276 of 514** once the parser learned all three shapes;
the jump is the point, because the date is not derivable any other way. Do NOT
be tempted to compute it as listing + 30: the anchor is the last day for
LODGING APPLICATIONS, not the listing, so the true gap runs 17–45 days. Six
deals sit outside the usual 20–50 day band and every one was checked against
its filing — e.g. 1440 says "expire on Saturday, 30 January 2021" for a
13 January listing, exactly 17 days. Parsed, not guessed.

Blank expiry maps to `shoe_note`, which now also covers the case the gate
caught: a deal whose over-allotment outcome is ALREADY published but whose
announcement never spelled the expiry out — the date is moot once resolved,
and the note says so rather than leaving an unexplained hole.

## File map (what to never delete)

- `data/deals.json` — canonical output (regenerated by merge; safe to rebuild)
- `data/batches/*.json` — SOURCE-OF-TRUTH caches; deleting one forces a slow
  refetch, deleting `stabilization.json`/`aastocks_deal.json` costs ~an hour
- `scrape/text_cache/`, `scrape/pdf_cache/` — parsed filings; large but cheap
  insurance, keep
- `ipo_lib/classify.py` GROUPS + `fetch_phip.py` PIPELINE_LABELS — the analyst
  judgment layers; only ever extend
- `TO_NOMURA/` — regenerated by `ipo.py export`, never edited by hand
