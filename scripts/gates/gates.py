#!/usr/bin/env python3
"""
Trading gates (separate from the market monitor page; does not change it).

Reuses the monitor engine's stock list and Yahoo download functions, read-only.

Gate 1 — breadth: (52-week new highs - new lows) / breadth universe.
         Closed when below -2%.
         New high / low = today's close is the highest / lowest close of the last
         252 sessions (closing prices, not intraday). Universe = the monitor's
         breadth universe (close >= $5, volume >= 300k that day) with 252 sessions
         of history.
Gate 4 — large vs small cap divergence: SPY close above its 200-day SMA while IWM
         close is below its 200-day SMA. Closed when that holds (mean-reversion
         setups only).
Gate 2 — momentum curve: each session t, take the stocks with RS rating >= 98 as of
         t-21 (RS score = 2 x 63-day return + 126-day + 189-day + 252-day return,
         ranked as a percentile within that day's momentum universe; a public
         approximation of the IBD RS rating, whose exact formula is not published).
         Equal-weight return t-21 -> t, minus SPY's return over the same window.
         Closed when that excess return is in the worst 5% of the last 756
         sessions (~3 years).
         Caveat: the stock list is today's listed stocks, so stocks delisted in
         the past are missing from past portfolios (survivorship bias).
Gate 3 (own positions) comes from the Trade Journal, not from here.

Outputs (data/gates/):
  gates_history.csv : one row per session
  latest.json       : latest session + rules + log
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "market_monitor"))
import engine  # noqa: E402  (read-only reuse: build_universe, download_bars)

OUT_DIR = os.path.join(HERE, "..", "..", "data", "gates")
HIST_CSV = os.path.join(OUT_DIR, "gates_history.csv")
LATEST_JSON = os.path.join(OUT_DIR, "latest.json")

LOOKBACK_52W = 252
G1_CUT = -2.0          # percent
RS_MIN = 98            # RS rating cut-off (percentile, 1-99 scale)
HOLD = 21              # sessions held (~1 month)
PCT_WINDOW = 756       # sessions (~3 years) for the gate 2 percentile
G2_CUT = 5.0           # percentile
HISTORY_DAYS = 1650    # calendar days downloaded (RS 252 + hold 21 + window 756 + margin)
SMA_LONG = 200
MIN_PRICE = engine.MIN_PRICE
MIN_VOL = engine.MIN_VOL

log_lines = []


def log(msg):
    line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}Z] {msg}"
    print(line, flush=True)
    log_lines.append(line)


# --------------------------------------------------------------------------
# Pure functions (unit-testable)
# --------------------------------------------------------------------------
def gate1_breadth(close, vol, lookback=LOOKBACK_52W):
    close = close.sort_index()
    vol = vol.reindex_like(close)
    hi = close.rolling(lookback, min_periods=lookback).max()
    lo = close.rolling(lookback, min_periods=lookback).min()
    uni = close.notna() & hi.notna() & (close >= MIN_PRICE) & (vol >= MIN_VOL)
    nh = (uni & (close >= hi)).sum(axis=1)
    nl = (uni & (close <= lo)).sum(axis=1)
    n = uni.sum(axis=1)
    out = pd.DataFrame({"g1_universe": n, "g1_new_high": nh, "g1_new_low": nl})
    out["g1_ratio_pct"] = 100 * (out["g1_new_high"] - out["g1_new_low"]) / out["g1_universe"].replace(0, np.nan)
    out = out[out["g1_universe"] > 0]
    out["g1_closed"] = out["g1_ratio_pct"] < G1_CUT
    return out


def rs_rating(close, vol):
    """Percentile RS rating (0-100) within each day's momentum universe."""
    close = close.sort_index()
    vol = vol.reindex_like(close)
    r = lambda n: close / close.shift(n) - 1  # noqa: E731
    score = 2 * r(63) + r(126) + r(189) + r(252)
    uni = (close.notna() & (close >= MIN_PRICE) & (vol >= MIN_VOL)
           & (close * vol >= engine.MIN_DOLLAR_VOL) & score.notna())
    score = score.where(uni)
    return 100 * score.rank(axis=1, pct=True)


def gate2_momentum(close, vol, spy, rs_min=RS_MIN, hold=HOLD, window=PCT_WINDOW):
    close = close.sort_index()
    rs = rs_rating(close, vol)
    pick = rs >= rs_min                                  # chosen at t-hold
    fwd = close / close.shift(hold) - 1                  # return t-hold -> t
    chosen = pick.shift(hold, fill_value=False).astype(bool)
    port = fwd.where(chosen).mean(axis=1)
    n = (chosen & fwd.notna()).sum(axis=1)
    spy = spy.reindex(close.index)
    spy_ret = spy / spy.shift(hold) - 1
    out = pd.DataFrame({"g2_n": n, "g2_port_ret_pct": 100 * port, "g2_spy_ret_pct": 100 * spy_ret})
    out["g2_excess_pct"] = out["g2_port_ret_pct"] - out["g2_spy_ret_pct"]
    out = out[(out["g2_n"] > 0) & out["g2_excess_pct"].notna()]
    ex = out["g2_excess_pct"]
    out["g2_pctile"] = ex.rolling(window, min_periods=window).apply(
        lambda a: 100 * (a <= a[-1]).mean(), raw=True)
    out["g2_closed"] = (out["g2_pctile"] <= G2_CUT).astype(object)
    out.loc[out["g2_pctile"].isna(), "g2_closed"] = None
    return out


