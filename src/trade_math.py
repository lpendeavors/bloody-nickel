"""
Trade math — position sizing, entry/stop calculation, risk management.

All formulas are explicit and testable. No magic numbers.
"""


def risk_per_share(entry: float, stop: float) -> float:
    """
    How much you lose per share if stopped out.

    Formula: entry_price - stop_price
    """
    if entry <= 0 or stop <= 0:
        raise ValueError("Entry and stop must be positive")
    if stop >= entry:
        raise ValueError("Stop must be below entry")
    return round(entry - stop, 4)


def acceptable_risk(account_balance: float, risk_pct: float) -> float:
    """
    Maximum dollar amount you're willing to lose on this trade.

    Formula: account_balance * risk_percent
    """
    if account_balance <= 0:
        raise ValueError("Account balance must be positive")
    if not (0 < risk_pct <= 0.05):
        raise ValueError("Risk percent must be between 0 and 5%")
    return round(account_balance * risk_pct, 2)


def shares_to_buy(accept_risk: float, rps: float) -> int:
    """
    Number of shares to buy based on risk.

    Formula: acceptable_risk / risk_per_share
    Rounded down (never round up — that increases risk).
    """
    if rps <= 0:
        raise ValueError("Risk per share must be positive")
    if accept_risk <= 0:
        raise ValueError("Acceptable risk must be positive")
    return int(accept_risk / rps)


def max_shares_by_allocation(account_balance: float, max_pct: float, entry: float) -> int:
    """
    Maximum shares based on position allocation cap.

    Formula: (account_balance * max_pct) / entry_price
    """
    if entry <= 0:
        raise ValueError("Entry must be positive")
    if not (0 < max_pct <= 1):
        raise ValueError("Max pct must be between 0 and 1")
    return int((account_balance * max_pct) / entry)


def position_value(shares: int, entry: float) -> float:
    """
    Total dollar value of the position.

    Formula: shares * entry_price
    """
    return round(shares * entry, 2)


def total_risk(shares: int, rps: float) -> float:
    """
    Total dollar risk on this trade.

    Formula: shares * risk_per_share
    """
    return round(shares * rps, 2)


def combined_risk_pct(current_risk_dollars: float, account_balance: float) -> float:
    """
    What percentage of account is at risk across all open trades.

    Formula: current_risk_dollars / account_balance
    """
    if account_balance <= 0:
        raise ValueError("Account balance must be positive")
    return round(current_risk_dollars / account_balance, 4)


def build_trade_plan(
    entry_price: float,
    stop_price: float,
    account_balance: float,
    risk_pct: float = 0.01,
    max_position_pct: float = 0.20,
    current_open_risk: float = 0,
) -> dict:
    """
    Build a complete trade plan from entry and stop prices.

    Returns dict with all trade details, or None if invalid.
    """
    try:
        rps = risk_per_share(entry_price, stop_price)
    except ValueError:
        return None

    # Cap risk at 25% of entry (stop too far away = bad setup)
    if rps > entry_price * 0.25:
        return None

    accept = acceptable_risk(account_balance, risk_pct)
    shares = shares_to_buy(accept, rps)
    max_by_alloc = max_shares_by_allocation(account_balance, max_position_pct, entry_price)
    shares = min(shares, max_by_alloc)

    if shares <= 0:
        return None

    # Check combined risk
    this_risk = total_risk(shares, rps)
    new_combined = current_open_risk + this_risk
    max_risk = account_balance * 0.08  # 8% max combined

    if new_combined > max_risk:
        # Reduce shares to fit within combined risk
        remaining_risk = max_risk - current_open_risk
        if remaining_risk <= 0:
            return None
        shares = int(remaining_risk / rps)
        if shares <= 0:
            return None
        this_risk = total_risk(shares, rps)

    return {
        "entry": round(entry_price, 4),
        "stop": round(stop_price, 4),
        "risk_per_share": rps,
        "shares": shares,
        "position_value": position_value(shares, entry_price),
        "total_risk": this_risk,
        "risk_pct_of_accept": round(this_risk / accept * 100, 1),
    }
