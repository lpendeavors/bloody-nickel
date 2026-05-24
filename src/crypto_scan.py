#!/usr/bin/env python3
"""
Bloody Nickel — Hyperliquid Crypto Scanner

Scans top perp pairs on Hyperliquid for confluence signals.
No auth needed — read-only market data.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from hyperliquid_client import get_meta_and_contexts, get_candle_array
from crypto_scanner import scan_coin, is_kill_switch_active

# Top coins to scan by volume
TOP_COINS = [
    "BTC", "ETH", "SOL", "DOGE", "XRP", "ARB", "AVAX", "LINK",
    "SUI", "APT", "OP", "WIF", "PEPE", "FET", "RNDR", "TIA",
    "INJ", "SEI", "PYTH", "JUP", "ONDO", "PENDLE", "ENA", "STX",
]

# Config
MIN_CONFLUENCE = 3
MAX_LEVERAGE = 5  # Conservative for Larry's risk tolerance


def scan_all():
    """Scan all configured coins for confluence signals."""
    # Check kill switch
    active, reason = is_kill_switch_active()
    if active:
        print(f"🛑 Kill switch active: {reason}")
        return []

    # Get market contexts for volume ranking
    try:
        meta_ctx = get_meta_and_contexts()
        universe = meta_ctx[0]["universe"]
        contexts = meta_ctx[1]

        # Build volume map
        vol_map = {}
        for i, asset in enumerate(universe):
            name = asset["name"]
            if i < len(contexts):
                vol = float(contexts[i].get("dayNtlVlm", 0))
                vol_map[name] = vol
    except Exception as e:
        print(f"⚠️ Could not fetch market contexts: {e}")
        vol_map = {}

    # Sort coins by volume, take top N
    ranked = sorted(
        [c for c in TOP_COINS if c in vol_map],
        key=lambda x: vol_map.get(x, 0),
        reverse=True,
    )[:20]

    if not ranked:
        ranked = TOP_COINS[:20]

    print(f"📊 Scanning {len(ranked)} Hyperliquid pairs...")
    signals = []

    for coin in ranked:
        try:
            # Fetch multi-timeframe data
            candles_4h = get_candle_array(coin, "4h", hours_back=200)
            candles_1h = get_candle_array(coin, "1h", hours_back=100)
            candles_15m = get_candle_array(coin, "15m", hours_back=50)

            signal = scan_coin(coin, candles_4h, candles_1h, candles_15m)
            if signal and signal.score >= MIN_CONFLUENCE:
                signals.append(signal)
                emoji = "🟢" if signal.direction == "long" else "🔴"
                print(f"   {emoji} {coin}: {signal.score} factors | "
                      f"{signal.direction.upper()} @ ${signal.entry:.6f} | "
                      f"Stop ${signal.stop:.6f} | R:R {signal.risk_reward}")
            else:
                score = signal.score if signal else 0
                print(f"   ⚪ {coin}: {score} factors (need {MIN_CONFLUENCE})")

            time.sleep(0.2)  # Rate limit
        except Exception as e:
            print(f"   ⚠️ {coin}: {e}")

    # Sort by score descending
    signals.sort(key=lambda s: s.score, reverse=True)
    return signals


def format_output(signals: list) -> str:
    """Format signals for Discord."""
    if not signals:
        return ("📊 **Hyperliquid Crypto Scan** — No setups.\n"
                f"Need {MIN_CONFLUENCE}+ confluence factors. Market quiet or kill switch active.")

    lines = [
        f"📊 **Hyperliquid Crypto Scan** — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**{len(signals)} signal(s)** | {MIN_CONFLUENCE}+ confluence required\n",
    ]

    for s in signals:
        emoji = "🟢" if s.direction == "long" else "🔴"
        lines.append(f"{emoji} **{s.coin}** — {s.direction.upper()} | Score: {s.score}")
        lines.append(f"   Entry: `${s.entry:.6f}` | Stop: `${s.stop:.6f}`")
        lines.append(f"   T1 (1:1): `${s.target_1:.6f}` | T2 (2:1): `${s.target_2:.6f}`")
        lines.append(f"   R:R: {s.risk_reward} | Risk: `${s.risk_per_share:.6f}`/unit")
        lines.append(f"   Factors: {' · '.join(s.factors)}")
        lines.append("")

    lines.append(
        "_Confluence: RSI + Volume + VWAP + EMA 9/21 + Liquidity sweep + Order block · "
        "Max 5x leverage · 2% risk/trade_"
    )
    return "\n".join(lines)


def main():
    signals = scan_all()
    output = format_output(signals)

    print("\n" + "=" * 60)
    print(output)
    print("=" * 60)

    # Save results
    out_dir = os.path.join(os.path.dirname(__file__), "..")
    results = [{
        "coin": s.coin,
        "direction": s.direction,
        "score": s.score,
        "entry": s.entry,
        "stop": s.stop,
        "target_1": s.target_1,
        "target_2": s.target_2,
        "risk_per_share": s.risk_per_share,
        "risk_reward": s.risk_reward,
        "factors": s.factors,
        "timestamp": s.timestamp,
    } for s in signals]

    with open(os.path.join(out_dir, "latest_crypto_signals.json"), "w") as f:
        json.dump(results, f, indent=2)

    return output


if __name__ == "__main__":
    main()
