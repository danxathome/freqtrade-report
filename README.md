# freqtrade-report

A small **toolkit for Freqtrade** users: turn backtests into clean HTML reports, compare
strategies side by side, analyse your pairs, and sanity-check your config — each as a simple
command.

**Entry/exit signals per pair (good & bad trades):**

![Entry/exit preview](docs/preview.png)

**The full report at a glance:**

![Full report](docs/full_report.png)

> Or open the included [`example_report.html`](example_report.html) live in your browser.

## The tools

| Command | What it does |
|---|---|
| `ft-report` | Backtest → good-looking single-file HTML report (equity, drawdown, per-pair P&L, exit reasons, monthly returns, **entry/exit charts**). |
| `ft-compare` | Put **2+ backtests side by side** — overlaid equity/drawdown + a KPI comparison table. |
| `ft-pairlist` | Rank your pairs by volume, volatility, data coverage and price-jumps — helps build a good static pairlist. |
| `ft-configcheck` | Check a `config.json` for common mistakes (live-mode, empty whitelist, exposed API keys, …). |

## Install

```bash
# inside your freqtrade environment (so freqtrade itself is importable):
pip install .
```

This gives you the four commands above. (You can also just run the scripts directly without
installing, e.g. `python ft_report.py ...`.)

Requirements: Python 3.9+, `pandas`, `numpy`, `matplotlib`, and a working **freqtrade** install.

## Usage

```bash
# 1) Report from a backtest result
ft-report path/to/backtest-result.zip -o report.html

# 2) Compare strategies
ft-compare A.zip B.zip --labels "Strategy A,Strategy B" -o compare.html

# 3) Analyse pairs (build a pairlist)
ft-pairlist --timeframe 1d --top 30 -o pairlist.csv

# 4) Check a config
ft-configcheck user_data/config.json
```

**Where are the output files saved?** In the folder you run the command from (your current
working directory) unless you give a full path, e.g. `-o ~/Desktop/report.html`.
Open the generated HTML in any browser. Everything (charts included) is embedded — nothing to host.

`ft-report` options: `--datadir` (default `user_data/data`), `--exchange` (default `binance`),
`--timeframe` (default: from the backtest), `--pairs` (how many good AND bad pairs to chart, default 2).

## What's in the report

- **KPIs:** total profit %, end balance, win rate, profit factor, max drawdown, avg profit/trade, avg duration, best/worst trade
- **Equity curve + drawdown** chart
- **Profit per pair** (chart + table)
- **Exit-reason breakdown** (count, sum, mean %)
- **Monthly returns**
- **Trade examples:** price charts of the best- and worst-performing pairs with entry/exit
  markers (green ▲ entry, blue ● winning exit, red ✕ losing exit). (Needs the candle data in `--datadir`.)

## Support / Donate

This toolkit is free. If it saves you time, a small tip is hugely appreciated 🙏

- ₿ **USDC (BEP20 / BSC network):** `0x5906b08f245d82f28f44192549bdbfb8370c948d`
  *(please send only on the BEP20/BSC network)*
- ☕ Buy Me a Coffee: *(coming soon)*

## License

MIT — see [LICENSE](LICENSE).
