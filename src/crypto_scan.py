#!/usr/bin/env python3
"""
Bloody Nickel — Hyperliquid Market Mechanics Scanner

Scans for REAL edge: funding extremes, order book walls,
OI divergence, liquidity imbalance, cascade proximity.

Outputs sized trade plans ready to execute.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from hyperliquid_client import get_meta_and_contexts, _post
from market_mechanics import scan_market_mechanics
from position_sizer import size_trade, load_config

# Larry's watchlist
COINS = [
    "SOL", "BTC", "ETH",
    "DOGE", "XRP", "ARB", "AVAX", "LINK",
    "SUI", "APT", "OP", "WIF", "PEPE",
    "FET", "RNDR", "TIA", "INJ", "SEI",
    "JUP", "ENA", "PENDLE", "ONDO", "STX",
    "NEAR", "FTM", "AAVE", "UNI", "CRV",
]


def get_order_book(coin: str, n_levels: int = 20) -> dict:
    """Get L2 order book for a coin."""
    return _post({"type": "l2Book", "coin": coin, "nSigFigs": 5})


def scan_all():
    """Scan all coins for market mechanics signals."""
    config = load_config()
    min_score = config.get("min_confluence_score", 3)

    # Get metadata and contexts
    meta_ctx = get_meta_and_contexts()
    universe = meta_ctx[0]["universe"]
    contexts = meta_ctx[1]

    # Build context map
    ctx_map = {}
    for i, asset in enumerate(universe):
        name = asset["name"]
        if i < len(contexts):
            ctx_map[name] = contexts[i]

    print(f"📊 Scanning {len(COINS)} Hyperliquid pairs...")
    print(f"   Account: ${config['account_balance']} | Risk: {config['risk_per_trade_pct']*100}%/trade | Max lev: {config['max_leverage']}x")
    print(f"   Edge: Funding · Book Walls · OI · Liquidity\n")

    signals = []

    for coin in COINS:
        if coin not in ctx_map:
            continue

        try:
            ctx = ctx_map[coin]
            book = get_order_book(coin)
            signal = scan_market_mechanics(coin, ctx, book)

            if signal and signal.score >= min_score:
                plan = size_trade(
                    coin=signal.coin,
                    direction=signal.direction,
                    entry=signal.entry,
                    stop=signal.stop,
                    target_1=signal.target_1,
                    target_2=signal.target_2,
                    mechanics=signal.mechanics,
                    score=signal.score,
                    config=config,
                )
                if plan:
                    signals.append(plan)
                    emoji = "🟢" if plan.direction == "long" else "🔴"
                    print(f"   {emoji} {coin}: {plan.units:,} units {plan.direction.upper()}")
                    print(f"      Entry: ${plan.entry} | Stop: ${plan.stop}")
                    print(f"      T1: ${plan.target_1} | T2: ${plan.target_2}")
                    print(f"      Risk: ${plan.total_risk} ({plan.risk_pct}%) | {plan.leverage}x lev")
                    print(f"      {' · '.join(plan.mechanics)}")
                    print()
            else:
                score = signal.score if signal else 0
                funding = float(ctx.get("funding", 0))
                print(f"   ⚪ {coin}: {score} mechanics (need {min_score}) | {funding*100:.4f}%/8h")

            time.sleep(0.15)
        except Exception as e:
            print(f"   ⚠️ {coin}: {e}")

    signals.sort(key=lambda s: s.score, reverse=True)
    return signals


def format_output(signals: list) -> str:
    """Format signals as trade plans for Discord."""
    config = load_config()

    if not signals:
        return ("📊 **Hyperliquid Scanner** — No setups.\n"
                "Market quiet. No funding extremes, no book walls firing.")

    lines = [
        f"📊 **Hyperliquid Trade Plans** — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Account: ${config['account_balance']} | {len(signals)} signal(s)\n",
    ]

    for plan in signals:
        emoji = "🟢" if plan.direction == "long" else "🔴"
        lines.append(f"{emoji} **{plan.coin}** — {plan.direction.upper()} | Score: {plan.score}")
        lines.append(f"Entry: `${plan.entry}`")
        lines.append(f"Stop: `${plan.stop}` (${plan.risk_per_unit}/unit)")
        lines.append(f"T1: `${plan.target_1}` | T2: `${plan.target_2}`")
        lines.append(f"**{plan.units:,} units** | ${plan.position_value} value | {plan.leverage}x leverage")
        lines.append(f"Risk: **${plan.total_risk}** ({plan.risk_pct}%)")
        lines.append(f"R:R: {round(abs(plan.target_1 - plan.entry) / plan.risk_per_unit, 2)}")
        lines.append(f"{' · '.join(plan.mechanics)}")
        lines.append("")

    lines.append("_Enter with limit order · Set stop-loss immediately · T1 = take profit · Walk away_")
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
        "coin": p.coin,
        "direction": p.direction,
        "score": p.score,
        "entry": p.entry,
        "stop": p.stop,
        "target_1": p.target_1,
        "target_2": p.target_2,
        "units": p.units,
        "position_value": p.position_value,
        "leverage": p.leverage,
        "risk_per_unit": p.risk_per_unit,
        "total_risk": p.total_risk,
        "risk_pct": p.risk_pct,
        "mechanics": p.mechanics,
    } for p in signals]

    with open(os.path.join(out_dir, "latest_crypto_signals.json"), "w") as f:
        json.dump(results, f, indent=2)

    return output


if __name__ == "__main__":
    main()
