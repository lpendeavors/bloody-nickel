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
pip install yfinance requests numpy
python src/screener.py          # Penny stock scan
python src/crypto_scan.py       # Hyperliquid crypto scan
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

## Hyperliquid Crypto Scanner

Scans top perp pairs for confluence signals (3+ required):
- RSI(14) oversold/momentum on 4H and 1H
- Volume spike ≥ 2x the 20-period average
- VWAP bounce (within 1%)
- EMA 9/21 crossover on 4H
- Liquidity sweep (stop hunt reversal)
- Order block return

Kill switches:
- No trading 2-5am UTC (low liquidity)
- 3% daily drawdown → stop
- 2 consecutive losses → 1hr cooldown
