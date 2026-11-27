# claude-market-monitor

Daily US market monitor built by Claude, run in parallel with `daily-market-summary` (Grok).

Site: https://matt-manus.github.io/claude-market-monitor/ (from `docs/`; past days in `docs/archive/`).

| Section | What | Source |
|---|---|---|
| 1 | Macro: VIX, DXY, 10Y, gold, oil, BTC | Yahoo |
| 2 | CNN Fear & Greed, Cboe equity put/call | CNN graphdata, Cboe daily stats |
| 3 | SPY/QQQ/DIA/IWM vs MAs, RSI, A/D | Yahoo; Russell 2000 A/D from Finviz |
| 4A | % of S&P 500 / Nasdaq-100 / Dow 30 members above 20/50/200-day SMA; 20-day breadth and RSP/IWM vs SPY | Wikipedia, NASDAQ API, SSGA DIA, Yahoo |
| 4B | Stockbee Market Monitor | Stockbee public Google Sheet |
| 4C | Breadth table, 4% pulse, momentum share (recent + 10 years) | NASDAQ screener + Yahoo |
| 5 | 11 sector ETFs vs SPY (5/21/63 days) | Yahoo |
| 6 | Momentum by group (35 groups of NASDAQ industries), leaders, ETFs | NASDAQ screener + Yahoo |

Universe (momentum): US-listed common/ordinary shares and ADRs incl. foreign-registered ordinary shares; close ≥ $5, volume ≥ 300k, $ volume ≥ $5M; momentum = close ≥ 1.2 × close 63 sessions earlier.

Schedule: `daily.yml` 06:37 and 09:37 HKT Tue–Sat; `mom10y.yml` monthly. Code in `scripts/market_monitor/`, data in `data/monitor/`.
