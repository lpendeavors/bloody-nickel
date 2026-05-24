"""Tests for trade math — verify every formula."""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trade_math import (
    risk_per_share,
    acceptable_risk,
    shares_to_buy,
    max_shares_by_allocation,
    position_value,
    total_risk,
    combined_risk_pct,
    build_trade_plan,
)


class TestRiskPerShare:
    def test_basic(self):
        assert risk_per_share(3.03, 2.45) == 0.58

    def test_small_values(self):
        assert risk_per_share(1.02, 1.00) == 0.02

    def test_stop_must_be_below_entry(self):
        with pytest.raises(ValueError):
            risk_per_share(3.00, 3.50)

    def test_both_positive(self):
        with pytest.raises(ValueError):
            risk_per_share(-1, 2)


class TestAcceptableRisk:
    def test_10k_1pct(self):
        assert acceptable_risk(10000, 0.01) == 100.0

    def test_22k_1pct(self):
        assert acceptable_risk(22000, 0.01) == 220.0

    def test_10k_2pct(self):
        assert acceptable_risk(10000, 0.02) == 200.0

    def test_invalid_balance(self):
        with pytest.raises(ValueError):
            acceptable_risk(-1000, 0.01)

    def test_invalid_risk_pct(self):
        with pytest.raises(ValueError):
            acceptable_risk(10000, 0.10)


class TestSharesToBuy:
    def test_basic(self):
        # $100 risk / $0.58 risk per share = 172 shares
        assert shares_to_buy(100, 0.58) == 172

    def test_larry_example(self):
        # From Larry's spreadsheet: $220 / $0.58 = 379.3 -> 379
        # But Larry said 380... let me check
        # $220 / $0.58 = 379.31... -> int() rounds down to 379
        # Larry rounded up. We round down for safety.
        assert shares_to_buy(220, 0.58) == 379

    def test_small_risk(self):
        assert shares_to_buy(100, 0.02) == 5000

    def test_zero_rps(self):
        with pytest.raises(ValueError):
            shares_to_buy(100, 0)


class TestMaxSharesByAllocation:
    def test_20pct_of_10k_at_3(self):
        # $10000 * 0.20 = $2000 / $3.00 = 666 shares
        assert max_shares_by_allocation(10000, 0.20, 3.00) == 666

    def test_20pct_of_22k_at_3(self):
        assert max_shares_by_allocation(22000, 0.20, 3.03) == 1452


class TestPositionValue:
    def test_basic(self):
        assert position_value(380, 3.03) == 1151.4

    def test_small(self):
        assert position_value(100, 1.50) == 150.0


class TestTotalRisk:
    def test_basic(self):
        assert total_risk(380, 0.58) == 220.4

    def test_larry_example(self):
        # 380 shares * $0.58 = $220.40
        assert total_risk(380, 0.58) == 220.4


class TestCombinedRiskPct:
    def test_basic(self):
        assert combined_risk_pct(220, 10000) == 0.022

    def test_zero(self):
        assert combined_risk_pct(0, 10000) == 0.0


class TestBuildTradePlan:
    def test_larry_yz_example(self):
        # From Larry's spreadsheet: YZ, $22K, 1%, entry $3.03, stop $2.45
        plan = build_trade_plan(
            entry_price=3.03,
            stop_price=2.45,
            account_balance=22000,
            risk_pct=0.01,
            max_position_pct=0.20,
        )
        assert plan is not None
        assert plan["entry"] == 3.03
        assert plan["stop"] == 2.45
        assert plan["risk_per_share"] == 0.58
        assert plan["shares"] == 379  # 220 / 0.58 = 379.31 -> 379
        assert plan["total_risk"] == 219.82  # 379 * 0.58
        assert plan["position_value"] == 1148.37  # 379 * 3.03

    def test_basic_10k(self):
        plan = build_trade_plan(
            entry_price=2.02,
            stop_price=1.80,
            account_balance=10000,
            risk_pct=0.01,
        )
        assert plan is not None
        assert plan["entry"] == 2.02
        assert plan["stop"] == 1.80
        assert plan["risk_per_share"] == 0.22
        assert plan["shares"] == 454  # 100 / 0.22 = 454.54 -> 454
        assert plan["total_risk"] == 99.88  # 454 * 0.22
        assert plan["position_value"] == 917.08  # 454 * 2.02

    def test_stop_too_far(self):
        # Stop too far away (>25% of entry) -> None
        plan = build_trade_plan(
            entry_price=1.00,
            stop_price=0.70,
            account_balance=10000,
            risk_pct=0.01,
        )
        assert plan is None  # 30% risk per share > 25% cap

    def test_combined_risk_cap(self):
        # Already have $700 at risk, can only add $100 more (8% of $10K)
        plan = build_trade_plan(
            entry_price=2.02,
            stop_price=1.80,
            account_balance=10000,
            risk_pct=0.01,
            current_open_risk=700,
        )
        # Combined risk cap is 8% = $800, already have $700
        # Remaining: $100 / $0.22 = 454 shares -> but cap limits to 454
        assert plan is not None
        assert plan["total_risk"] + 700 <= 800 + 0.01  # floating point tolerance

    def test_combined_risk_exceeded(self):
        # Already at max risk
        plan = build_trade_plan(
            entry_price=2.02,
            stop_price=1.80,
            account_balance=10000,
            risk_pct=0.01,
            current_open_risk=800,
        )
        assert plan is None

    def test_allocation_cap(self):
        # Very cheap stock, would need 5000 shares but capped at 20%
        plan = build_trade_plan(
            entry_price=0.50,
            stop_price=0.48,
            account_balance=10000,
            risk_pct=0.01,
            max_position_pct=0.20,
        )
        # 100 / 0.02 = 5000 shares, but 20% cap = 2000 / 0.50 = 4000
        assert plan is not None
        assert plan["shares"] == 4000
        assert plan["position_value"] == 2000.0
