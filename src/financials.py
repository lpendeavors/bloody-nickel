"""
Financial analysis — dilution, hope, debt, scoring.
"""


def check_dilution(float_m: float) -> bool:
    """
    Check for possible dilution.
    Very high float relative to market cap can indicate dilution.
    Returns True if dilution is suspected.
    """
    return float_m > 50


def check_financials_hope(info: dict) -> bool:
    """
    Check for any sign of hope in financials.
    Returns True if there's positive signal.
    """
    revenue_growth = info.get("revenueGrowth", 0) or 0
    earnings_growth = info.get("earningsGrowth", 0) or 0
    gross_margins = info.get("grossMargins", 0) or 0
    profit_margins = info.get("profitMargins", 0) or 0

    return any([
        revenue_growth > 0,
        earnings_growth > 0,
        gross_margins > 0.2,
        profit_margins > 0,
    ])


def check_debt_concern(info: dict) -> bool:
    """
    Check if debt is a concern.
    Returns True if debt/revenue ratio is alarming.
    """
    debt = info.get("totalDebt", 0) or 0
    revenue = info.get("totalRevenue", 0) or 0
    if debt <= 0 or revenue <= 0:
        return False
    return debt / revenue > 5


def score_candidate(
    trend_change: bool,
    has_volume_spike: bool,
    has_low_float: bool,
    has_high_short: bool,
    dilution_flag: bool,
    financials_hope: bool,
    debt_concern: bool,
    patterns: list,
) -> tuple:
    """
    Score a candidate (0-16 scale).
    Returns (score, list_of_flags).
    """
    score = 0
    flags = []

    if not trend_change:
        return 0, ["❌ No trend change"]

    # Required: trend change
    score += 2
    flags.append("✅ Trend change")

    # Indicators
    if has_volume_spike:
        score += 2
        flags.append("✅ Volume spike")
    if has_low_float:
        score += 2
        flags.append("✅ Low float")
    if has_high_short:
        score += 2
        flags.append("✅ High short")

    # Financials
    if not dilution_flag:
        score += 1
        flags.append("✅ No dilution")
    else:
        flags.append("⚠️ Possible dilution")

    if financials_hope:
        score += 1
        flags.append("✅ Financials hopeful")
    if debt_concern:
        score -= 1
        flags.append("❌ High debt")

    # Patterns
    for p in patterns:
        score += 2
        flags.append(f"✅ {p['type']}")

    return score, flags
