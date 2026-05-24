"""
Pattern detection — breakout, flag, trend-change gap, cup-and-handle.

Each pattern returns entry/stop prices or None if not detected.
"""

import numpy as np


def detect_breakout(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                    current_price: float) -> dict | None:
    """
    Breakout of resistance.

    Logic:
    - Resistance = highest high of last 5 days (excluding today)
    - Breakout = current price > resistance
    - Entry = current price + $0.02
    - Stop = lowest low of last 20 days - $0.05 (or 10-day - $0.03 if <20 days)
    """
    if len(highs) < 6:
        return None

    resistance = float(np.max(highs[-6:-1]))  # Last 5 days, not including today
    if current_price <= resistance:
        return None

    # Stop: use 20-day low if available, else 10-day
    if len(lows) >= 20:
        stop_level = float(np.min(lows[-20:]))
        stop = round(stop_level - 0.05, 4)
    elif len(lows) >= 10:
        stop_level = float(np.min(lows[-10:]))
        stop = round(stop_level - 0.03, 4)
    else:
        stop_level = float(np.min(lows))
        stop = round(stop_level - 0.03, 4)

    entry = round(current_price + 0.02, 4)

    if stop >= entry:
        return None

    return {
        "type": "Breakout",
        "entry": entry,
        "stop": stop,
        "details": f"Broke resistance at ${resistance:.4f}",
    }


def detect_flag(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                current_price: float) -> dict | None:
    """
    Flag pattern.

    Logic:
    - Steep upward move in first half
    - Consolidation (tighter range) in second half
    - Price near or breaking upper channel
    - Entry = high of second half + $0.02
    - Stop = low of second half - $0.05
    """
    if len(closes) < 10:
        return None

    mid = len(closes) // 2
    first_half = closes[:mid]
    second_half = closes[mid:]

    # First half: steep move (range > 8% of min)
    first_range = float(np.max(first_half) - np.min(first_half))
    if np.min(first_half) <= 0 or first_range / float(np.min(first_half)) < 0.08:
        return None

    # Second half: consolidation (range < 60% of first half range)
    second_range = float(np.max(second_half) - np.min(second_half))
    if second_range > first_range * 0.6:
        return None

    # Price should be near or above upper channel
    channel_high = float(np.max(second_half))
    if current_price < channel_high * 0.95:
        return None

    channel_low = float(np.min(second_half))
    entry = round(channel_high + 0.02, 4)
    stop = round(channel_low - 0.05, 4)

    if stop >= entry:
        return None

    return {
        "type": "Flag",
        "entry": entry,
        "stop": stop,
        "details": f"Channel ${channel_low:.4f}-${channel_high:.4f}",
    }


def detect_trend_change_gap(opens: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                             closes: np.ndarray, volumes: np.ndarray,
                             current_price: float, ma10: float) -> dict | None:
    """
    Trend-change gap.

    Logic:
    - Downtrend: first avg of last 10 days > second avg * 1.05
    - Gap up: today's open > yesterday's close * 1.03
    - Closes higher than open (green candle)
    - Crosses 10-day moving average
    - Entry = current price + $0.02
    - Stop = today's low - $0.03
    """
    if len(closes) < 10:
        return None

    # Check downtrend
    last_10 = closes[-10:]
    first_avg = float(np.mean(last_10[:5]))
    second_avg = float(np.mean(last_10[5:]))
    if first_avg <= second_avg * 1.05:
        return None

    # Check gap up
    if len(closes) < 2 or len(opens) < 1:
        return None
    prev_close = float(closes[-2])
    today_open = float(opens[-1])
    if prev_close <= 0:
        return None
    gap_pct = ((today_open - prev_close) / prev_close) * 100
    if gap_pct < 3:
        return None

    # Closes higher than open
    if current_price <= today_open:
        return None

    # Crosses 10-day MA
    if ma10 <= 0 or current_price <= ma10:
        return None

    entry = round(current_price + 0.02, 4)
    stop = round(float(lows[-1]) - 0.03, 4)

    if stop >= entry:
        return None

    return {
        "type": "Trend-change gap",
        "entry": entry,
        "stop": stop,
        "details": f"Gap up {gap_pct:.1f}% from downtrend, crossed 10-day MA",
    }


def detect_cup_and_handle(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                           current_price: float) -> dict | None:
    """
    Cup-and-handle pattern.

    Logic:
    - Follows a downtrend
    - Left rim > bottom * 1.08 (gradual direction change)
    - Right rim > bottom * 1.08
    - Price near or above right rim
    - Entry = current price + $0.02
    - Stop = lowest low of last 5 days - $0.02
    """
    if len(closes) < 15:
        return None

    third = len(closes) // 3
    left_high = float(np.max(closes[:third]))
    bottom = float(np.min(closes[third:2 * third]))
    right_high = float(np.max(closes[2 * third:]))

    if bottom <= 0:
        return None

    # Cup shape: rims > bottom by 8%+
    if left_high <= bottom * 1.08 or right_high <= bottom * 1.08:
        return None

    # Price near or above right rim
    if current_price < right_high * 0.97:
        return None

    # Stop: lowest low of last 5 days
    low_5d = float(np.min(lows[-5:]))
    entry = round(current_price + 0.02, 4)
    stop = round(low_5d - 0.02, 4)

    if stop >= entry:
        return None

    return {
        "type": "Cup-and-handle",
        "entry": entry,
        "stop": stop,
        "details": f"Cup bottom ${bottom:.4f}, right rim ${right_high:.4f}",
    }


def detect_all_patterns(hist_df, current_price: float, ma10: float) -> list:
    """
    Run all pattern detectors on a price history DataFrame.
    Returns list of detected patterns with entry/stop.
    """
    highs = hist_df["High"].values.astype(float)
    lows = hist_df["Low"].values.astype(float)
    closes = hist_df["Close"].values.astype(float)
    opens = hist_df["Open"].values.astype(float)
    volumes = hist_df["Volume"].values.astype(float)

    patterns = []

    p = detect_breakout(highs, lows, closes, current_price)
    if p:
        patterns.append(p)

    p = detect_flag(highs, lows, closes, current_price)
    if p:
        patterns.append(p)

    p = detect_trend_change_gap(opens, highs, lows, closes, volumes, current_price, ma10)
    if p:
        patterns.append(p)

    p = detect_cup_and_handle(highs, lows, closes, current_price)
    if p:
        patterns.append(p)

    return patterns
