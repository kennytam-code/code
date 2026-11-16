# HK IPO desk files

**IPO / lock-up email notebook — 17 November 2026**

[Open the two-cell notebook](HK_IPO_Two_Emails.ipynb) · [Download notebook](https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Two_Emails.ipynb) · [Copy cell 2 only](HK_IPO_Second_Email_Cell.py) · [Instructions and checks](_ipo_db/ipo_email/README.md)

Run cell 1, then cell 2 in your Bloomberg-enabled Jupyter environment. The original first cell is unchanged. Cell 2 creates a separate unsent Outlook draft for YES/NEW shortable lock-ups with IPO price, latest price, price changes, unlock metrics, average 20-day turnover (HKDm) and an A-share flag. The body starts directly with the table. A-share status uses etnet capital classes; uncertain cases stay N/A. 35 offline tests pass; live Bloomberg and Windows Outlook remain unverified.

**[Download the Excel workbook](https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx)**

| File | Download |
|---|---|
| Excel | [IPO Live, A/H, Peer Trades, Screener and Database](https://github.com/kennytam-code/code/raw/refs/heads/main/HK_IPO_Database_v1.xlsx) |
| HTML dashboard | [Download and open locally](https://github.com/kennytam-code/code/raw/refs/heads/main/hk_ipo_dashboard.html) |
| Compressed HTML | [ZIP for shared-drive transfer](https://github.com/kennytam-code/code/raw/refs/heads/main/_ipo_db/TO_NOMURA/hk_ipo_dashboard.zip) |
| Updater | [Standalone Python updater](https://github.com/kennytam-code/code/raw/refs/heads/main/hk_ipo.py) |

15 November 2026: 527 IPOs, 717 live-monitor stocks and 75 A/H pairs. All existing A/H pairs, FX and CSI 300 refreshed through **13 November**. The HTML shows A/H price action and premium in separate aligned charts, with an optional CSI 300 comparison. Excel A/H caps are current share-class caps in CNY millions / HKD millions; they are distinct from Database market cap at IPO. Latest IPO Live snapshot remains 9 November; other datasets retain their recorded dates. Native Excel opened without repair; live Bloomberg responses remain unverified.

[Desk instructions](READ_ME_FIRST.txt) · [Maintenance handover](_ipo_db/START_HERE.md) · [Release details](_ipo_db/data/release_state.json)
