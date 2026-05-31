"""Logistic regression model for EdgeCall earnings beat/miss prediction.
Pure numpy — no XGBoost/sklearn/scipy so the Vercel bundle stays under 500MB.
"""
from __future__ import annotations

import os
import joblib
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

from features import FEATURE_NAMES, FEATURE_DESCRIPTIONS

logger = logging.getLogger(__name__)

_IS_VERCEL = os.environ.get("VERCEL") == "1"
MODEL_DIR = Path("/tmp/model_artifacts") if _IS_VERCEL else Path(__file__).parent / "model_artifacts"
MODEL_PATH = MODEL_DIR / "edgecall_model.joblib"
META_PATH  = MODEL_DIR / "model_meta.joblib"


# ---------------------------------------------------------------------------
# Pure-numpy logistic regression with L2 regularisation
# ---------------------------------------------------------------------------

class _LogisticRegression:
    """Gradient-descent logistic regression. No scipy/sklearn dependency."""

    def __init__(self, lr: float = 0.05, n_iter: int = 2000, l2: float = 0.01):
        self.lr = lr
        self.n_iter = n_iter
        self.l2 = l2
        self.weights: np.ndarray | None = None
        self.bias: float = 0.0
        # store normalisation params so we can scale at predict time
        self.mean_: np.ndarray | None = None
        self.std_:  np.ndarray | None = None

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        # z-score normalise
        self.mean_ = X.mean(axis=0)
        self.std_  = X.std(axis=0) + 1e-8
        Xn = (X - self.mean_) / self.std_

        n, m = Xn.shape
        self.weights = np.zeros(m)
        self.bias    = 0.0

        for _ in range(self.n_iter):
            pred  = self._sigmoid(Xn @ self.weights + self.bias)
            error = pred - y
            self.weights -= self.lr * (Xn.T @ error / n + self.l2 * self.weights)
            self.bias    -= self.lr * error.mean()

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Xn   = (X - self.mean_) / self.std_
        prob = self._sigmoid(Xn @ self.weights + self.bias)
        return np.column_stack([1 - prob, prob])

    @property
    def feature_importances_(self) -> np.ndarray:
        w = np.abs(self.weights)
        return w / (w.sum() + 1e-9)

    def get_params(self) -> dict:
        return {"lr": self.lr, "n_iter": self.n_iter, "l2": self.l2}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_confidence_tier(prob: float) -> str:
    d = abs(prob - 0.5)
    if d >= 0.15:  return "High"
    if d >= 0.07:  return "Medium"
    return "Low"


def _roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    desc = np.argsort(-y_score)
    yt   = y_true[desc]
    tp   = np.cumsum(yt);        fp = np.cumsum(1 - yt)
    tpr  = tp / (tp[-1] + 1e-9); fpr = fp / (fp[-1] + 1e-9)
    return float(abs(np.trapz(tpr, fpr)))


def _cv_auc(clf_factory, X: np.ndarray, y: np.ndarray, k: int = 5) -> np.ndarray:
    idx  = np.random.default_rng(42).permutation(len(y))
    fold = len(y) // k
    scores = []
    for i in range(k):
        val = idx[i*fold:(i+1)*fold]
        tr  = np.concatenate([idx[:i*fold], idx[(i+1)*fold:]])
        m   = clf_factory()
        m.fit(X[tr], y[tr])
        scores.append(_roc_auc(y[val], m.predict_proba(X[val])[:, 1]))
    return np.array(scores)


