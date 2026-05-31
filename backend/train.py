"""
Training script for EdgeCall.
Run once to build model_artifacts/edgecall_model.joblib

Usage:
    python train.py
    python train.py --tickers AAPL MSFT NVDA  # subset for quick test
"""

import argparse
import logging
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from data_fetcher import (
    TRAINING_TICKERS,
    get_price_history,
    get_earnings_history,
    get_sector_etf,
    get_revenue_growth,
    get_analyst_recommendation_score,
)
from features import compute_features_for_event, FEATURE_NAMES
from model import get_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def build_training_data(tickers: list[str]) -> tuple[np.ndarray, np.ndarray]:
    all_X = []
    all_y = []

    # Pre-download SPY for market momentum
    train_end = datetime.today()
    train_start = train_end - timedelta(days=365 * 7)

    logger.info("Downloading SPY (market benchmark)...")
    spy_data = get_price_history("SPY", train_start, train_end)

    for i, ticker in enumerate(tickers):
        logger.info(f"[{i+1}/{len(tickers)}] Processing {ticker}...")
        try:
            # Earnings history
            earnings = get_earnings_history(ticker, limit=28)
            if earnings.empty or len(earnings) < 4:
                logger.warning(f"  {ticker}: insufficient earnings data, skipping")
                continue

            # Price history (7 years for features)
            price_data = get_price_history(ticker, train_start, train_end)
            if price_data.empty:
                logger.warning(f"  {ticker}: no price data, skipping")
                continue

            # Sector ETF
            sector_etf = get_sector_etf(ticker)
            sector_data = get_price_history(sector_etf, train_start, train_end)

            # Revenue growth and analyst score (current, used as static feature for all events)
            rev_growth = get_revenue_growth(ticker)
            analyst_score = get_analyst_recommendation_score(ticker)

            n_events = 0
            for edate in earnings.index:
                # Skip earnings with insufficient prior history
                lookback_start = edate - pd.Timedelta(days=400)
                px_slice = price_data[price_data.index >= lookback_start]
                if len(px_slice) < 60:
                    continue

                feats = compute_features_for_event(
                    earnings_date=edate,
                    price_data=price_data,
                    sector_data=sector_data,
                    spy_data=spy_data,
                    earnings_history=earnings,
                    revenue_growth=rev_growth,
                    analyst_score=analyst_score,
                )
                label = int(earnings.loc[edate, "beat"])
                all_X.append([feats[k] for k in FEATURE_NAMES])
                all_y.append(label)
                n_events += 1

            logger.info(f"  {ticker}: {n_events} earnings events processed")
            time.sleep(0.2)  # be nice to yfinance

        except Exception as e:
            logger.error(f"  {ticker}: FAILED — {e}")
            continue

    X = np.array(all_X, dtype=np.float32)
    y = np.array(all_y, dtype=np.int32)
    logger.info(f"Total training samples: {len(y)} | Beat rate: {y.mean():.1%}")
    return X, y


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="*", default=None, help="Subset of tickers (default: all)")
    args = parser.parse_args()

    tickers = args.tickers if args.tickers else TRAINING_TICKERS
    logger.info(f"Training on {len(tickers)} tickers...")

    X, y = build_training_data(tickers)

    if len(y) < 50:
        logger.error("Not enough training samples. Need at least 50.")
        return

    model = get_model()
    metrics = model.train(X, y)
    logger.info(f"Training complete!")
    logger.info(f"  CV AUC:    {metrics['cv_auc']:.3f}")
    logger.info(f"  Samples:   {metrics['n_samples']}")
    logger.info(f"  Beat rate: {metrics['beat_rate']:.1%}")
    logger.info("Model saved to backend/model_artifacts/")


if __name__ == "__main__":
    main()
