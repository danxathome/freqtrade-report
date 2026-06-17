#!/usr/bin/env python3
"""
freqtrade-configcheck  -  Prueft eine Freqtrade-config.json auf typische Fehler.

Usage:
    python ft_configcheck.py user_data/config.json
"""
import argparse
import json
import sys

OK, WARN, ERR = "OK  ", "WARN", "FEHLER"


def check(path):
    issues = []
    try:
        with open(path) as f:
            c = json.load(f)
    except Exception as e:
        print(f"{ERR}: config nicht lesbar/kein gueltiges JSON: {e}")
        sys.exit(1)

    def add(level, msg):
        issues.append((level, msg))

    # Pflichtfelder
    for key in ["max_open_trades", "stake_currency", "stake_amount", "timeframe", "exchange"]:
        if key not in c:
            add(ERR, f"Pflichtfeld fehlt: '{key}'")

    # dry_run
    if c.get("dry_run") is True:
        add(OK, "dry_run = true (Papierhandel, kein echtes Geld)")
    elif c.get("dry_run") is False:
        add(WARN, "dry_run = FALSE -> ECHTGELD-Handel! Nur wenn du das wirklich willst.")
    else:
        add(WARN, "dry_run nicht gesetzt (Standard ist true)")

    # API-Keys im Klartext
    ex = c.get("exchange", {})
    if ex.get("key") or ex.get("secret"):
        add(WARN, "API key/secret stehen in der config -> niemals oeffentlich teilen / committen!")

    # Pairlist
    wl = ex.get("pair_whitelist", [])
    pls = c.get("pairlists", [])
    methods = [m.get("method") for m in pls] if isinstance(pls, list) else []
    if "StaticPairList" in methods and not wl:
        add(ERR, "StaticPairList aktiv, aber pair_whitelist ist leer")
    elif not wl and "VolumePairList" not in methods:
        add(WARN, "pair_whitelist leer und keine VolumePairList -> evtl. keine Paare")
    else:
        add(OK, f"{len(wl)} Paare in der Whitelist, Pairlist-Methoden: {methods or 'keine'}")

    # stake_amount
    sa = c.get("stake_amount")
    if sa == "unlimited":
        tbr = c.get("tradable_balance_ratio")
        if tbr is None:
            add(WARN, "stake_amount 'unlimited' ohne tradable_balance_ratio -> evtl. 100% Einsatz")
        else:
            add(OK, f"stake_amount unlimited, tradable_balance_ratio={tbr}")
    elif isinstance(sa, (int, float)):
        wallet = c.get("dry_run_wallet")
        if wallet and sa > wallet:
            add(ERR, f"stake_amount ({sa}) groesser als dry_run_wallet ({wallet})")
        else:
            add(OK, f"stake_amount fix = {sa}")

    # timeframe plausibel
    tf = c.get("timeframe")
    if tf and not any(tf.endswith(u) for u in ("m", "h", "d", "w")):
        add(WARN, f"timeframe '{tf}' sieht ungewoehnlich aus")

    # trading_mode / spot
    if c.get("trading_mode", "spot") == "spot" and c.get("can_short"):
        add(WARN, "can_short=true im Spot-Modus -> Shorten geht im Spot nicht")

    # Ausgabe
    print(f"\nConfig-Check: {path}\n" + "-" * 50)
    order = {ERR: 0, WARN: 1, OK: 2}
    for level, msg in sorted(issues, key=lambda x: order[x[0]]):
        print(f"[{level}] {msg}")
    nerr = sum(1 for l, _ in issues if l == ERR)
    nwarn = sum(1 for l, _ in issues if l == WARN)
    print("-" * 50)
    print(f"Ergebnis: {nerr} Fehler, {nwarn} Warnungen.")
    if nerr == 0:
        print("Keine kritischen Fehler gefunden.")


def main():
    p = argparse.ArgumentParser(description="Freqtrade-config.json pruefen.")
    p.add_argument("config", help="Pfad zur config.json")
    args = p.parse_args()
    check(args.config)


if __name__ == "__main__":
    main()
