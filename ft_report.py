#!/usr/bin/env python3
"""
freqtrade-report  -  Schoener HTML-Report aus einem Freqtrade-Backtest.

Usage:
    python freqtrade_report.py <backtest-result.zip|.json> [-o report.html]
        [--datadir user_data/data] [--exchange binance] [--timeframe 5m] [--pairs 2]

Erzeugt eine einzelne, selbsterklaerende HTML-Datei mit:
  - Kennzahlen (Profit, Drawdown, Winrate, Profit-Faktor, ...)
  - Equity-Kurve + Drawdown-Verlauf
  - Gewinn/Verlust je Paar
  - Aufschluesselung nach Exit-Grund
  - Monats-Renditen
  - Trade-Beispiele: Kurs-Charts gut/schlecht laufender Paare mit Entry-/Exit-Markern

Benoetigt: freqtrade (fuer load_*), pandas, numpy, matplotlib.
"""
import argparse
import base64
import io
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

try:
    from freqtrade.data.btanalysis import load_backtest_data, load_backtest_stats
except Exception:
    print("Fehler: freqtrade ist nicht importierbar. Bitte im Freqtrade-venv ausfuehren.")
    sys.exit(1)

try:
    from freqtrade.data.history import load_pair_history
    from freqtrade.enums import CandleType
    _HAVE_HIST = True
