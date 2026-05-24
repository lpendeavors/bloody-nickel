#!/usr/bin/env python3
"""
Bloody Nickel — Penny Stock Screener

Screens the market for penny stock setups matching Larry's checklist:
- Trend change + at least one indicator (vol spike, low float, high short)
- Financial review (no dilution, sign of hope)
- Tradable patterns (breakout, flag, gap, cup-and-handle)
- Risk management (1% per trade, 20% max position)
"""

import json
import os
import sys
import time
from datetime import datetime

import yfinance as yf

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from trade_math import build_trade_plan
from patterns import detect_all_patterns
from financials import check_dilution, check_financials_hope, check_debt_concern, score_candidate

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)


def screen_candidates():
    """Pull from yfinance screener feeds."""
    print("🔍 Screening...")
    all_quotes = {}

    for name, screener in [
        ("most_short", "most_shorted_stocks"),
        ("small_cap", "small_cap_gainers"),
        ("aggressive", "aggressive_small_caps"),
    ]:
        try:
            data = yf.screen(screener, count=50)
            for q in data.get("quotes", []):
                all_quotes[q.get("symbol", "")] = q
            print(f"   {name}: {len(data.get('quotes', []))}")
        except Exception as e:
            print(f"   ⚠️ {name}: {e}")

    lo = CONFIG["price_min"]
    hi = CONFIG["price_max"]
    penny = {s: q for s, q in all_quotes.items()
             if lo < (q.get("regularMarketPrice", 0) or 0) < hi}
    print(f"   {len(penny)} penny candidates")
    return penny


def analyze_ticker(sym, info, hist):
    """Analyze one ticker against the full checklist."""
    if hist.empty or len(hist) < 5:
        return None

    price = float(hist["Close"].iloc[-1])
    vol_now = float(hist["Volume"].iloc[-1])
    vol_avg = float(hist["Volume"].mean())
    vol_ratio = vol_now / vol_avg if vol_avg > 0 else 0

    # Float and short
    float_shares = info.get("floatShares", 0) or 0
    float_m = float_shares / 1_000_000
    short_pct = info.get("shortPercentOfFloat", 0) or 0
    short_pct = short_pct * 100 if short_pct < 1 else short_pct

    # Moving averages
    closes = hist["Close"].values
    ma10 = float(hist["Close"].rolling(10).mean().iloc[-1]) if len(hist) >= 10 else price

    # ===== TREND CHANGE =====
    trend_change = False
    if len(closes) >= 10:
        first_avg = float(closes[-10:-5].mean())
        second_avg = float(closes[-5:].mean())
        was_down = first_avg > second_avg * 1.05
        if was_down:
            trend_change = True

    # Breakout = trend change
    breakout_detected = False
    if len(hist) >= 6:
        resistance = float(hist["High"].iloc[-6:-1].max())
        if price > resistance:
            breakout_detected = True
            trend_change = True

    # Gap up = trend change
    gap_up = False
    if len(hist) >= 2:
        prev_close = float(hist["Close"].iloc[-2])
        today_open = float(hist["Open"].iloc[-1])
        if prev_close > 0:
            gap_pct = ((today_open - prev_close) / prev_close) * 100
            if gap_pct > CONFIG["gap_threshold_pct"]:
                gap_up = True
                trend_change = True

    if not trend_change:
        return None

    # ===== INDICATORS =====
    has_vol_spike = vol_ratio >= CONFIG["volume_spike_ratio"]
    has_low_float = 0 < float_m < CONFIG["float_threshold_m"]
    has_high_short = short_pct > CONFIG["short_threshold_pct"]

    if not (has_vol_spike or has_low_float or has_high_short):
        return None  # Need at least one indicator

    # ===== FINANCIALS =====
    dilution = check_dilution(float_m)
    hope = check_financials_hope(info)
    debt = check_debt_concern(info)

    # ===== PATTERNS =====
    patterns = detect_all_patterns(hist, price, ma10)

    # ===== SCORE =====
    score, flags = score_candidate(
        trend_change=True,
        has_volume_spike=has_vol_spike,
        has_low_float=has_low_float,
        has_high_short=has_high_short,
        dilution_flag=dilution,
        financials_hope=hope,
        debt_concern=debt,
        patterns=patterns,
    )

    # ===== TRADE PLANS =====
    trade_plans = []
    for p in patterns:
        plan = build_trade_plan(
            entry_price=p["entry"],
            stop_price=p["stop"],
            account_balance=CONFIG["account_balance"],
            risk_pct=CONFIG["risk_percent"],
            max_position_pct=CONFIG["max_position_pct"],
        )
        if plan:
            plan["pattern"] = p["type"]
            plan["details"] = p["details"]
            trade_plans.append(plan)

    return {
        "ticker": sym,
        "name": info.get("shortName", ""),
        "price": round(price, 4),
        "float_m": round(float_m, 2),
        "short_pct": round(short_pct, 1),
        "vol_ratio": round(vol_ratio, 1),
        "score": score,
        "flags": flags,
        "patterns": [p["type"] for p in patterns],
        "trade_plans": trade_plans,
        "dilution": dilution,
        "financials_hope": hope,
        "debt_concern": debt,
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "market_cap": info.get("marketCap", 0),
    }


