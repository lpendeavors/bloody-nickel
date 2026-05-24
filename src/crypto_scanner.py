"""
Crypto technical scanner — confluence-based signals for Hyperliquid.

Entry requires 3+ confluence factors:
- RSI oversold/momentum
- Volume spike (2x+ avg)
- VWAP bounce
- EMA crossover (9/21)
- Liquidity sweep (stop hunt)
- Order block return

Kill switches:
- 3% daily drawdown → stop
- 2 consecutive losses → 1hr cooldown
- No trading 2-5am UTC
"""

import numpy as np
from dataclasses import dataclass


def rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index. Returns array same length as input."""
    n = len(closes)
    if n < period + 1:
        return np.full(n, np.nan)

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # Wilder's smoothing (exponential)
    alpha = 1.0 / period
    avg_gain = np.zeros(len(gains))
    avg_loss = np.zeros(len(gains))
    avg_gain[period - 1] = np.mean(gains[:period])
    avg_loss[period - 1] = np.mean(losses[:period])

    for i in range(period, len(gains)):
        avg_gain[i] = alpha * gains[i] + (1 - alpha) * avg_gain[i - 1]
        avg_loss[i] = alpha * losses[i] + (1 - alpha) * avg_loss[i - 1]

    rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100)
    rsi_values = 100 - (100 / (1 + rs))

    # Pad with NaN for alignment — first `period` values have no RSI
    result = np.full(n, np.nan)
    result[period:] = rsi_values[period - 1:n - 1]
    return result


def ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    alpha = 2.0 / (period + 1)
    result = np.zeros_like(data)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result


def vwap(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
         volumes: np.ndarray) -> np.ndarray:
    """Volume Weighted Average Price (rolling from start)."""
    typical = (highs + lows + closes) / 3
    cum_tp_vol = np.cumsum(typical * volumes)
    cum_vol = np.cumsum(volumes)
    return np.where(cum_vol > 0, cum_tp_vol / cum_vol, closes)


@dataclass
class ConfluenceSignal:
    """A confluence-based trade signal."""
    coin: str
    direction: str  # "long" or "short"
    factors: list   # list of factor descriptions
    score: int      # number of confluence factors
    entry: float
    stop: float
    target_1: float   # 1:1 R:R
    target_2: float   # 2:1 R:R
    risk_per_share: float
    timestamp: str

    @property
    def risk_reward(self) -> float:
        """R:R ratio to first target."""
        if self.risk_per_share <= 0:
            return 0
        return round((self.target_1 - self.entry) / self.risk_per_share, 2)


def scan_coin(coin: str, candles_4h, candles_1h, candles_15m) -> ConfluenceSignal | None:
    """
    Scan a single coin for confluence.

    Args:
        coin: symbol name
        candles_4h: CandleArray of 4H data
        candles_1h: CandleArray of 1H data
        candles_15m: CandleArray of 15m data
    """
    if len(candles_4h) < 30 or len(candles_1h) < 30 or len(candles_15m) < 30:
        return None

    price = candles_1h.last_price
    factors = []

    # ===== RSI =====
    rsi_4h = rsi(candles_4h.closes)
    rsi_1h = rsi(candles_1h.closes)
    rsi_val_4h = rsi_4h[-1] if not np.isnan(rsi_4h[-1]) else 50
    rsi_val_1h = rsi_1h[-1] if not np.isnan(rsi_1h[-1]) else 50

    # Oversold bounce (long)
    if rsi_val_4h < 35 or rsi_val_1h < 35:
        factors.append(f"RSI oversold (4H={rsi_val_4h:.0f}, 1H={rsi_val_1h:.0f})")

    # Momentum (short) — RSI > 65 with volume
    if rsi_val_4h > 65 or rsi_val_1h > 65:
        vol_ratio = candles_1h.last_volume / candles_1h.avg_volume if candles_1h.avg_volume > 0 else 0
        if vol_ratio > 1.5:
            factors.append(f"RSI momentum (4H={rsi_val_4h:.0f}, 1H={rsi_val_1h:.0f}, vol={vol_ratio:.1f}x)")

    # ===== VOLUME SPIKE =====
    vol_1h_ratio = candles_1h.last_volume / candles_1h.avg_volume if candles_1h.avg_volume > 0 else 0
    vol_15m_ratio = candles_15m.last_volume / candles_15m.avg_volume if candles_15m.avg_volume > 0 else 0

    if vol_1h_ratio >= 2.0:
        factors.append(f"Volume spike 1H ({vol_1h_ratio:.1f}x)")
    if vol_15m_ratio >= 2.5:
        factors.append(f"Volume spike 15m ({vol_15m_ratio:.1f}x)")

    # ===== VWAP BOUNCE =====
    vwap_1h = vwap(candles_1h.highs, candles_1h.lows, candles_1h.closes, candles_1h.volumes)
    vwap_val = vwap_1h[-1]
    vwap_dist = abs(price - vwap_val) / vwap_val

    if vwap_dist < 0.01:  # Within 1% of VWAP
        if price > vwap_val:
            factors.append("VWAP bounce (above)")
        else:
            factors.append("VWAP bounce (below)")

    # ===== EMA CROSSOVER (9/21 on 4H) =====
    ema_9 = ema(candles_4h.closes, 9)
    ema_21 = ema(candles_4h.closes, 21)

    # Cross happened in last 3 candles
    if len(ema_9) >= 3:
        cross_up = ema_9[-1] > ema_21[-1] and ema_9[-3] < ema_21[-3]
        cross_down = ema_9[-1] < ema_21[-1] and ema_9[-3] > ema_21[-3]
        if cross_up:
            factors.append("EMA 9/21 cross up (4H)")
        elif cross_down:
            factors.append("EMA 9/21 cross down (4H)")

    # ===== LIQUIDITY SWEEP =====
    # Price wicks below recent swing low then closes back above
    if len(candles_1h) >= 10:
        recent_lows = candles_1h.lows[-10:-1]
        swing_low = float(np.min(recent_lows))
        last_low = candles_1h.lows[-1]
        last_close = candles_1h.closes[-1]

        if last_low < swing_low and last_close > swing_low:
            factors.append(f"Liquidity sweep (wick below ${swing_low:.4f})")

    # ===== ORDER BLOCK =====
    # Zone where last aggressive move started
    if len(candles_4h) >= 10:
        # Find the biggest candle in last 10 (the aggressive move)
        ranges = candles_4h.highs[-10:] - candles_4h.lows[-10:]
        biggest_idx = int(np.argmax(ranges))
        ob_high = float(candles_4h.highs[-10 + biggest_idx])
        ob_low = float(candles_4h.lows[-10 + biggest_idx])

        if ob_low <= price <= ob_high * 1.02:
            factors.append(f"Order block zone (${ob_low:.4f}-${ob_high:.4f})")

    # ===== TREND DIRECTION =====
    if len(factors) < 3:
        return None

    # Determine direction based on factors
    long_signals = sum(1 for f in factors if any(k in f.lower() for k in ["oversold", "bounce", "cross up", "sweep"]))
    short_signals = sum(1 for f in factors if any(k in f.lower() for k in ["momentum", "cross down"]))

    if long_signals > short_signals:
        direction = "long"
    elif short_signals > long_signals:
        direction = "short"
    else:
        direction = "long"  # default to long in ambiguous

    # ===== ENTRY / STOP / TARGETS =====
    if direction == "long":
        entry = round(price + price * 0.001, 6)  # Slightly above current
        # Stop: below recent swing low or VWAP
        if len(candles_1h) >= 10:
            stop_level = float(np.min(candles_1h.lows[-10:]))
        else:
            stop_level = price * 0.97
        stop = round(stop_level - stop_level * 0.005, 6)  # 0.5% below

        rps = entry - stop
        if rps <= 0:
            return None

        target_1 = round(entry + rps, 6)      # 1:1
        target_2 = round(entry + rps * 2, 6)  # 2:1
    else:
        entry = round(price - price * 0.001, 6)
        if len(candles_1h) >= 10:
            stop_level = float(np.max(candles_1h.highs[-10:]))
        else:
            stop_level = price * 1.03
        stop = round(stop_level + stop_level * 0.005, 6)

        rps = stop - entry
        if rps <= 0:
            return None

        target_1 = round(entry - rps, 6)
        target_2 = round(entry - rps * 2, 6)

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return ConfluenceSignal(
        coin=coin,
        direction=direction,
        factors=factors,
        score=len(factors),
        entry=entry,
        stop=stop,
        target_1=target_1,
        target_2=target_2,
        risk_per_share=round(rps, 6),
        timestamp=ts,
    )


def is_kill_switch_active() -> tuple:
    """
    Check if kill switch is active.
    Returns (active: bool, reason: str).
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # No trading 2-5am UTC (low liquidity)
    if 2 <= now.hour < 5:
        return True, "Low liquidity hours (2-5am UTC)"

    # TODO: Track daily drawdown and consecutive losses in state file
    return False, ""