def gate4_divergence(spy, iwm, n=SMA_LONG):
    df = pd.DataFrame({"spy": spy, "iwm": iwm}).dropna()
    df["spy_sma200"] = df["spy"].rolling(n, min_periods=n).mean()
    df["iwm_sma200"] = df["iwm"].rolling(n, min_periods=n).mean()
    df = df.dropna()
    df["spy_above"] = df["spy"] > df["spy_sma200"]
    df["iwm_above"] = df["iwm"] > df["iwm_sma200"]
    df["g4_closed"] = df["spy_above"] & ~df["iwm_above"]
    return df


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, 4)
    return o


# --------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    started = datetime.now(timezone.utc)
    start = (started - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")

    uni, info = engine.build_universe()
    close, vol, failed = engine.download_bars(uni["ysym"].tolist(), start)
    log(f"Bars: {close.shape[1]} tickers x {close.shape[0]} days; no data for {len(failed)}")
    if close.empty:
        raise SystemExit("No price data — stopping.")
    close.index = pd.to_datetime(close.index)
    vol.index = pd.to_datetime(vol.index)

    # drop an incomplete latest session (same 98% guard as the monitor)
    if len(close.index) >= 2:
        n_last, n_prev = int(close.iloc[-1].notna().sum()), int(close.iloc[-2].notna().sum())
        if n_prev and n_last < 0.98 * n_prev:
            log(f"Coverage guard: {close.index[-1].date()} has {n_last} priced vs {n_prev}; dropping it")
            close, vol = close.iloc[:-1], vol.iloc[:-1]
    # drop today's bar if the US session has not closed yet
    now_et = pd.Timestamp.now(tz="America/New_York")
    if len(close) and close.index[-1].date() == now_et.date() and (now_et.hour, now_et.minute) < (16, 45):
        log(f"Dropping {close.index[-1].date()}: US session not closed yet (ET {now_et:%H:%M})")
        close, vol = close.iloc[:-1], vol.iloc[:-1]

    g1 = gate1_breadth(close, vol)

    import yfinance as yf
    px = {}
    for sym in ["SPY", "IWM"]:
        d = yf.download(sym, start=start, auto_adjust=False, progress=False)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        px[sym] = d["Close"]
        px[sym].index = pd.to_datetime(px[sym].index)
    g4 = gate4_divergence(px["SPY"], px["IWM"])
    g4 = g4[g4.index <= close.index[-1]]
    g2 = gate2_momentum(close, vol, px["SPY"])

    h = g1.join(g2, how="left").join(g4[["spy", "spy_sma200", "iwm", "iwm_sma200", "g4_closed"]], how="left")
    h = h[h.index >= h.index[-1] - pd.Timedelta(days=760)]   # keep ~2 years in the CSV
    h.index = pd.to_datetime(h.index).date
    h.index.name = "date"
    h.round(4).to_csv(HIST_CSV)

    last = h.iloc[-1]
    latest = {
        "run_utc": started.strftime("%Y-%m-%d %H:%M"),
        "session": str(h.index[-1]),
        "gate1": {
            "closed": bool(last["g1_closed"]),
            "ratio_pct": last["g1_ratio_pct"],
            "new_high": last["g1_new_high"], "new_low": last["g1_new_low"],
            "universe": last["g1_universe"],
            "closed_since": None,
        },
        "gate2": {
            "closed": None if pd.isna(last["g2_closed"]) else bool(last["g2_closed"]),
            "excess_pct": last["g2_excess_pct"], "pctile": last["g2_pctile"],
            "port_ret_pct": last["g2_port_ret_pct"], "spy_ret_pct": last["g2_spy_ret_pct"],
            "n_stocks": last["g2_n"],
        },
        "gate4": {
            "closed": None if pd.isna(last["g4_closed"]) else bool(last["g4_closed"]),
            "spy": last["spy"], "spy_sma200": last["spy_sma200"],
            "iwm": last["iwm"], "iwm_sma200": last["iwm_sma200"],
        },
        "rules": {
            "gate1": f"(new highs - new lows) / universe < {G1_CUT}% -> closed. New high/low = close is the "
                     f"highest/lowest close of the last {LOOKBACK_52W} sessions (closing prices). Universe = close >= "
                     f"${MIN_PRICE:.0f}, volume >= {MIN_VOL:,} that day, with {LOOKBACK_52W} sessions of history.",
            "gate4": "SPY close > 200-day SMA and IWM close < 200-day SMA -> closed (mean-reversion setups only).",
            "gate2": f"stocks with RS rating >= {RS_MIN} at t-{HOLD} (RS score = 2 x 63d + 126d + 189d + 252d return, "
                     f"percentile within the momentum universe), equal weight, return to t minus SPY; closed when in "
                     f"the worst {G2_CUT:.0f}% of the last {PCT_WINDOW} sessions. Survivorship bias: today's stock list only.",
            "gate3": "from the Trade Journal, not this script",
        },
        "universe_info": info,
        "no_data_tickers": len(failed),
        "log": log_lines + engine.log_lines,
    }
    # first session of the current closed streak for gate 1
    if last["g1_closed"]:
        s = h["g1_closed"].astype(bool)
        run = s[::-1].cumprod()[::-1]
        latest["gate1"]["closed_since"] = str(run[run.astype(bool)].index[0])
    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(clean(latest), f, ensure_ascii=False, indent=1, allow_nan=False)
    log(f"Done. Session {latest['session']}; gate1 {last['g1_ratio_pct']:.2f}%; "
        f"gate2 {last['g2_excess_pct']} pct {last['g2_pctile']}; gate4 {last['g4_closed']}")


if __name__ == "__main__":
    sys.exit(main())
