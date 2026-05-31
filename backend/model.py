"""XGBoost model for earnings beat/miss prediction."""
from __future__ import annotations

import os
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

from xgboost import XGBClassifier

from features import FEATURE_NAMES, FEATURE_DESCRIPTIONS

logger = logging.getLogger(__name__)

# On Vercel only /tmp is writable; fall back to local dir otherwise
_IS_VERCEL = os.environ.get("VERCEL") == "1"
MODEL_DIR = Path("/tmp/model_artifacts") if _IS_VERCEL else Path(__file__).parent / "model_artifacts"
MODEL_PATH = MODEL_DIR / "edgecall_model.joblib"
META_PATH = MODEL_DIR / "model_meta.joblib"


def get_confidence_tier(prob: float) -> str:
    distance = abs(prob - 0.5)
    if distance >= 0.15:
        return "High"
    elif distance >= 0.07:
        return "Medium"
    return "Low"


def _manual_cv_auc(clf, X: np.ndarray, y: np.ndarray, k: int = 5) -> np.ndarray:
    """K-fold CV returning per-fold ROC-AUC without sklearn dependency."""
    n = len(y)
    idx = np.random.default_rng(42).permutation(n)
    fold_size = n // k
    scores = []
    for i in range(k):
        val_idx = idx[i * fold_size: (i + 1) * fold_size]
        tr_idx = np.concatenate([idx[:i * fold_size], idx[(i + 1) * fold_size:]])
        clone = clf.__class__(**clf.get_params())
        clone.fit(X[tr_idx], y[tr_idx])
        probs = clone.predict_proba(X[val_idx])[:, 1]
        scores.append(_roc_auc(y[val_idx], probs))
    return np.array(scores)


def _roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Compute ROC-AUC via trapezoidal rule."""
    desc = np.argsort(-y_score)
    y_s = y_true[desc]
    tp = np.cumsum(y_s)
    fp = np.cumsum(1 - y_s)
    tp_rate = tp / (tp[-1] + 1e-9)
    fp_rate = fp / (fp[-1] + 1e-9)
    return float(abs(np.trapz(tp_rate, fp_rate)))


def build_summary(ticker: str, prob: float, features: dict, feature_importance: dict) -> str:
    pct = int(prob * 100)
    tier = get_confidence_tier(prob)
    direction = "beating" if prob >= 0.5 else "missing"

    # Find top 2 driving features
    top_feats = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:3]
    feat_phrases = []
    for fname, _ in top_feats:
        val = features.get(fname, 0)
        desc_map = {
            "recent_surprise_avg": f"{'strong' if val > 5 else 'weak'} recent EPS surprise history",
            "beat_miss_streak": f"{'beat' if val > 0 else 'miss'} streak of {abs(int(val))} quarters",
            "pre_earnings_drift_30d": f"{'positive' if val > 0 else 'negative'} pre-earnings price drift",
            "sector_momentum_30d": f"{'strong' if val > 0 else 'weak'} sector momentum",
            "eps_alpha_vs_market": f"{'outperforming' if val > 0 else 'underperforming'} the market",
            "revenue_growth": f"{'accelerating' if val > 0.1 else 'slowing'} revenue growth",
            "analyst_score": f"{'bullish' if val > 0 else 'bearish'} analyst consensus",
            "iv_rank_proxy": f"{'elevated' if val > 1.2 else 'calm'} implied volatility",
            "price_momentum_90d": f"{'strong' if val > 0.1 else 'weak'} 90-day momentum",
            "market_momentum_30d": f"{'rising' if val > 0 else 'falling'} broad market",
        }
        phrase = desc_map.get(fname, fname.replace("_", " "))
        feat_phrases.append(phrase)

    drivers = " and ".join(feat_phrases[:2])
    return (
        f"EdgeCall gives {ticker} a {pct}% chance of {direction} estimates "
        f"({tier} confidence) — driven by {drivers}."
    )


class EdgeCallModel:
    def __init__(self):
        self.model: XGBClassifier | None = None
        self.feature_importance: dict[str, float] = {}
        self.meta: dict = {}
        self.is_loaded = False

    def load(self) -> bool:
        if MODEL_PATH.exists() and META_PATH.exists():
            try:
                self.model = joblib.load(MODEL_PATH)
                self.meta = joblib.load(META_PATH)
                self.feature_importance = self.meta.get("feature_importance", {})
                self.is_loaded = True
                logger.info(f"Model loaded — trained on {self.meta.get('n_samples', '?')} samples")
                return True
            except Exception as e:
                logger.error(f"Model load failed: {e}")
        return False

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Train XGBoost and save to disk. Returns training metrics."""
        MODEL_DIR.mkdir(exist_ok=True)

        self.model = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )

        # Manual 5-fold CV AUC (no sklearn dependency)
        cv_scores = _manual_cv_auc(self.model, X, y, k=5)
        logger.info(f"CV AUC: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

        # Final fit on all data
        self.model.fit(X, y)

        importances = self.model.feature_importances_
        self.feature_importance = {
            name: float(imp) for name, imp in zip(FEATURE_NAMES, importances)
        }

        self.meta = {
            "trained_at": datetime.utcnow().isoformat(),
            "n_samples": int(len(y)),
            "n_features": int(X.shape[1]),
            "beat_rate": float(y.mean()),
            "cv_auc_mean": float(cv_scores.mean()),
            "cv_auc_std": float(cv_scores.std()),
            "feature_importance": self.feature_importance,
            "feature_names": FEATURE_NAMES,
        }

        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.meta, META_PATH)
        self.is_loaded = True

        return {
            "cv_auc": float(cv_scores.mean()),
            "n_samples": int(len(y)),
            "beat_rate": float(y.mean()),
        }

    def predict(self, X: np.ndarray) -> tuple[float, str]:
        """Return (beat_probability, confidence_tier)."""
        if not self.is_loaded or self.model is None:
            raise RuntimeError("Model not loaded")
        prob = float(self.model.predict_proba(X)[0][1])
        tier = get_confidence_tier(prob)
        return prob, tier

    def get_feature_importance(self) -> list[dict]:
        total = sum(self.feature_importance.values()) or 1
        return sorted(
            [
                {
                    "feature": k,
                    "importance": round(v / total * 100, 1),
                    "description": FEATURE_DESCRIPTIONS.get(k, k),
                }
                for k, v in self.feature_importance.items()
            ],
            key=lambda x: x["importance"],
            reverse=True,
        )


# Singleton
_model_instance: EdgeCallModel | None = None


def get_model() -> EdgeCallModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = EdgeCallModel()
        _model_instance.load()
    return _model_instance