def run_screener():
    """Full scan: screen -> enrich -> score -> output."""
    candidates = screen_candidates()
    if not candidates:
        return []

    symbols = list(candidates.keys())[:CONFIG["max_tickers_to_scan"]]
    results = []

    print(f"\n📊 Analyzing {len(symbols)} tickers...")

    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            hist = t.history(period="1mo")

            result = analyze_ticker(sym, info, hist)
            if result:
                results.append(result)
                print(f"   ✅ {sym}: ${result['price']:.4f} | Score {result['score']}")
            time.sleep(0.3)
        except Exception as e:
            print(f"   ⚠️ {sym}: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def format_output(results):
    """Format for Discord."""
    if not results:
        return ("📊 **Daily Penny Stock Scan** — No setups today.\n"
                "Criteria: Trend change + (Vol spike | Float <30M | Short >20%)")

    lines = [
        f"📊 **Daily Penny Stock Scan** — {datetime.now().strftime('%Y-%m-%d')}",
        f"**{len(results)} candidates** | Trend change + indicator(s)\n",
    ]

    for i, r in enumerate(results[:10], 1):
        lines.append(f"**{i}. {r['ticker']}** — ${r['price']:.4f} | Score: {r['score']}")
        lines.append(
            f"   Float: {r['float_m']:.1f}M | Short: {r['short_pct']:.1f}% | "
            f"Vol: {r['vol_ratio']:.1f}x | MCap: ${r.get('market_cap', 0) / 1_000_000:.1f}M"
        )
        lines.append(f"   {' · '.join(r['flags'])}")

        for tp in r.get("trade_plans", []):
            lines.append(
                f"   📐 **{tp['pattern']}**: Entry ${tp['entry']:.4f} | "
                f"Stop ${tp['stop']:.4f} | Risk ${tp['risk_per_share']:.4f}/sh | "
                f"{tp['shares']} shares (${tp['position_value']:.0f}) | "
                f"Risk: ${tp['total_risk']:.2f}"
            )
        lines.append("")

    lines.append(
        "_Trend change + (Vol spike | Float <30M | Short >20%) · "
        "Patterns: Breakout/Flag/Gap/Cup · 1% risk/trade · 20% max position_"
    )
    return "\n".join(lines)


def main():
    results = run_screener()
    output = format_output(results)

    print("\n" + "=" * 60)
    print(output)
    print("=" * 60)

    # Save results
    out_dir = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(out_dir, "latest_results.json"), "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Save trade records
    records = []
    for r in results:
        for tp in r.get("trade_plans", []):
            records.append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "symbol": r["ticker"],
                "account_balance": CONFIG["account_balance"],
                "risk_pct": f"{CONFIG['risk_percent']*100:.0f}%",
                "entry_price": tp["entry"],
                "stop_price": tp["stop"],
                "risk_per_share": tp["risk_per_share"],
                "total_risk": tp["total_risk"],
                "shares": tp["shares"],
                "pattern": tp["pattern"],
            })

    with open(os.path.join(out_dir, "trade_records.json"), "w") as f:
        json.dump(records, f, indent=2)

    return output


if __name__ == "__main__":
    main()
