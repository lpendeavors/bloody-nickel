"""Tests for pattern detection."""

import pytest
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from patterns import (
    detect_breakout,
    detect_flag,
    detect_trend_change_gap,
    detect_cup_and_handle,
)


class TestBreakout:
    def test_breakout_detected(self):
        # 5 days of highs, then price breaks above
        highs = np.array([10.0, 10.5, 10.2, 10.8, 10.3, 11.5])
        lows = np.array([9.5, 9.8, 9.7, 10.0, 9.9, 10.5])
        closes = np.array([9.8, 10.3, 10.0, 10.5, 10.1, 11.2])
        result = detect_breakout(highs, lows, closes, 11.2)
        assert result is not None
        assert result["type"] == "Breakout"
        assert result["entry"] == 11.22
        # 20-day low not available (only 6 days), use 10-day: 9.5 - 0.03
        assert result["stop"] == 9.47

    def test_no_breakout(self):
        # Price below resistance
        highs = np.array([10.0, 10.5, 10.2, 10.8, 10.3, 10.1])
        lows = np.array([9.5, 9.8, 9.7, 10.0, 9.9, 9.6])
        closes = np.array([9.8, 10.3, 10.0, 10.5, 10.1, 9.9])
        result = detect_breakout(highs, lows, closes, 9.9)
        assert result is None

    def test_too_few_days(self):
        highs = np.array([10.0, 10.5, 10.2])
        lows = np.array([9.5, 9.8, 9.7])
        closes = np.array([9.8, 10.3, 10.0])
        result = detect_breakout(highs, lows, closes, 11.0)
        assert result is None


class TestFlag:
    def test_flag_detected(self):
        # Steep move up, then consolidation
        closes = np.array([5.0, 5.5, 6.0, 6.5, 7.0, 6.8, 6.9, 6.7, 6.85, 7.05])
        highs = closes + 0.1
        lows = closes - 0.1
        result = detect_flag(highs, lows, closes, 7.05)
        assert result is not None
        assert result["type"] == "Flag"

    def test_no_flag_no_steep_move(self):
        # Flat first half
        closes = np.array([5.0, 5.0, 5.1, 5.0, 5.1, 5.0, 5.1, 5.0, 5.1, 5.05])
        highs = closes + 0.1
        lows = closes - 0.1
        result = detect_flag(highs, lows, closes, 5.05)
        assert result is None


class TestTrendChangeGap:
    def test_gap_detected(self):
        # 10 days: downtrend, then gap up + close > open + cross MA
        closes = np.array([10.0, 9.8, 9.5, 9.2, 9.0, 8.8, 8.5, 8.3, 8.1, 9.5])
        opens = np.array([10.1, 9.9, 9.6, 9.3, 9.1, 8.9, 8.6, 8.4, 8.2, 8.5])
        highs = np.maximum(opens, closes) + 0.1
        lows = np.minimum(opens, closes) - 0.1
        volumes = np.ones(10) * 100000
        ma10 = 8.8  # Below current price of 9.5

        result = detect_trend_change_gap(opens, highs, lows, closes, volumes, 9.5, ma10)
        assert result is not None
        assert result["type"] == "Trend-change gap"

    def test_no_gap_no_downtrend(self):
        # Uptrend
        closes = np.array([5.0, 5.2, 5.4, 5.6, 5.8, 6.0, 6.2, 6.4, 6.6, 6.8])
        opens = closes - 0.1
        highs = closes + 0.1
        lows = closes - 0.2
        volumes = np.ones(10) * 100000
        result = detect_trend_change_gap(opens, highs, lows, closes, volumes, 6.8, 6.0)
        assert result is None


class TestCupAndHandle:
    def test_cup_detected(self):
        # Left rim high, bottom low, right rim high
        # 15+ days
        closes = np.array([
            8.0, 8.5, 9.0, 8.8, 8.2,  # left side
            7.0, 6.5, 6.0, 6.5, 7.0,  # bottom
            8.0, 8.5, 8.8, 9.0, 9.1,  # right side
        ])
        highs = closes + 0.2
        lows = closes - 0.2
        result = detect_cup_and_handle(highs, lows, closes, 9.1)
        assert result is not None
        assert result["type"] == "Cup-and-handle"

    def test_no_cup_flat(self):
        # No cup shape
        closes = np.array([5.0] * 15)
        highs = closes + 0.1
        lows = closes - 0.1
        result = detect_cup_and_handle(highs, lows, closes, 5.0)
        assert result is None
