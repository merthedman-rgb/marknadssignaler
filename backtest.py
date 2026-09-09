"""
Backtestar signalreglerna (MA20/MA50 + RSI14 + MACD + volym) mot HISTORISK
DAGSDATA, for att ge en statistisk kansla for om reglerna har haft nagon
edge alls - helt separat fran den live korande signal_check.py.

Viktiga begransningar (lasvart innan du drar slutsatser):
- Kors pa DAGSKURSER (flera ars historik finns gratis), inte 5-minuters-data
  som den skarpa signalen anvander - resultatet ar darfor en fingervisning,
  inte ett exakt bevis for hur 5-minuterssystemet skulle ha presterat.
- Multi-tidsram-filtret (daglig trend) anvands inte har eftersom vi redan ar
  pa dagsniva - det vore cirkulart.
- Transaktionskostnader, spread och slippage ar INTE med i berakningen.
- Historisk avkastning garanterar inget om framtiden.

Korning: python backtest.py
Krav: samma paket som signal_check.py (se requirements.txt)
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import yfinance as yf

from signal_check import ASSETS, compute_indicators, volume_confirms

LOOKBACK_PERIOD = "2y"
FORWARD_DAYS = 5  # hur manga handelsdagar framat vi mater avkastningen over


@dataclass
class SignalEvent:
    date: str
    signal: str
    price: float
    forward_return_pct: float | None


def backtest_asset(ticker: str) -> list[SignalEvent]:
    df = yf.download(ticker, period=LOOKBACK_PERIOD, interval="1d", progress=False)
    if df is None or df.empty:
        return []
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close, volume = df["Close"], df["Volume"]
    ma20, ma50, rsi, hist = compute_indicators(close)
    vol_ma = volume.rolling(20).mean()

    events = []
    for i in range(50, len(df) - FORWARD_DAYS):  # 50 for att MA50 ska finnas
        m20, m50, r, h = ma20.iloc[i], ma50.iloc[i], rsi.iloc[i], hist.iloc[i]
        if any(pd.isna(x) for x in [m20, m50, r, h]):
            continue
        vol_ok = volume.iloc[i] > vol_ma.iloc[i] if not pd.isna(vol_ma.iloc[i]) else False

        signal = "neutral"
        if m20 > m50 and r < 70 and h > 0 and vol_ok:
            signal = "long"
        elif m20 < m50 and r > 30 and h < 0 and vol_ok:
            signal = "short"

        if signal == "neutral":
            continue

        price_now = close.iloc[i]
        price_fwd = close.iloc[i + FORWARD_DAYS]
        fwd_ret = (price_fwd - price_now) / price_now * 100
        if signal == "short":
            fwd_ret = -fwd_ret  # positiv avkastning = ratt riktning aven for short

        events.append(SignalEvent(
            date=str(df.index[i].date()),
            signal=signal,
            price=round(float(price_now), 2),
            forward_return_pct=round(float(fwd_ret), 2),
        ))
    return events


def summarize(label: str, events: list[SignalEvent], baseline_return_pct: float) -> None:
    print(f"\n=== {label} ===")
    if not events:
        print("Inga signaler genererades under perioden (med dagens tröskelvärden).")
        return

    returns = [e.forward_return_pct for e in events]
    wins = [r for r in returns if r > 0]
    win_rate = len(wins) / len(returns) * 100
    avg_return = sum(returns) / len(returns)

    print(f"Antal signaler:       {len(events)}")
    print(f"Träffsäkerhet:        {win_rate:.1f}% positiv {FORWARD_DAYS}-dagarsavkastning i rätt riktning")
    print(f"Snittavkastning/signal:{avg_return:+.2f}%  (över {FORWARD_DAYS} handelsdagar)")
    print(f"Jämfört med köp-och-behåll över hela perioden: {baseline_return_pct:+.2f}%")

    longs = [e for e in events if e.signal == "long"]
    shorts = [e for e in events if e.signal == "short"]
    print(f"  varav LONG:  {len(longs)} st")
    print(f"  varav SHORT: {len(shorts)} st")


def main():
    print(f"Backtest av signalreglerna, {LOOKBACK_PERIOD} historik, dagskurser, "
          f"{FORWARD_DAYS}-dagars framåtblick.\n"
          f"OBS: körs på dagsdata, inte samma tidsupplösning som den live 5-minuterssignalen.")

    for key, meta in ASSETS.items():
        df = yf.download(meta["ticker"], period=LOOKBACK_PERIOD, interval="1d", progress=False)
        if df is None or df.empty:
            print(f"\n=== {meta['label']} ===\nIngen data hittades för {meta['ticker']}.")
            continue
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        baseline = (close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100

        events = backtest_asset(meta["ticker"])
        summarize(meta["label"], events, float(baseline))


if __name__ == "__main__":
    main()
