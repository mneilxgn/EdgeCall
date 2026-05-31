"""
Generate synthetic but statistically realistic training data for EdgeCall.
Uses known empirical relationships between earnings beat signals.

Run this when Yahoo Finance is rate-limited or for quick demos.
Real model training: python train.py (requires Yahoo Finance access).
"""
from __future__ import annotations

import numpy as np
import logging
from model import get_model
from features import FEATURE_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RNG = np.random.default_rng(42)
N_SAMPLES = 2000  # simulates ~60 tickers x ~33 quarters each


def generate_sample() -> tuple[np.ndarray, int]:
    """
    Generate one synthetic earnings event with realistic feature correlations.

    Empirical priors from academic literature:
    - S&P 500 large caps beat EPS ~72% of the time
    - Pre-earnings drift, recent surprises, and beat streak are predictive
    - Sector and market momentum have modest positive effects
    """
    # ---- latent "company quality" signal (drives most of the beating tendency)
    quality = RNG.normal(0, 1)

    # 1. pre_earnings_drift_30d
    pre_drift = np.clip(quality * 0.03 + RNG.normal(0, 0.06), -0.4, 0.4)

    # 2. iv_rank_proxy (higher before uncertain beats)
    iv_rank = np.clip(abs(quality) * 0.3 + 0.7 + RNG.exponential(0.3), 0.3, 4.0)

    # 3. sector_momentum_30d
    sector_mom = np.clip(RNG.normal(0.005, 0.04), -0.25, 0.25)

    # 4. market_momentum_30d
    market_mom = np.clip(RNG.normal(0.005, 0.035), -0.25, 0.25)

    # 5. beat_miss_streak (correlated with quality)
    streak_raw = quality * 1.5 + RNG.normal(0, 1.5)
    streak = int(np.clip(np.round(streak_raw), -8, 8))

    # 6. recent_surprise_avg (strongly correlated with quality)
    surprise_avg = np.clip(quality * 4 + RNG.normal(0, 5), -30, 30)

    # 7. recent_surprise_std
    surprise_std = np.clip(abs(RNG.normal(3, 3)), 0, 20)

    # 8. price_momentum_90d
    momentum_90d = np.clip(quality * 0.06 + RNG.normal(0, 0.12), -0.5, 0.5)

    # 9. eps_alpha_vs_market
    eps_alpha = np.clip(pre_drift - market_mom + RNG.normal(0, 0.02), -0.35, 0.35)

    # 10. revenue_growth
    rev_growth = np.clip(quality * 0.08 + RNG.normal(0.05, 0.12), -0.8, 1.5)

    # 11. analyst_score
    analyst = np.clip(quality * 0.5 + RNG.normal(0, 0.5), -2.5, 2.5)

    features = np.array([
        pre_drift, iv_rank, sector_mom, market_mom,
        float(streak), surprise_avg, surprise_std, momentum_90d,
        eps_alpha, rev_growth, analyst,
    ], dtype=np.float32)

    # Beat probability via logistic regression on latent signal + noise
    log_odds = (
        0.6               # baseline (companies beat ~72% of the time)
        + 1.2 * quality   # core quality
        + 0.4 * (surprise_avg / 10)
        + 0.3 * float(streak) / 4
        + 0.2 * (pre_drift / 0.1)
        + 0.15 * (rev_growth / 0.2)
        + 0.1 * analyst
        + RNG.normal(0, 0.5)   # noise
    )
    prob_beat = 1 / (1 + np.exp(-log_odds))
    label = int(RNG.random() < prob_beat)

    return features, label


def main():
    logger.info(f"Generating {N_SAMPLES} synthetic training samples...")
    X_list, y_list = [], []
    for _ in range(N_SAMPLES):
        x, y = generate_sample()
        X_list.append(x)
        y_list.append(y)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    logger.info(f"Beat rate: {y.mean():.1%} (expected ~72%)")

    model = get_model()
    metrics = model.train(X, y)
    logger.info("Synthetic model trained!")
    logger.info(f"  CV AUC:  {metrics['cv_auc']:.3f}  (limited by synthetic data quality)")
    logger.info(f"  Samples: {metrics['n_samples']}")
    logger.info("")
    logger.info("⚠️  This model is trained on SYNTHETIC data for demo purposes.")
    logger.info("   For production accuracy, run: python train.py")
    logger.info("   (requires Yahoo Finance API access — no rate limit)")


if __name__ == "__main__":
    main()
