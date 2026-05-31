"""Feature engineering for the EdgeCall earnings beat/miss classifier."""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "pre_earnings_drift_30d",
    "iv_rank_proxy",
    "sector_momentum_30d",
    "market_momentum_30d",
    "beat_miss_streak",
    "recent_surprise_avg",
    "recent_surprise_std",
    "price_momentum_90d",
    "eps_alpha_vs_market",
    "revenue_growth",
    "analyst_score",
]

FEATURE_DESCRIPTIONS = {
    "pre_earnings_drift_30d": "Stock return in the 30 days leading up to earnings — positive drift often signals buy-side accumulation.",
    "iv_rank_proxy": "30-day realized volatility vs 1-year range. High rank means options are pricing in a big move.",
    "sector_momentum_30d": "How the stock's sector ETF has performed over the past 30 days.",
    "market_momentum_30d": "Broad market (S&P 500) return over the past 30 days — the rising tide effect.",
    "beat_miss_streak": "Consecutive quarters of beats (positive) or misses (negative). Streaks tend to persist.",
    "recent_surprise_avg": "Average EPS surprise % over the last 3 quarters. Shows whether the company consistently clears the bar.",
    "recent_surprise_std": "Variability in recent EPS surprises — high std means unpredictable beats/misses.",
    "price_momentum_90d": "Stock return over the prior 90 days — medium-term momentum often reflects fundamental trends.",
    "eps_alpha_vs_market": "Stock's 30-day return minus market return — how much is company-specific vs macro.",
    "revenue_growth": "Year-over-year revenue growth from the most recent 4 quarters vs prior 4 quarters.",
    "analyst_score": "Analyst consensus signal: positive = bullish recommendations, negative = bearish.",
}


def _pct_return(series: pd.Series, lookback_trading_days: int) -> float:
    """Return the percentage return over the last N trading days in series."""
    s = series.dropna()
    if len(s) < 5:
        return 0.0
    n = min(lookback_trading_days, len(s) - 1)
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1)


def _realized_vol(returns: pd.Series, window: int) -> float:
    r = returns.dropna()
    if len(r) < 5:
        return 0.01
    r = r.iloc[-window:]
    return float(r.std() * np.sqrt(252))


def compute_beat_miss_streak(earnings_df: pd.DataFrame, before_date: pd.Timestamp) -> int:
    """Count consecutive beats (positive) or misses (negative) strictly before before_date."""
    past = earnings_df[earnings_df.index < before_date].sort_index(ascending=False)
    if past.empty:
        return 0
    streak = 0
    expected_beat = int(past.iloc[0]["beat"])
    for _, row in past.iterrows():
        b = int(row["beat"])
        if b == expected_beat:
            streak += 1 if expected_beat == 1 else -1
        else:
            break
    return streak


def compute_features_for_event(
    earnings_date: pd.Timestamp,
    price_data: pd.DataFrame,
    sector_data: pd.DataFrame,
    spy_data: pd.DataFrame,
    earnings_history: pd.DataFrame,
    revenue_growth: float = 0.0,
    analyst_score: float = 0.0,
) -> dict[str, float]:
    """
    Compute all features for a single earnings event.
    All price data must cover at least 1 year before earnings_date.
    """
    cutoff = earnings_date - pd.Timedelta(days=1)

    # Slice price data up to cutoff
    px = price_data[price_data.index <= cutoff]["Close"].dropna()
    sx = sector_data[sector_data.index <= cutoff]["Close"].dropna() if not sector_data.empty else pd.Series(dtype=float)
    mx = spy_data[spy_data.index <= cutoff]["Close"].dropna() if not spy_data.empty else pd.Series(dtype=float)

    # --- Feature 1: pre-earnings drift 30d ---
    pre_drift_30d = _pct_return(px, 22)  # ~22 trading days = 30 calendar

    # --- Feature 2: IV rank proxy ---
    if len(px) >= 60:
        daily_returns = px.pct_change().dropna()
        vol_30d = _realized_vol(daily_returns, 22)
        vol_252d = _realized_vol(daily_returns, 252)
        iv_rank_proxy = vol_30d / vol_252d if vol_252d > 0 else 1.0
    else:
        iv_rank_proxy = 1.0

    # --- Feature 3: sector momentum 30d ---
    sector_momentum = _pct_return(sx, 22) if len(sx) >= 10 else 0.0

    # --- Feature 4: market momentum 30d ---
    market_momentum = _pct_return(mx, 22) if len(mx) >= 10 else 0.0

    # --- Feature 5: beat/miss streak ---
    streak = compute_beat_miss_streak(earnings_history, earnings_date)

    # --- Features 6 & 7: recent surprise avg and std ---
    past_earnings = earnings_history[earnings_history.index < earnings_date].sort_index()
    if not past_earnings.empty:
        recent = past_earnings["surprise_pct"].iloc[-3:]
        recent_avg = float(recent.mean()) if not recent.empty else 0.0
        recent_std = float(recent.std()) if len(recent) > 1 else 0.0
    else:
        recent_avg = 0.0
        recent_std = 0.0

    # clamp to reasonable range
    recent_avg = np.clip(recent_avg, -50, 50)

    # --- Feature 8: 90d price momentum ---
    momentum_90d = _pct_return(px, 65)  # ~65 trading days = 90 calendar

    # --- Feature 9: alpha vs market ---
    eps_alpha = pre_drift_30d - market_momentum

    return {
        "pre_earnings_drift_30d": float(np.clip(pre_drift_30d, -0.5, 0.5)),
        "iv_rank_proxy": float(np.clip(iv_rank_proxy, 0.1, 5.0)),
        "sector_momentum_30d": float(np.clip(sector_momentum, -0.3, 0.3)),
        "market_momentum_30d": float(np.clip(market_momentum, -0.3, 0.3)),
        "beat_miss_streak": float(np.clip(streak, -8, 8)),
        "recent_surprise_avg": float(np.clip(recent_avg, -50, 50)),
        "recent_surprise_std": float(np.clip(recent_std, 0, 30)),
        "price_momentum_90d": float(np.clip(momentum_90d, -0.6, 0.6)),
        "eps_alpha_vs_market": float(np.clip(eps_alpha, -0.4, 0.4)),
        "revenue_growth": float(np.clip(revenue_growth, -1.0, 2.0)),
        "analyst_score": float(np.clip(analyst_score, -2.5, 2.5)),
    }


def features_to_array(features: dict[str, float]) -> np.ndarray:
    """Convert feature dict to numpy array in canonical order."""
    return np.array([features.get(k, 0.0) for k in FEATURE_NAMES], dtype=np.float32).reshape(1, -1)
