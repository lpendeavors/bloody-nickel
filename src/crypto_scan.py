#!/usr/bin/env python3
"""
Bloody Nickel — Hyperliquid Market Mechanics Scanner

Scans for REAL edge: funding extremes, order book walls,
OI divergence, liquidity imbalance, cascade proximity.

No squiggly lines. No Reddit TA.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from hyperliquid_client import get_meta_and_contexts, get_all_mids, _post
from market_mechanics import scan_market_mechanics

# Larry's watchlist — high volume perps
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
    
    print(f"📊 Scanning {len(COINS)} Hyperliquid pairs for market mechanics...")
    print(f"   Edge: Funding extremes · Book walls · OI divergence · Liquidity imbalance\n")
    
    signals = []
    
    for coin in COINS:
        if coin not in ctx_map:
            continue
        
        try:
            ctx = ctx_map[coin]
            book = get_order_book(coin)
            
            signal = scan_market_mechanics(coin, ctx, book)
            
            if signal:
                emoji = "🟢" if signal.direction == "long" else "🔴"
                signals.append(signal)
                print(f"   {emoji} {coin}: {signal.score} mechanics | "
                      f"{signal.direction.upper()} @ ${signal.entry}")
                print(f"      Funding: {signal.funding_rate*100:.4f}%/8h | "
                      f"OI: {signal.open_interest:,.0f} | "
                      f"Premium: {signal.premium*100:.3f}%")
                print(f"      {' · '.join(signal.mechanics)}")
                print()
            else:
                # Show quiet status
                funding = float(ctx.get("funding", 0))
                oi = float(ctx.get("openInterest", 0))
                print(f"   ⚪ {coin}: quiet | "
                      f"Funding: {funding*100:.4f}%/8h | OI: {oi:,.0f}")
            
            time.sleep(0.15)  # Rate limit
        except Exception as e:
            print(f"   ⚠️ {coin}: {e}")
    
    signals.sort(key=lambda s: s.score, reverse=True)
    return signals


def format_output(signals: list) -> str:
    """Format signals for Discord."""
    if not signals:
        return ("📊 **Hyperliquid Market Mechanics Scan** — No setups.\n"
                "Market is quiet. No funding extremes, no book walls firing, no OI divergence.")
    
    lines = [
        f"📊 **Hyperliquid Market Mechanics** — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**{len(signals)} signal(s)** | Edge: Funding · Book Walls · OI · Liquidity\n",
    ]
    
    for s in signals:
        emoji = "🟢" if s.direction == "long" else "🔴"
        lines.append(f"{emoji} **{s.coin}** — {s.direction.upper()} | Score: {s.score}")
        lines.append(f"   Entry: `${s.entry}` | Stop: `${s.stop}`")
        lines.append(f"   T1 (1:1): `${s.target_1}` | T2 (2:1): `${s.target_2}`")
        lines.append(f"   R:R: {s.risk_reward} | Risk: `${s.risk_per_unit}`/unit")
        lines.append(f"   Funding: {s.funding_rate*100:.4f}%/8h | OI: {s.open_interest:,.0f}")
        lines.append(f"   {' · '.join(s.mechanics)}")
        lines.append("")
    
    lines.append("_Mechanics: Funding · Book Walls · OI Divergence · Liquidity Imbalance · Cascade Proximity_")
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
        "risk_per_unit": s.risk_per_unit,
        "risk_reward": s.risk_reward,
        "funding_rate": s.funding_rate,
        "open_interest": s.open_interest,
        "premium": s.premium,
        "mechanics": s.mechanics,
        "timestamp": s.timestamp,
    } for s in signals]
    
    with open(os.path.join(out_dir, "latest_crypto_signals.json"), "w") as f:
        json.dump(results, f, indent=2)
    
    return output


if __name__ == "__main__":
    main()
