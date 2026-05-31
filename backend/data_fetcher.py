"""Data fetching utilities using yfinance."""

from __future__ import annotations

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)

# ~60 large-cap training tickers across sectors
TRAINING_TICKERS = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "ORCL", "CSCO", "INTC",
    "AMD", "QCOM", "TXN", "ADBE", "CRM", "AVGO", "NOW", "AMAT", "MU", "PANW",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "C", "AXP", "USB", "TFC",
    # Healthcare
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT", "DHR", "BMY",
    # Consumer
    "WMT", "HD", "MCD", "KO", "PEP", "COST", "NKE", "SBUX", "TGT", "LOW",
    # Industrials / Energy
    "XOM", "CVX", "CAT", "GE", "HON", "RTX", "LMT", "UPS", "DE", "COP",
    # Other
    "V", "MA", "PG", "DIS", "NFLX", "VZ", "NEE", "BRK-B", "T", "SPGI",
]

SECTOR_ETFS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Financial Services": "XLF",
    "Health Care": "XLV",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Utilities": "XLU",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Basic Materials": "XLB",
}

_ticker_sector_cache: dict[str, str] = {}


def get_ticker_info(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        return info
    except Exception as e:
        logger.warning(f"Could not fetch info for {ticker}: {e}")
        return {}


def get_sector_etf(ticker: str) -> str:
    if ticker in _ticker_sector_cache:
        return _ticker_sector_cache[ticker]
    try:
        info = get_ticker_info(ticker)
        sector = info.get("sector", "") or ""
        etf = SECTOR_ETFS.get(sector, "SPY")
        _ticker_sector_cache[ticker] = etf
        return etf
    except Exception:
        return "SPY"


def get_price_history(ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Download OHLCV price history, return DataFrame with DatetimeIndex."""
    try:
        df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception as e:
        logger.warning(f"Price download failed for {ticker}: {e}")
        return pd.DataFrame()


def get_earnings_history(ticker: str, limit: int = 24) -> pd.DataFrame:
    """
    Return DataFrame of past earnings events with columns:
      EPS Estimate, Reported EPS, Surprise(%), beat (0/1)
    Index: earnings date (tz-naive).
    """
    try:
        t = yf.Ticker(ticker)
        df = t.get_earnings_dates(limit=limit)
        if df is None or df.empty:
            return pd.DataFrame()

        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.sort_index(ascending=True)

        # keep only rows where we have both estimate and actual
        df = df.dropna(subset=["EPS Estimate", "Reported EPS"])

        # remove future dates
        df = df[df.index <= pd.Timestamp.now()]

        df["surprise_pct"] = df.get("Surprise(%)", (df["Reported EPS"] - df["EPS Estimate"]) / df["EPS Estimate"].abs() * 100)
        df["beat"] = (df["Reported EPS"] > df["EPS Estimate"]).astype(int)
        return df
    except Exception as e:
        logger.warning(f"Earnings history fetch failed for {ticker}: {e}")
        return pd.DataFrame()


def get_next_earnings_date(ticker: str) -> datetime | None:
    """Return the next upcoming earnings date for a ticker, or None."""
    try:
        t = yf.Ticker(ticker)
        df = t.get_earnings_dates(limit=8)
        if df is None or df.empty:
            return None

        df.index = pd.to_datetime(df.index).tz_localize(None)
        now = pd.Timestamp.now()
        future = df[df.index > now]
        if future.empty:
            return None
        return future.index.min().to_pydatetime()
    except Exception as e:
        logger.warning(f"Next earnings fetch failed for {ticker}: {e}")
        return None


def get_revenue_growth(ticker: str) -> float:
    """YoY revenue growth from most recent 4 quarters vs prior 4 quarters."""
    try:
        t = yf.Ticker(ticker)
        qs = t.quarterly_income_stmt
        if qs is None or qs.empty:
            return 0.0
        rev_row = None
        for label in ["Total Revenue", "Revenue", "Net Revenue"]:
            if label in qs.index:
                rev_row = qs.loc[label]
                break
        if rev_row is None:
            return 0.0
        rev_row = rev_row.dropna().sort_index(ascending=False)
        if len(rev_row) < 8:
            return 0.0
        recent_4 = rev_row.iloc[:4].sum()
        prior_4 = rev_row.iloc[4:8].sum()
        if prior_4 == 0:
            return 0.0
        return float((recent_4 - prior_4) / abs(prior_4))
    except Exception:
        return 0.0


def get_analyst_recommendation_score(ticker: str) -> float:
    """
    Convert analyst mean recommendation to a score.
    yfinance: 1=Strong Buy, 2=Buy, 3=Hold, 4=Sell, 5=Strong Sell
    We invert so higher = more bullish.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        rec = info.get("recommendationMean", 3.0) or 3.0
        return float(3.0 - rec)  # range ~[-2, 2], positive = bullish
    except Exception:
        return 0.0


def get_upcoming_earnings_for_calendar(tickers: list[str], days_ahead: int = 14) -> list[dict]:
    """Check a list of tickers for earnings in the next N days."""
    results = []
    cutoff = pd.Timestamp.now() + pd.Timedelta(days=days_ahead)
    now = pd.Timestamp.now()

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            df = t.get_earnings_dates(limit=8)
            if df is None or df.empty:
                continue
            df.index = pd.to_datetime(df.index).tz_localize(None)
            upcoming = df[(df.index > now) & (df.index <= cutoff)]
            if not upcoming.empty:
                edate = upcoming.index.min()
                results.append({"ticker": ticker, "earnings_date": edate.isoformat()})
            time.sleep(0.05)
        except Exception:
            continue
    return results
