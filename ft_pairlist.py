#!/usr/bin/env python3
"""
freqtrade-pairlist  -  Analysiert die vorhandenen Kursdaten und rankt Paare.

Hilft beim Zusammenstellen einer guten StaticPairList: Volumen, Volatilitaet,
Datenabdeckung und auffaellige Preis-Spruenge je Paar.

Usage:
    python ft_pairlist.py [--datadir user_data/data] [--exchange binance]
        [--timeframe 1d] [--quote USDC] [--top 30] [-o pairlist.csv]
"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser(description="Kursdaten analysieren & Paare ranken.")
    p.add_argument("--datadir", default="user_data/data")
    p.add_argument("--exchange", default="binance")
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--quote", default="USDC", help="Quote-Waehrung (Default USDC)")
    p.add_argument("--top", type=int, default=30, help="wie viele Top-Paare ausgeben")
    p.add_argument("-o", "--output", default=None, help="optional als CSV speichern")
    args = p.parse_args()

    folder = os.path.join(args.datadir, args.exchange)
    pattern = os.path.join(folder, f"*_{args.quote}-{args.timeframe}.feather")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"Keine Daten gefunden: {pattern}")
        sys.exit(1)

    rows = []
    for f in files:
        pair = os.path.basename(f).replace(f"_{args.quote}-{args.timeframe}.feather", "") + f"/{args.quote}"
        try:
            df = pd.read_feather(f)
        except Exception:
            continue
        if df.empty or "close" not in df.columns:
            continue
        ret = df["close"].pct_change()
        quote_vol = (df["close"] * df["volume"])
        big_jumps = int((ret.abs() > 0.20).sum())
        rows.append({
            "pair": pair,
            "avg_quote_vol": round(quote_vol.mean(), 0),
            "volatility_%": round(ret.std() * 100, 2),
            "days": len(df),
            "start": str(df["date"].min())[:10],
            "price_jumps>20%": big_jumps,
        })

    res = pd.DataFrame(rows).sort_values("avg_quote_vol", ascending=False).reset_index(drop=True)
    res.index += 1

    print(f"\n{len(res)} Paare analysiert ({args.timeframe}, Quote {args.quote}). "
          f"Top {min(args.top, len(res))} nach Ø-Volumen:\n")
    show = res.head(args.top).copy()
    show["avg_quote_vol"] = show["avg_quote_vol"].map(lambda v: f"{v:,.0f}")
    print(show.to_string())
    print("\nHinweis: hohes Volumen = liquide (gut handelbar); viele >20%-Spruenge = riskant/"
          "illiquide oder Daten-Artefakte. Wenig 'days' = kurze Historie.")

    if args.output:
        res.to_csv(args.output, index=False)
        print(f"\nVollständige Liste gespeichert: {args.output}")


if __name__ == "__main__":
    main()
