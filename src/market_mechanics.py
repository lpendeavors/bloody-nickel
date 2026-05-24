"""
Hyperliquid market mechanics scanner - REAL edge, not Reddit TA.

Edge sources:
1. Funding rate extremes (crowding)
2. Order book walls (where the liquidity lives)
3. Open interest divergence (someone's loading)
4. Premium/discount (sentiment)
5. Volume anomaly (institutional flow)
6. Liquidation cascade proximity
"""

import numpy as np
from dataclasses import dataclass, field


@dataclass
class MarketSignal:
    """Signal based on market mechanics, not chart patterns."""
    coin: str
    direction: str       # "long" or "short"
    mechanics: list      # what the order book/funding/OI is telling us
    score: int
    funding_rate: float
    open_interest: float
    premium: float
    bid_wall: float      # largest bid level
    ask_wall: float      # largest ask level
    entry: float
    stop: float
    target_1: float
    target_2: float
    risk_per_unit: float
    timestamp: str

    @property
    def risk_reward(self):
        if self.risk_per_unit <= 0:
            return 0
        return round(abs(self.target_1 - self.entry) / self.risk_per_unit, 2)


def detect_funding_extreme(ctx: dict) -> tuple:
    """
    Funding rate extreme = overcrowded side about to get squeezed.

    Negative funding → shorts paying longs → short squeeze likely
    Positive funding → longs paying shorts → long squeeze likely

    Returns: (signal_type, description) or (None, "")
    """
    funding = float(ctx.get("funding", 0))

    # Funding is per 8 hours. Annualize for context.
    # Extreme: > 0.01% per 8h (≈11% annualized) or < -0.01%
    if funding < -0.0001:
        return "long", f"Funding extreme SHORT ({funding*100:.4f}%/8h) - shorts overcrowded, squeeze likely"
    elif funding > 0.0001:
        return "short", f"Funding extreme LONG ({funding*100:.4f}%/8h) - longs overcrowded, dump likely"

    return None, ""


def detect_book_walls(book: dict, mid_px: float) -> tuple:
    """
    Find large resting orders (walls) in the order book.

    Bid wall = support (where big money is buying)
    Ask wall = resistance (where big money is selling)

    Returns: (bid_wall_px, bid_wall_sz, ask_wall_px, ask_wall_sz)
    """
    bids = book.get("levels", [[], []])[0]
    asks = book.get("levels", [[], []])[1]

    if not bids or not asks:
        return None, 0, None, 0

    # Filter out levels with missing data
    bids = [b for b in bids if b.get("sz") and b.get("px")]
    asks = [a for a in asks if a.get("sz") and a.get("px")]

    if not bids or not asks:
        return None, 0, None, 0

    # Find largest bid and ask
    best_bid = max(bids, key=lambda x: float(x.get("sz", 0)))
    best_ask = max(asks, key=lambda x: float(x.get("sz", 0)))

    bid_px = float(best_bid.get("px", 0))
    bid_sz = float(best_bid.get("sz", 0))
    ask_px = float(best_ask.get("px", 0))
    ask_sz = float(best_ask.get("sz", 0))

    # Wall must be significant - at least 3x average level size
    avg_bid_sz = np.mean([float(b.get("sz", 0)) for b in bids]) if bids else 0
    avg_ask_sz = np.mean([float(a.get("sz", 0)) for a in asks]) if asks else 0

    significant_bid = bid_sz > avg_bid_sz * 3
    significant_ask = ask_sz > avg_ask_sz * 3

    return (
        bid_px if significant_bid else None,
        bid_sz if significant_bid else 0,
        ask_px if significant_ask else None,
        ask_sz if significant_ask else 0,
    )


def detect_oi_divergence(ctx: dict, candles) -> tuple:
    """
    Open interest divergence:
    - OI increasing + price flat = someone loading (breakout coming)
    - OI increasing + price dropping = shorts loading (dump coming)
    - OI decreasing + price dropping = longs closing (capitulation)
    - OI decreasing + price rising = shorts covering (squeeze)
    """
    # We need historical OI to detect divergence - for now use current context
    oi = float(ctx.get("openInterest", 0))
    premium = float(ctx.get("premium", 0))

    signals = []

    # Persistent discount = bearish positioning
    if premium < -0.002:
        signals.append(("short", f"Persistent discount to oracle ({premium*100:.2f}%) - bearish positioning"))
    # Persistent premium = bullish positioning
    elif premium > 0.002:
        signals.append(("long", f"Persistent premium to oracle ({premium*100:.2f}%) - bullish positioning"))

    return signals


def detect_volume_anomaly(ctx: dict) -> tuple:
    """
    Volume anomaly - daily volume relative to OI.

    High volume/OI ratio = active trading, possible accumulation or distribution.
    Low volume/OI ratio = quiet, waiting.
    """
    volume = float(ctx.get("dayNtlVlm", 0))
    oi = float(ctx.get("openInterest", 0))

    if oi <= 0:
        return None, ""

    vol_oi_ratio = volume / oi

    # Volume/OI can be in different units (notional vs units), so use relative threshold
    # Just flag if volume is very high in absolute terms
    if volume > 500_000_000:  # $500M+ daily volume
        return "alert", f"High volume ${volume/1e6:.0f}M — active trading"

    return None, ""


