"""
Kollar tekniska signaler (MA20/MA50, RSI14, MACD) for Guld, OMX30 och Nasdaq,
och skickar en push-notis via ntfy.sh nar laget byter (LONG / SHORT / NEUTRAL).

Korning: python signal_check.py
Miljovariabel som behovs: NTFY_TOPIC (ditt hemliga ntfy-amne, se README)
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

ASSETS = {
    "guld": {"ticker": "XAU=X", "label": "Guld", "unit": "$/oz"},
    "omx30": {"ticker": "^OMX", "label": "OMX Stockholm 30", "unit": "p"},
    "nasdaq": {"ticker": "^NDX", "label": "Nasdaq US Tech 100", "unit": "p"},
}

STATE_FILE = Path(__file__).parent / "state.json"
HISTORY_FILE = Path(__file__).parent / "history.json"
HISTORY_MAX_ENTRIES = 50
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}" if NTFY_TOPIC else None


def compute_indicators(close: pd.Series):
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line

    return ma20, ma50, rsi, hist


def determine_signal(ma20, ma50, rsi, hist) -> str:
    m20, m50, r, h = ma20.iloc[-1], ma50.iloc[-1], rsi.iloc[-1], hist.iloc[-1]
    if any(pd.isna(x) for x in [m20, m50, r, h]):
        return "neutral"
    if m20 > m50 and r < 70 and h > 0:
        return "long"
    if m20 < m50 and r > 30 and h < 0:
        return "short"
    return "neutral"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def load_history() -> list:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return []


def save_history(history: list) -> None:
    trimmed = history[-HISTORY_MAX_ENTRIES:]
    HISTORY_FILE.write_text(json.dumps(trimmed, indent=2, ensure_ascii=False))


def send_notification(title: str, message: str, priority: str = "default") -> None:
    if not NTFY_URL:
        print("NTFY_TOPIC saknas i miljon - hoppar over notis:", title, "|", message)
        return
    try:
        requests.post(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": priority},
            timeout=10,
        )
    except requests.RequestException as exc:
        print("Kunde inte skicka notis:", exc)


def fetch_close_series(ticker: str) -> pd.Series | None:
    # 5-minuters-candlar, senaste 5 dagarna - yfinance tillater max ~60 dagars
    # historik for 5-minutersdata, men vi behover bara ett hundratal candlar
    # for MA20/MA50 att fa nog historik.
    df = yf.download(ticker, period="5d", interval="5m", progress=False)
    if df is None or df.empty:
        return None
    close = df["Close"]
    if isinstance(close, pd.DataFrame):  # yfinance kan returnera multi-index
        close = close.iloc[:, 0]
    return close


def run(fetch_fn=fetch_close_series) -> list[tuple]:
    """Kor hela kontrollen. fetch_fn kan bytas ut i tester."""
    state = load_state()
    history = load_history()
    changes = []

    for key, meta in ASSETS.items():
        close = fetch_fn(meta["ticker"])
        if close is None or close.empty:
            print(f"Ingen data for {meta['label']} ({meta['ticker']})")
            continue

        ma20, ma50, rsi, hist = compute_indicators(close)
        signal = determine_signal(ma20, ma50, rsi, hist)
        price = float(close.iloc[-1])

        prev_entry = state.get(key, {})
        prev_signal = prev_entry.get("signal")
        now_str = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M")

        def safe(x):
            return None if pd.isna(x) else round(float(x), 2)

        m20, m50, r, h = safe(ma20.iloc[-1]), safe(ma50.iloc[-1]), safe(rsi.iloc[-1]), safe(hist.iloc[-1])

        if signal != prev_signal:
            changes.append((meta["label"], prev_signal, signal, price, meta["unit"]))
            signal_since = now_str
            history.append({
                "time_utc": now_str,
                "key": key,
                "label": meta["label"],
                "from": prev_signal,
                "to": signal,
                "price": round(price, 2),
                "unit": meta["unit"],
                "ma20": m20,
                "ma50": m50,
                "rsi": r,
                "macd_hist": h,
            })
        else:
            signal_since = prev_entry.get("signal_since", now_str)

        state[key] = {
            "label": meta["label"],
            "signal": signal,
            "signal_since": signal_since,
            "price": round(price, 2),
            "unit": meta["unit"],
            "ma20": m20,
            "ma50": m50,
            "rsi": r,
            "macd_hist": h,
            "updated_utc": now_str,
        }

    save_state(state)
    save_history(history)

    for label, prev, new, price, unit in changes:
        title = f"{label}: {new.upper()}"
        message = f"Nytt lage: {new.upper()} (forut: {prev or 'okant'}). Pris: {price:.2f}{unit}"
        priority = "high" if new in ("long", "short") else "default"
        send_notification(title, message, priority)
        print(title, "-", message)

    if not changes:
        print("Inga lagesbyten denna korning.")

    return changes


if __name__ == "__main__":
    run()
