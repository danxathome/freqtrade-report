#!/usr/bin/env python3
"""
freqtrade-compare  -  Mehrere Freqtrade-Backtests nebeneinander vergleichen.

Usage:
    python ft_compare.py A.zip B.zip [C.zip ...] -o compare.html [--labels "A,B,C"]

Erzeugt eine HTML-Seite mit:
  - Equity-Kurven aller Strategien uebereinander (in % vom Start)
  - Drawdown-Verlauf uebereinander
  - KPI-Vergleichstabelle (Profit, MaxDD, Winrate, Profit-Faktor, Trades, ...)
"""
import argparse
import base64
import io
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from freqtrade.data.btanalysis import load_backtest_data, load_backtest_stats
except Exception:
    print("Fehler: freqtrade ist nicht importierbar. Bitte im Freqtrade-venv ausfuehren.")
    sys.exit(1)

COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _series(src):
    trades = load_backtest_data(src)
    if trades.empty or "close_date" not in trades.columns:
        return None
    trades = trades.sort_values("close_date").reset_index(drop=True)
    start = 1000.0
    try:
        stats = load_backtest_stats(src)
        start = float(list(stats["strategy"].values())[0].get("starting_balance", start))
    except Exception:
        pass
    trades["close_date"] = pd.to_datetime(trades["close_date"])
    eq = start + trades["profit_abs"].cumsum()
    eq_pct = eq / start * 100.0
    rm = np.maximum.accumulate(eq.values)
    dd = (eq.values - rm) / rm * 100.0
    w = trades[trades["profit_abs"] > 0]["profit_abs"].sum()
    l = abs(trades[trades["profit_abs"] <= 0]["profit_abs"].sum())
    kpi = {
        "Profit %": round(trades["profit_abs"].sum() / start * 100, 2),
        "Max DD %": round(dd.min(), 2),
        "Winrate %": round((trades["profit_abs"] > 0).mean() * 100, 1),
        "Profit-Faktor": round(w / l, 2) if l else float("inf"),
        "Trades": len(trades),
        "O Dauer (h)": round(trades["trade_duration"].mean() / 60, 1),
    }
    return {"date": trades["close_date"], "eq_pct": eq_pct, "dd": dd, "kpi": kpi}


def build(sources, labels, out):
    data = []
    for src, lab in zip(sources, labels):
        s = _series(src)
        if s is None:
            print(f"  uebersprungen (keine Trades): {src}")
            continue
        s["label"] = lab
        data.append(s)
    if not data:
        print("Keine gueltigen Backtests gefunden.")
        sys.exit(1)

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 7), height_ratios=[3, 1], sharex=True)
    for i, s in enumerate(data):
        c = COLORS[i % len(COLORS)]
        a1.plot(s["date"], s["eq_pct"], color=c, lw=1.8, label=s["label"])
        a2.plot(s["date"], s["dd"], color=c, lw=1.0)
    a1.axhline(100, color="grey", ls="--", lw=0.8)
    a1.set_ylabel("Equity (% vom Start)"); a1.set_title("Equity-Vergleich"); a1.legend(loc="upper left"); a1.grid(alpha=0.25)
    a2.set_ylabel("Drawdown %"); a2.grid(alpha=0.25)
    equity_png = _png(fig)

    table = pd.DataFrame({s["label"]: s["kpi"] for s in data}).T
    table = table[["Profit %", "Max DD %", "Winrate %", "Profit-Faktor", "Trades", "O Dauer (h)"]]

    css = """body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#0f1419;color:#e6e6e6}
    .wrap{max-width:1000px;margin:0 auto;padding:24px} h1{font-size:22px;margin:0 0 4px}
    .sub{color:#8a93a0;font-size:13px;margin-bottom:20px}
    img{max-width:100%;border-radius:10px;border:1px solid #263241;margin:8px 0 24px}
    table{border-collapse:collapse;width:100%;margin:8px 0 20px;font-size:14px}
    th,td{border:1px solid #263241;padding:8px 12px;text-align:right} th{background:#1a212b}
    td:first-child,th:first-child{text-align:left;font-weight:600}
    h2{font-size:16px;border-bottom:1px solid #263241;padding-bottom:6px}"""
    html = f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Backtest-Vergleich</title>
    <style>{css}</style></head><body><div class="wrap">
    <h1>Freqtrade Backtest-Vergleich</h1>
    <div class="sub">{len(data)} Strategien &middot; erstellt {datetime.now():%Y-%m-%d %H:%M}</div>
    <h2>Equity & Drawdown</h2><img src="data:image/png;base64,{equity_png}">
    <h2>Kennzahlen-Vergleich</h2>{table.to_html()}
    </div></body></html>"""
    with open(out, "w") as f:
        f.write(html)
    print(f"Vergleich gespeichert: {out}")
    print(table.to_string())


def main():
    p = argparse.ArgumentParser(description="Mehrere Freqtrade-Backtests vergleichen.")
    p.add_argument("sources", nargs="+", help="Backtest-Ergebnisdateien (.zip/.json)")
    p.add_argument("-o", "--output", default="compare.html")
    p.add_argument("--labels", default=None, help="Komma-getrennte Namen, z.B. \"Strat A,Strat B\"")
    args = p.parse_args()
    if args.labels:
        labels = [x.strip() for x in args.labels.split(",")]
    else:
        labels = [f"#{i+1}" for i in range(len(args.sources))]
    while len(labels) < len(args.sources):
        labels.append(f"#{len(labels)+1}")
    build(args.sources, labels, args.output)


if __name__ == "__main__":
    main()
