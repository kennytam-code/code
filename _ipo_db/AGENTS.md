# HK IPO project instructions

Read `START_HERE.md` before changing this project. It is the current handover;
`MAINTENANCE.md` is a historical log whose older instructions may be superseded.
Read `data/release_state.json` for the latest delivered counts, dates and limits.

The user is a Nomura sales/trading analyst. Keep the desk views compact, elegant,
clear and usable. Latest feedback rejects brick red and large red blocks on
Screener; use the official signature-graphic red as an accent with grey/white.
Remove large per-tab title rows. Preserve useful
section colours and red/green performance changes. Remove
generic footnotes from visible Excel/HTML views; no Notes sheet in the final workbook. Preserve the eleven W_* inputs on the hidden calculation sheet. Keep methods and review notes
in this repository, not in extra workbook tabs. Formatting never changes data.

HTML A/H and Lock-up comparison lines must obey the active sector/subsector/search
scope. Stocks, Selected average and Sector averages are separate views. No
stock-plus-average overlay; at most six lines per page, with complete legends.
Lock-up is a historical study only: source-confirmed cornerstone dates and
completed ±30-session return endpoints. Use historical_lockups.historical_events;
do not restore unconfirmed/future rows or derive an exact date from a generic
six-month phrase. Primary review: data/lockup_date_review.json. Never allow an
allocation roster heading to absorb a subsequent controller lock-up table.

Use one heavy operation at a time. Python: 512 MiB; Node: 384 MiB. Never increase
these limits to rescue a failed build. Use the staged native build and bounded
Artifact projections. Preserve unrelated files, user work and Word studies.

Do not state that Bloomberg has been tested live without a real terminal run.
Do not invent missing prices, subscription figures, expiry dates or valuations.
An internal arithmetic pass is not independent primary-source verification.
Use exact legal cornerstone names and explicit documented comparison aliases.

No subagents or parallel heavy processes unless the user explicitly requests them.
Do not publish a partially patched workbook. Run the affected checks and verify
the delivery hashes. Existing user authorization to publish applies only to the
work requested in that session; do not infer authorization for new work.
