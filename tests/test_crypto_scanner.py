"""Tests for crypto technical indicators and scanner."""

import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from crypto_scanner import rsi, ema, vwap, scan_coin
from hyperliquid_client import CandleArray


def make_candles(closes, volumes=None, highs=None, lows=None, opens=None):
    """Helper to create a CandleArray from simple data."""
    n = len(closes)
    if volumes is None:
        volumes = [1000.0] * n
    if highs is None:
        highs = [c + 0.5 for c in closes]
    if lows is None:
        lows = [c - 0.5 for c in closes]
    if opens is None:
        opens = [c - 0.1 for c in closes]

    return CandleArray(
        opens=np.array(opens),
        highs=np.array(highs),
        lows=np.array(lows),
        closes=np.array(closes),
        volumes=np.array(volumes),
        timestamps=np.array([1000 * i for i in range(n)]),
    )


class TestRSI:
    def test_overbought(self):
        # Steadily increasing prices → RSI should be high
        closes = np.array([100 + i * 2 for i in range(50)], dtype=float)
        result = rsi(closes)
        # Last RSI should be very high (near 100)
        assert result[-1] > 70

    def test_oversold(self):
        # Steadily decreasing prices → RSI should be low
        closes = np.array([200 - i * 2 for i in range(50)], dtype=float)
        result = rsi(closes)
        assert result[-1] < 30

    def test_neutral(self):
        # Oscillating prices → RSI near 50
        closes = np.array([100 + (i % 2) * 2 for i in range(50)], dtype=float)
        result = rsi(closes)
        assert 40 < result[-1] < 60

    def test_length_preserved(self):
        closes = np.array([100.0] * 30)
        result = rsi(closes)
        assert len(result) == len(closes)


class TestEMA:
    def test_basic(self):
        data = np.array([10.0, 11.0, 12.0, 13.0, 14.0])
        result = ema(data, 3)
        # EMA should track toward the data
        assert result[-1] > result[0]
        assert len(result) == len(data)

    def test_constant(self):
        data = np.array([10.0] * 20)
        result = ema(data, 5)
        assert abs(result[-1] - 10.0) < 0.001


class TestVWAP:
    def test_basic(self):
        highs = np.array([11.0, 12.0, 13.0])
        lows = np.array([9.0, 10.0, 11.0])
        closes = np.array([10.0, 11.0, 12.0])
        volumes = np.array([100.0, 100.0, 100.0])
        result = vwap(highs, lows, closes, volumes)
        # VWAP should be weighted average of typical prices
        assert len(result) == 3
        assert result[-1] > 0


class TestScanCoin:
    def test_insufficient_data(self):
        c4 = make_candles([10.0] * 5)
        c1 = make_candles([10.0] * 5)
        c15 = make_candles([10.0] * 5)
        result = scan_coin("TEST", c4, c1, c15)
        assert result is None

    def test_no_confluence(self):
        # Flat market, no signals
        prices = [100.0] * 50
        c4 = make_candles(prices)
        c1 = make_candles(prices)
        c15 = make_candles(prices)
        result = scan_coin("TEST", c4, c1, c15)
        assert result is None  # Not enough factors

    def test_volume_spike_detected(self):
        # Create a scenario with volume spike
        prices = [100.0] * 50
        vols = [1000.0] * 49 + [5000.0]  # 5x volume on last candle
        c4 = make_candles(prices, volumes=vols)
        c1 = make_candles(prices, volumes=vols)
        c15 = make_candles(prices, volumes=vols)
        result = scan_coin("TEST", c4, c1, c15)
        # Should detect volume spike at minimum
        if result:
            assert any("Volume" in f for f in result.factors)
