"""
Hyperliquid API client — candle data, mids, metadata.

No auth needed for read-only market data.
"""

import time
import requests
import numpy as np
from dataclasses import dataclass

BASE_URL = "https://api.hyperliquid.xyz/info"


def _post(body: dict, timeout: int = 10) -> dict:
    """POST to Hyperliquid info endpoint."""
    resp = requests.post(
        BASE_URL,
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def get_all_mids() -> dict:
    """Get mid prices for all coins. Returns {coin: price_str}."""
    return _post({"type": "allMids"})


def get_meta() -> dict:
    """Get perpetuals metadata (universe + margin tables)."""
    return _post({"type": "meta"})


def get_meta_and_contexts() -> list:
    """Get metadata + asset contexts (mark price, funding, OI, volume)."""
    return _post({"type": "metaAndAssetCtxs"})


def get_candles(coin: str, interval: str = "1h", hours_back: int = 100) -> list:
    """
    Get OHLCV candle data.

    Args:
        coin: e.g. "BTC", "ETH", "SOL"
        interval: "1m","3m","5m","15m","30m","1h","2h","4h","8h","12h","1d","3d","1w","1M"
        hours_back: how many hours of data to fetch

    Returns list of candle dicts with keys: t, T, s, i, o, c, h, l, v, n
    """
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (hours_back * 3600 * 1000)

    return _post({
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": start_ms,
            "endTime": now_ms,
        }
    })


@dataclass
class CandleArray:
    """Candle data as numpy arrays for efficient computation."""
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    volumes: np.ndarray
    timestamps: np.ndarray

    @classmethod
    def from_api(cls, candles: list) -> "CandleArray":
        """Parse API response into numpy arrays."""
        if not candles:
            raise ValueError("No candle data")

        opens = np.array([float(c["o"]) for c in candles])
        highs = np.array([float(c["h"]) for c in candles])
        lows = np.array([float(c["l"]) for c in candles])
        closes = np.array([float(c["c"]) for c in candles])
        volumes = np.array([float(c["v"]) for c in candles])
        timestamps = np.array([int(c["t"]) for c in candles])

        return cls(opens=opens, highs=highs, lows=lows, closes=closes,
                   volumes=volumes, timestamps=timestamps)

    @property
    def last_price(self) -> float:
        return float(self.closes[-1])

    @property
    def last_volume(self) -> float:
        return float(self.volumes[-1])

    @property
    def avg_volume(self) -> float:
        return float(np.mean(self.volumes))

    def __len__(self):
        return len(self.closes)


def get_candle_array(coin: str, interval: str = "1h", hours_back: int = 100) -> CandleArray:
    """Get candles as numpy arrays. Main entry point for analysis."""
    candles = get_candles(coin, interval, hours_back)
    return CandleArray.from_api(candles)
