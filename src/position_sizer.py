"""
Position sizer for Hyperliquid trades.

Same math as penny stocks but adapted for perps:
- Risk-based sizing (not allocation-based)
- Leverage-aware
- Entry/stop/target calculated before you enter
"""

import json
import os
from dataclasses import dataclass


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "crypto.json")
    with open(config_path) as f:
        return json.load(f)


@dataclass
class TradePlan:
    """Complete trade plan — everything you need before clicking."""
    coin: str
    direction: str
    entry: float
    stop: float
    target_1: float
    target_2: float
    units: int
    position_value: float
    leverage: float
    risk_per_unit: float
    total_risk: float
    risk_pct: float
    mechanics: list
    score: int

    def summary(self) -> str:
        emoji = "🟢" if self.direction == "long" else "🔴"
        lines = [
            f"{emoji} **{self.coin}** — {self.direction.upper()}",
            f"Entry: `${self.entry}`",
            f"Stop: `${self.stop}` (${self.risk_per_unit}/unit)",
            f"T1: `${self.target_1}` | T2: `${self.target_2}`",
            f"Units: {self.units:,} | Value: ${self.position_value:,.2f}",
            f"Leverage: {self.leverage:.1f}x",
            f"Risk: ${self.total_risk:.2f} ({self.risk_pct:.1f}% of account)",
            f"R:R: {round(abs(self.target_1 - self.entry) / self.risk_per_unit, 2)}",
            f"Score: {self.score} | {' · '.join(self.mechanics)}",
        ]
        return "\n".join(lines)


def size_trade(
    coin: str,
    direction: str,
    entry: float,
    stop: float,
    target_1: float,
    target_2: float,
    mechanics: list,
    score: int,
    config: dict = None,
) -> TradePlan | None:
    """
    Size a trade based on risk.
    
    Formula: units = floor(acceptable_risk / risk_per_unit)
    Then check leverage cap.
    """
    if config is None:
        config = load_config()
    
    balance = config["account_balance"]
    risk_pct = config["risk_per_trade_pct"]
    max_leverage = config.get("max_leverage", 5)
    
    # Risk per unit
    if direction == "long":
        rps = entry - stop
    else:
        rps = stop - entry
    
    if rps <= 0:
        return None
    
    # How much can we risk?
    acceptable_risk = balance * risk_pct
    
    # How many units?
    units = int(acceptable_risk / rps)
    if units <= 0:
        return None
    
    # Check leverage
    position_value = units * entry
    leverage = position_value / balance
    
    if leverage > max_leverage:
        # Cap at max leverage
        units = int((balance * max_leverage) / entry)
        position_value = units * entry
        leverage = position_value / balance
    
    total_risk = units * rps
    actual_risk_pct = (total_risk / balance) * 100
    
    return TradePlan(
        coin=coin,
        direction=direction,
        entry=round(entry, 6),
        stop=round(stop, 6),
        target_1=round(target_1, 6),
        target_2=round(target_2, 6),
        units=units,
        position_value=round(position_value, 2),
        leverage=round(leverage, 2),
        risk_per_unit=round(rps, 6),
        total_risk=round(total_risk, 2),
        risk_pct=round(actual_risk_pct, 2),
        mechanics=mechanics,
        score=score,
    )