except Exception:
    _HAVE_HIST = False


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _load_candles(pair, timeframe, datadir, exchange):
    if not _HAVE_HIST:
        return None
    try:
        df = load_pair_history(pair=pair, timeframe=timeframe, datadir=Path(datadir) / exchange,
                               data_format="feather", candle_type=CandleType.SPOT)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def _pair_plot(pair, ptrades, candles):
    ptrades = ptrades.copy()
    tmin = ptrades["open_date"].min()
    tmax = ptrades["close_date"].max()
    pad = (tmax - tmin) * 0.08 if tmax > tmin else pd.Timedelta(days=1)
    c = candles[(candles["date"] >= tmin - pad) & (candles["date"] <= tmax + pad)]
    if c.empty:
        return None
    pnl = ptrades["profit_abs"].sum()
    wr = (ptrades["profit_abs"] > 0).mean() * 100
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(c["date"], c["close"], color="#222", lw=0.8, zorder=2)
    wins = ptrades[ptrades["profit_abs"] > 0]
    loss = ptrades[ptrades["profit_abs"] <= 0]
    for _, r in ptrades.iterrows():
        col = "#2ca02c" if r["profit_abs"] > 0 else "#d62728"
        ax.plot([r["open_date"], r["close_date"]], [r["open_rate"], r["close_rate"]],
                color=col, lw=0.9, alpha=0.6, zorder=3)
    ax.scatter(ptrades["open_date"], ptrades["open_rate"], marker="^", s=70,
               color="#2ca02c", edgecolor="k", lw=0.4, label="Entry", zorder=5)
    ax.scatter(wins["close_date"], wins["close_rate"], marker="o", s=55,
               color="#1565c0", edgecolor="k", lw=0.4, label="Exit (Gewinn)", zorder=5)
    ax.scatter(loss["close_date"], loss["close_rate"], marker="x", s=60,
               color="#d62728", lw=1.6, label="Exit (Verlust)", zorder=6)
    ax.set_title(f"{pair}  |  {len(ptrades)} Trades, {pnl:+.2f} USDC, Winrate {wr:.0f}%",
                 fontsize=11, fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, ncol=3)
    ax.grid(alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    return _png(fig)


def _trade_example_section(trades, timeframe, datadir, exchange, n_each):
    """Charts der besten und schlechtesten Paare (>=3 Trades) mit Entry/Exit-Markern."""
    if not _HAVE_HIST:
        return '<p style="color:#8a93a0">Trade-Charts uebersprungen (Kursdaten nicht ladbar).</p>'
    counts = trades["pair"].value_counts()
    pnl = trades.groupby("pair")["profit_abs"].sum().sort_values()
    eligible = [p for p in pnl.index if counts.get(p, 0) >= 3]
    if not eligible:
        eligible = list(pnl.index)
    worst = eligible[:n_each]
    best = [p for p in reversed(eligible)][:n_each]
    selected = list(dict.fromkeys(best + worst))
    imgs = []
    for pair in selected:
        candles = _load_candles(pair, timeframe, datadir, exchange)
        if candles is None:
            continue
        png = _pair_plot(pair, trades[trades["pair"] == pair], candles)
        if png:
            tag = "gut" if pair in best else "schlecht"
            imgs.append(f'<div class="sub">{tag} laufendes Paar</div>'
                        f'<img src="data:image/png;base64,{png}">')
    if not imgs:
        return ('<p style="color:#8a93a0">Keine Kursdaten gefunden. Tipp: '
                '--datadir / --timeframe passend zum Backtest setzen.</p>')
    return "".join(imgs)


def build_report(src, out, datadir="user_data/data", exchange="binance",
                 timeframe=None, n_each=2):
    trades = load_backtest_data(src)
    if trades.empty or "close_date" not in trades.columns:
        print("Keine Trades im Ergebnis gefunden (leeres Backtest-Resultat?).")
        sys.exit(1)
    trades = trades.sort_values("close_date").reset_index(drop=True)

    start = 1000.0
    try:
        stats = load_backtest_stats(src)
        strat = list(stats["strategy"].values())[0]
        start = float(strat.get("starting_balance", start))
        if timeframe is None:
            timeframe = strat.get("timeframe")
    except Exception:
        pass
    if timeframe is None:
        timeframe = "5m"

    trades["open_date"] = pd.to_datetime(trades["open_date"])
    trades["close_date"] = pd.to_datetime(trades["close_date"])
    trades["equity"] = start + trades["profit_abs"].cumsum()
    eq = trades["equity"].values
    runmax = np.maximum.accumulate(eq)
    dd = (eq - runmax) / runmax * 100

    wins = trades[trades["profit_abs"] > 0]
    losses = trades[trades["profit_abs"] <= 0]
    pf = wins["profit_abs"].sum() / abs(losses["profit_abs"].sum()) if losses["profit_abs"].sum() != 0 else float("inf")

    kpis = {
        "Trades": len(trades),
        "Gesamt-Profit %": round(trades["profit_abs"].sum() / start * 100, 2),
        "Endkapital": round(eq[-1], 2),
        "Winrate %": round((trades["profit_abs"] > 0).mean() * 100, 1),
        "Profit-Faktor": round(pf, 2),
        "Max Drawdown %": round(dd.min(), 2),
        "O Profit/Trade %": round(trades["profit_ratio"].mean() * 100, 2),
        "O Dauer (h)": round(trades["trade_duration"].mean() / 60, 1),
        "Bester Trade %": round(trades["profit_ratio"].max() * 100, 2),
        "Schlechtester Trade %": round(trades["profit_ratio"].min() * 100, 2),
    }

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6), height_ratios=[3, 1], sharex=True)
    a1.plot(trades["close_date"], eq, color="#1f77b4"); a1.fill_between(trades["close_date"], start, eq, alpha=0.1)
    a1.axhline(start, color="grey", ls="--", lw=0.8); a1.set_ylabel("Equity"); a1.grid(alpha=0.25); a1.set_title("Equity-Kurve")
    a2.fill_between(trades["close_date"], dd, 0, color="#d62728", alpha=0.5); a2.set_ylabel("Drawdown %"); a2.grid(alpha=0.25)
    equity_png = _png(fig)

    g = trades.groupby("pair").agg(Trades=("profit_abs", "size"),
                                   Profit_USDC=("profit_abs", "sum"),
                                   Winrate=("profit_abs", lambda s: round((s > 0).mean() * 100, 1))).round(2)
    g = g.sort_values("Profit_USDC", ascending=False)
    fig2, ax2 = plt.subplots(figsize=(11, max(2.5, 0.35 * len(g))))
    ax2.barh(g.index, g["Profit_USDC"], color=["#2ca02c" if v > 0 else "#d62728" for v in g["Profit_USDC"]])
    ax2.axvline(0, color="grey", lw=0.8); ax2.set_title("Profit je Paar (USDC)"); ax2.grid(alpha=0.25); ax2.invert_yaxis()
    pair_png = _png(fig2)

    ex = trades.groupby("exit_reason").agg(Trades=("profit_abs", "size"),
                                           Profit_USDC=("profit_abs", "sum"),
                                           Mean_pct=("profit_ratio", lambda s: round(s.mean() * 100, 2))).round(2)
    ex = ex.sort_values("Profit_USDC", ascending=False)

    trades["ym"] = trades["close_date"].dt.strftime("%Y-%m")
    monthly = (trades.groupby("ym")["profit_abs"].sum() / start * 100).round(2)

    examples_html = _trade_example_section(trades, timeframe, datadir, exchange, n_each)

    def kpi_cards(k):
        return "".join(f'<div class="card"><div class="v">{v}</div><div class="l">{name}</div></div>'
                       for name, v in k.items())

    css = """
    body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#0f1419;color:#e6e6e6}
    .wrap{max-width:1000px;margin:0 auto;padding:24px}
    h1{font-size:22px;margin:0 0 4px} .sub{color:#8a93a0;font-size:13px;margin-bottom:6px}
    .cards{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px}
    .card{background:#1a212b;border:1px solid #263241;border-radius:10px;padding:12px 16px;min-width:130px}
    .card .v{font-size:20px;font-weight:700} .card .l{color:#8a93a0;font-size:12px;margin-top:2px}
    img{max-width:100%;border-radius:10px;border:1px solid #263241;margin:4px 0 22px}
    table{border-collapse:collapse;width:100%;margin:8px 0 28px;font-size:13px}
    th,td{border:1px solid #263241;padding:6px 10px;text-align:right} th{background:#1a212b}
    td:first-child,th:first-child{text-align:left}
    h2{font-size:16px;border-bottom:1px solid #263241;padding-bottom:6px;margin-top:8px}
    .foot{color:#6b7280;font-size:12px;margin-top:32px;text-align:center}
    """
    html = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
    <title>Freqtrade Backtest Report</title><style>{css}</style></head><body><div class="wrap">
    <h1>Freqtrade Backtest Report</h1>
    <div class="sub">Quelle: {src} &nbsp;|&nbsp; erstellt {datetime.now():%Y-%m-%d %H:%M}</div>
    <div class="cards">{kpi_cards(kpis)}</div>
    <h2>Equity & Drawdown</h2><img src="data:image/png;base64,{equity_png}">
    <h2>Profit je Paar</h2><img src="data:image/png;base64,{pair_png}">
    {g.to_html()}
    <h2>Exit-Gruende</h2>{ex.to_html()}
    <h2>Monats-Renditen (%)</h2>{monthly.to_frame('Return %').to_html()}
    <h2>Trade-Beispiele (gut & schlecht)</h2>{examples_html}
    <div class="foot">erstellt mit freqtrade-report &middot; Wenn dir das Tool hilft, freue ich mich ueber einen Kaffee (siehe README).</div>
    </div></body></html>"""

    with open(out, "w") as f:
        f.write(html)
    print(f"Report gespeichert: {out}")
    print(f"  Trades: {kpis['Trades']} | Profit: {kpis['Gesamt-Profit %']}% | "
          f"MaxDD: {kpis['Max Drawdown %']}% | Winrate: {kpis['Winrate %']}% | tf={timeframe}")


def main():
    p = argparse.ArgumentParser(description="Schoener HTML-Report aus einem Freqtrade-Backtest.")
    p.add_argument("source", help="Pfad zur Backtest-Ergebnisdatei (.zip oder .json)")
    p.add_argument("-o", "--output", default="freqtrade_report.html", help="Ausgabe-HTML")
    p.add_argument("--datadir", default="user_data/data", help="Freqtrade-Datenordner (fuer Kurs-Charts)")
    p.add_argument("--exchange", default="binance", help="Exchange-Unterordner in --datadir")
    p.add_argument("--timeframe", default=None, help="Timeframe der Kursdaten (Default: aus Backtest)")
    p.add_argument("--pairs", type=int, default=2, help="Anzahl gute UND schlechte Paare fuer Charts (Default 2)")
    args = p.parse_args()
    build_report(args.source, args.output, datadir=args.datadir,
                 exchange=args.exchange, timeframe=args.timeframe, n_each=args.pairs)


if __name__ == "__main__":
    main()