def build_summary(ticker: str, prob: float, features: dict, feature_importance: dict) -> str:
    pct  = int(prob * 100)
    tier = get_confidence_tier(prob)
    direction = "beating" if prob >= 0.5 else "missing"

    top = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:3]
    phrases = []
    for fname, _ in top:
        val = features.get(fname, 0)
        desc_map = {
            "recent_surprise_avg":   f"{'strong' if val > 5 else 'weak'} recent EPS surprise history",
            "beat_miss_streak":      f"{'beat' if val > 0 else 'miss'} streak of {abs(int(val))} quarters",
            "pre_earnings_drift_30d":f"{'positive' if val > 0 else 'negative'} pre-earnings price drift",
            "sector_momentum_30d":   f"{'strong' if val > 0 else 'weak'} sector momentum",
            "eps_alpha_vs_market":   f"{'outperforming' if val > 0 else 'underperforming'} the market",
            "revenue_growth":        f"{'accelerating' if val > 0.1 else 'slowing'} revenue growth",
            "analyst_score":         f"{'bullish' if val > 0 else 'bearish'} analyst consensus",
            "iv_rank_proxy":         f"{'elevated' if val > 1.2 else 'calm'} implied volatility",
            "price_momentum_90d":    f"{'strong' if val > 0.1 else 'weak'} 90-day momentum",
            "market_momentum_30d":   f"{'rising' if val > 0 else 'falling'} broad market",
        }
        phrases.append(desc_map.get(fname, fname.replace("_", " ")))

    drivers = " and ".join(phrases[:2])
    return (
        f"EdgeCall gives {ticker} a {pct}% chance of {direction} estimates "
        f"({tier} confidence) — driven by {drivers}."
    )


# ---------------------------------------------------------------------------
# Model wrapper
# ---------------------------------------------------------------------------

class EdgeCallModel:
    def __init__(self):
        self.model: _LogisticRegression | None = None
        self.feature_importance: dict[str, float] = {}
        self.meta: dict = {}
        self.is_loaded = False

    def load(self) -> bool:
        if MODEL_PATH.exists() and META_PATH.exists():
            try:
                self.model = joblib.load(MODEL_PATH)
                self.meta  = joblib.load(META_PATH)
                self.feature_importance = self.meta.get("feature_importance", {})
                self.is_loaded = True
                logger.info(f"Model loaded — {self.meta.get('n_samples','?')} samples, AUC {self.meta.get('cv_auc_mean',0):.3f}")
                return True
            except Exception as e:
                logger.error(f"Model load failed: {e}")
        return False

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        MODEL_DIR.mkdir(exist_ok=True)

        def factory():
            return _LogisticRegression(lr=0.05, n_iter=2000, l2=0.01)

        cv_scores = _cv_auc(factory, X, y, k=5)
        logger.info(f"CV AUC: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

        self.model = factory()
        self.model.fit(X, y)

        importances = self.model.feature_importances_
        self.feature_importance = {
            name: float(imp) for name, imp in zip(FEATURE_NAMES, importances)
        }
        self.meta = {
            "trained_at":   datetime.utcnow().isoformat(),
            "n_samples":    int(len(y)),
            "n_features":   int(X.shape[1]),
            "beat_rate":    float(y.mean()),
            "cv_auc_mean":  float(cv_scores.mean()),
            "cv_auc_std":   float(cv_scores.std()),
            "feature_importance": self.feature_importance,
            "feature_names": FEATURE_NAMES,
        }

        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.meta,  META_PATH)
        self.is_loaded = True
        return {"cv_auc": float(cv_scores.mean()), "n_samples": int(len(y)), "beat_rate": float(y.mean())}

    def predict(self, X: np.ndarray) -> tuple[float, str]:
        if not self.is_loaded or self.model is None:
            raise RuntimeError("Model not loaded")
        prob = float(self.model.predict_proba(X)[0][1])
        return prob, get_confidence_tier(prob)

    def get_feature_importance(self) -> list[dict]:
        total = sum(self.feature_importance.values()) or 1
        return sorted(
            [{"feature": k, "importance": round(v / total * 100, 1),
              "description": FEATURE_DESCRIPTIONS.get(k, k)}
             for k, v in self.feature_importance.items()],
            key=lambda x: x["importance"], reverse=True,
        )


_model_instance: EdgeCallModel | None = None

def get_model() -> EdgeCallModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = EdgeCallModel()
        _model_instance.load()
    return _model_instance