def detect_liquidity_imbalance(book: dict) -> tuple:
    """
    Bid/ask imbalance = where the next move is likely headed.

    Heavy bids, light asks → price likely up (buying pressure)
    Heavy asks, light bids → price likely down (selling pressure)
    """
    bids = book.get("levels", [[], []])[0]
    asks = book.get("levels", [[], []])[1]

    if not bids or not asks:
        return None, ""

    total_bid = sum(float(b.get("sz", 0)) for b in bids[:10])
    total_ask = sum(float(a.get("sz", 0)) for a in asks[:10])

    if total_ask <= 0:
        return None, ""

    ratio = total_bid / total_ask

    if ratio > 3.0:
        return "long", f"Bid/ask imbalance {ratio:.1f}:1 - heavy buying pressure in book"
    elif ratio < 0.33:
        return "short", f"Bid/ask imbalance {ratio:.2f}:1 - heavy selling pressure in book"

    return None, ""


def detect_cascade_proximity(ctx: dict, book: dict) -> tuple:
    """
    Estimate if price is near liquidation cascade zones.

    When OI is high and price moves toward the side with heavy leverage,
    liquidations cascade and accelerate the move.
    """
    oi = float(ctx.get("openInterest", 0))
    mark = float(ctx.get("markPx", 0))
    mid = float(ctx.get("midPx", 0))

    if mark <= 0 or mid <= 0:
        return None, ""

    # Mark vs mid divergence can indicate stress
    divergence = (mark - mid) / mid

    if abs(divergence) > 0.001:
        direction = "short" if divergence > 0 else "long"
        return direction, f"Mark/mid divergence {divergence*100:.3f}% - possible liquidation pressure"

    return None, ""


def scan_market_mechanics(coin: str, ctx: dict, book: dict, candles=None) -> MarketSignal | None:
    """
    Scan a coin using REAL market mechanics - not squiggly lines.

    Args:
        coin: symbol
        ctx: asset context (funding, OI, premium, volume)
        book: L2 order book
        candles: optional OHLCV for additional context
    """
    mechanics = []
    directions = {"long": 0, "short": 0}

    # 1. Funding extremes
    sig, desc = detect_funding_extreme(ctx)
    if sig:
        mechanics.append(desc)
        directions[sig] += 2  # Funding is strong signal

    # 2. Order book walls
    mid = float(ctx.get("midPx", 0))
    bid_px, bid_sz, ask_px, ask_sz = detect_book_walls(book, mid)
    if bid_px:
        mechanics.append(f"Bid wall ${bid_px} ({bid_sz:.0f} units)")
        directions["long"] += 1
    if ask_px:
        mechanics.append(f"Ask wall ${ask_px} ({ask_sz:.0f} units)")
        directions["short"] += 1

    # 3. OI / Premium signals
    oi_signals = detect_oi_divergence(ctx, candles)
    for sig, desc in oi_signals:
        mechanics.append(desc)
        directions[sig] += 1

    # 4. Volume anomaly
    sig, desc = detect_volume_anomaly(ctx)
    if sig:
        mechanics.append(desc)

    # 5. Liquidity imbalance
    sig, desc = detect_liquidity_imbalance(book)
    if sig:
        mechanics.append(desc)
        directions[sig] += 2  # Strong signal

    # 6. Cascade proximity
    sig, desc = detect_cascade_proximity(ctx, book)
    if sig:
        mechanics.append(desc)
        directions[sig] += 1

    # Need at least 2 mechanics to fire
    if len(mechanics) < 2:
        return None

    # Determine direction
    if directions["long"] > directions["short"]:
        direction = "long"
    elif directions["short"] > directions["long"]:
        direction = "short"
    else:
        return None  # Ambiguous - no trade

    # Entry / Stop / Targets
    mark = float(ctx.get("markPx", 0))
    premium = float(ctx.get("premium", 0))

    if direction == "long":
        entry = round(mark + mark * 0.0005, 4)
        # Stop below the bid wall if we have one, else 1.5% below
        if bid_px:
            stop = round(bid_px - bid_px * 0.005, 4)
        else:
            stop = round(mark * 0.985, 4)
        rps = entry - stop
        if rps <= 0:
            return None
        target_1 = round(entry + rps, 4)
        target_2 = round(entry + rps * 2, 4)
    else:
        entry = round(mark - mark * 0.0005, 4)
        if ask_px:
            stop = round(ask_px + ask_px * 0.005, 4)
        else:
            stop = round(mark * 1.015, 4)
        rps = stop - entry
        if rps <= 0:
            return None
        target_1 = round(entry - rps, 4)
        target_2 = round(entry - rps * 2, 4)

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return MarketSignal(
        coin=coin,
        direction=direction,
        mechanics=mechanics,
        score=len(mechanics),
        funding_rate=float(ctx.get("funding", 0)),
        open_interest=float(ctx.get("openInterest", 0)),
        premium=premium,
        bid_wall=bid_px or 0,
        ask_wall=ask_px or 0,
        entry=entry,
        stop=stop,
        target_1=target_1,
        target_2=target_2,
        risk_per_unit=round(rps, 4),
        timestamp=ts,
    )
