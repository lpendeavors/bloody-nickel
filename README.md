# Bloody Nickel — Penny Stock Screener

Daily penny stock screener for Larry's trading criteria.

## Criteria

**Entry signal:** Trend change + at least one of:
- Volume/price spike (1.5x+ average)
- Float < 30M
- Short float > 20%
- Interesting business story (manual review)

**Financials:**
- No evidence of dilution
- Sign of hope in financials
- No overtly promotional news
- No troubling SEC filings

**Tradable patterns:**
- Breakout of resistance
- Flag pattern
- Trend-change gap
- Cup-and-handle

**Risk management:**
- 1% risk per trade
- 20% max position allocation
- 6-8% max combined account risk

## Setup

```bash
pip install yfinance
python src/screener.py
```

## Testing

```bash
python -m pytest tests/ -v
```

## Config

Edit `config/settings.json` to adjust:
- Account balance
- Risk percentage
- Float threshold
- Short interest threshold
