"""EdgeCall FastAPI backend."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_fetcher import (
    TRAINING_TICKERS,
    get_earnings_history,
    get_next_earnings_date,
    get_price_history,
    get_sector_etf,
    get_revenue_growth,
    get_analyst_recommendation_score,
    get_ticker_info,
    get_upcoming_earnings_for_calendar,
)
from features import compute_features_for_event, FEATURE_NAMES, FEATURE_DESCRIPTIONS
from model import get_model, build_summary, get_confidence_tier

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Startup ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    model = get_model()
    if not model.is_loaded:
        logger.warning("Model not found. Run `python train.py` to train the model first.")
    yield


app = FastAPI(title="EdgeCall API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic schemas ---


class PredictionResponse(BaseModel):
    ticker: str
    company_name: str
    next_earnings_date: Optional[str]
    beat_probability: float
    confidence_tier: str
    summary: str
    features: dict[str, float]
    feature_descriptions: dict[str, str]
    model_ready: bool
    data_warning: Optional[str] = None


class HistoricalAccuracyResponse(BaseModel):
    ticker: str
    events: list[dict]
    overall_accuracy: float
    n_predictions: int


class CalendarEntry(BaseModel):
    ticker: str
    company_name: str
    earnings_date: str
    beat_probability: float
    confidence_tier: str


class FeatureImportanceResponse(BaseModel):
    features: list[dict]
    model_meta: dict


class TrainStatus(BaseModel):
    status: str
    message: str


# --- Helpers ---

_spy_cache: dict = {}


def get_spy_data() -> pd.DataFrame:
    global _spy_cache
    now = time.time()
    if _spy_cache.get("ts", 0) > now - 3600 and not _spy_cache.get("data", pd.DataFrame()).empty:
        return _spy_cache["data"]
    end = datetime.today()
    start = end - timedelta(days=365 * 2)
    data = get_price_history("SPY", start, end)
    _spy_cache = {"data": data, "ts": now}
    return data


def compute_current_features(ticker: str) -> tuple[dict, pd.DataFrame, Optional[str]]:
    """
    Compute real-time features for next earnings prediction.
    Returns (features, earnings_history, warning_message_or_None).
    """
    end = datetime.today()
    start = end - timedelta(days=365 * 3)

    data_warning = None
    price_data = get_price_history(ticker, start, end)
    if price_data.empty:
        data_warning = "Yahoo Finance data temporarily unavailable (rate limited). Prediction uses neutral signals — try again in a few minutes for real data."
        # Return neutral features
        neutral = {k: 0.0 for k in FEATURE_NAMES}
        return neutral, pd.DataFrame(), data_warning

    sector_etf = get_sector_etf(ticker)
    sector_data = get_price_history(sector_etf, start, end)
    spy_data = get_spy_data()

    earnings_history = get_earnings_history(ticker, limit=20)
    rev_growth = get_revenue_growth(ticker)
    analyst_score = get_analyst_recommendation_score(ticker)

    # Use today as the "earnings date" for real-time prediction
    today = pd.Timestamp.now().normalize()

    feats = compute_features_for_event(
        earnings_date=today,
        price_data=price_data,
        sector_data=sector_data,
        spy_data=spy_data,
        earnings_history=earnings_history,
        revenue_growth=rev_growth,
        analyst_score=analyst_score,
    )
    return feats, earnings_history, data_warning


# --- Routes ---


@app.get("/api/health")
def health():
    model = get_model()
    return {
        "status": "ok",
        "model_ready": model.is_loaded,
        "model_meta": model.meta if model.is_loaded else {},
    }


@app.get("/api/predict/{ticker}", response_model=PredictionResponse)
def predict(ticker: str):
    ticker = ticker.upper().strip()
    model = get_model()

    # Get company info
    try:
        info = get_ticker_info(ticker)
        company_name = info.get("longName") or info.get("shortName") or ticker
    except Exception:
        company_name = ticker

    # Next earnings date
    next_earnings = get_next_earnings_date(ticker)

    if not model.is_loaded:
        return PredictionResponse(
            ticker=ticker,
            company_name=company_name,
            next_earnings_date=next_earnings.isoformat() if next_earnings else None,
            beat_probability=0.5,
            confidence_tier="Low",
            summary="Model not trained yet. Run `python train.py` in the backend directory.",
            features={},
            feature_descriptions=FEATURE_DESCRIPTIONS,
            model_ready=False,
        )

    feats, _, data_warning = compute_current_features(ticker)
    X = np.array([[feats[k] for k in FEATURE_NAMES]], dtype=np.float32)
    prob, tier = model.predict(X)

    summary = build_summary(ticker, prob, feats, model.feature_importance)
    if data_warning:
        tier = "Low"

    return PredictionResponse(
        ticker=ticker,
        company_name=company_name,
        next_earnings_date=next_earnings.isoformat() if next_earnings else None,
        beat_probability=round(prob, 4),
        confidence_tier=tier,
        summary=summary,
        features=feats,
        feature_descriptions=FEATURE_DESCRIPTIONS,
        model_ready=True,
        data_warning=data_warning,
    )


@app.get("/api/accuracy/{ticker}", response_model=HistoricalAccuracyResponse)
def historical_accuracy(ticker: str):
    ticker = ticker.upper().strip()
    model = get_model()

    earnings = get_earnings_history(ticker, limit=20)
    if earnings.empty:
        raise HTTPException(status_code=404, detail=f"No earnings history found for {ticker}")

    if not model.is_loaded:
        return HistoricalAccuracyResponse(
            ticker=ticker,
            events=[],
            overall_accuracy=0.0,
            n_predictions=0,
        )

    end = datetime.today()
    start = end - timedelta(days=365 * 7)
    price_data = get_price_history(ticker, start, end)
    sector_etf = get_sector_etf(ticker)
    sector_data = get_price_history(sector_etf, start, end)
    spy_data = get_spy_data()
    rev_growth = get_revenue_growth(ticker)
    analyst_score = get_analyst_recommendation_score(ticker)

    events = []
    correct = 0
    for edate in earnings.index:
        px_slice = price_data[price_data.index >= edate - pd.Timedelta(days=400)]
        if len(px_slice) < 60:
            continue

        try:
            feats = compute_features_for_event(
                earnings_date=edate,
                price_data=price_data,
                sector_data=sector_data,
                spy_data=spy_data,
                earnings_history=earnings,
                revenue_growth=rev_growth,
                analyst_score=analyst_score,
            )
            X = np.array([[feats[k] for k in FEATURE_NAMES]], dtype=np.float32)
            prob, tier = model.predict(X)
            actual_beat = int(earnings.loc[edate, "beat"])
            predicted_beat = 1 if prob >= 0.5 else 0
            is_correct = predicted_beat == actual_beat
            if is_correct:
                correct += 1

            surprise_pct = float(earnings.loc[edate, "surprise_pct"])

            events.append(
                {
                    "date": edate.strftime("%Y-%m-%d"),
                    "beat_probability": round(prob, 3),
                    "confidence_tier": tier,
                    "predicted_beat": predicted_beat,
                    "actual_beat": actual_beat,
                    "is_correct": is_correct,
                    "surprise_pct": round(surprise_pct, 2),
                    "eps_estimate": float(earnings.loc[edate, "EPS Estimate"]),
                    "eps_actual": float(earnings.loc[edate, "Reported EPS"]),
                }
            )
        except Exception as e:
            logger.warning(f"Accuracy event failed for {ticker} {edate}: {e}")
            continue

    accuracy = correct / len(events) if events else 0.0

    return HistoricalAccuracyResponse(
        ticker=ticker,
        events=sorted(events, key=lambda x: x["date"], reverse=True),
        overall_accuracy=round(accuracy, 4),
        n_predictions=len(events),
    )


@app.get("/api/feature-importance", response_model=FeatureImportanceResponse)
def feature_importance():
    model = get_model()
    if not model.is_loaded:
        raise HTTPException(status_code=503, detail="Model not trained yet")
    return FeatureImportanceResponse(
        features=model.get_feature_importance(),
        model_meta={
            "trained_at": model.meta.get("trained_at", "unknown"),
            "n_samples": model.meta.get("n_samples", 0),
            "cv_auc": round(model.meta.get("cv_auc_mean", 0), 3),
            "beat_rate": round(model.meta.get("beat_rate", 0), 3),
        },
    )


@app.get("/api/calendar")
def upcoming_earnings_calendar():
    """Return predictions for stocks with earnings in the next 14 days."""
    model = get_model()

    # Use the training tickers list for the calendar (well-known large caps)
    upcoming = get_upcoming_earnings_for_calendar(TRAINING_TICKERS, days_ahead=14)

    results = []
    for item in upcoming[:30]:  # cap at 30 to avoid timeout
        ticker = item["ticker"]
        try:
            info = get_ticker_info(ticker)
            company_name = info.get("longName") or info.get("shortName") or ticker

            if model.is_loaded:
                feats, _, _warn = compute_current_features(ticker)
                X = np.array([[feats[k] for k in FEATURE_NAMES]], dtype=np.float32)
                prob, tier = model.predict(X)
            else:
                prob, tier = 0.5, "Low"

            results.append(
                {
                    "ticker": ticker,
                    "company_name": company_name,
                    "earnings_date": item["earnings_date"],
                    "beat_probability": round(prob, 3),
                    "confidence_tier": tier,
                }
            )
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Calendar entry failed for {ticker}: {e}")
            continue

    results.sort(key=lambda x: x["earnings_date"])
    return {"calendar": results, "model_ready": model.is_loaded}


_training_status = {"status": "idle", "message": ""}
_training_in_progress = False


@app.post("/api/train", response_model=TrainStatus)
def trigger_training(background_tasks: BackgroundTasks):
    global _training_in_progress
    if _training_in_progress:
        return TrainStatus(status="running", message="Training already in progress")

    def run_training():
        global _training_in_progress
        _training_in_progress = True
        _training_status["status"] = "running"
        try:
            import subprocess, sys
            result = subprocess.run(
                [sys.executable, "train.py"],
                capture_output=True, text=True, cwd=str(__import__("pathlib").Path(__file__).parent)
            )
            if result.returncode == 0:
                _training_status["status"] = "done"
                _training_status["message"] = "Training complete. Model reloaded."
                # Reload model
                import importlib, model as m
                m._model_instance = None
                get_model()
            else:
                _training_status["status"] = "error"
                _training_status["message"] = result.stderr[:500]
        except Exception as e:
            _training_status["status"] = "error"
            _training_status["message"] = str(e)
        finally:
            _training_in_progress = False

    background_tasks.add_task(run_training)
    return TrainStatus(status="started", message="Training started in background. This takes ~10 minutes.")


@app.get("/api/train/status")
def training_status():
    return _training_status
