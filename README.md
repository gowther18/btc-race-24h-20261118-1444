# BTC dip-bounce scalper — make.fun `btc-race-24h-20261118-1444`

A long-only cbBTC scalper for the `bars-replay/v1` harness (Python 3.13,
stdlib only, `main.py` at the repo root).

## Strategy

15-minute mean reversion with a bounce confirmation:

- **Entry** (flat only): the close fell ≥ 0.30% over the last 15 bars **and**
  rose ≥ 0.10% over the last 5 bars — the dip is turning. Buys the full
  cash balance of CBBTC.
- **Exit**: take profit +0.70% over the entry close, stop loss −0.50%, or
  a 18-bar max hold (these bounces fade fast). 5-bar cooldown after exits,
  no new entries in the last 30 bars of the window.

## Why this shape

On the frozen dev window the 15-minute return is strongly negatively
correlated with the next 15 minutes (−0.33) while the 5-minute return is
positively correlated (+0.15). Every trend-following, Bollinger, RSI and
Donchian variant tested on the same window lost money after the ~26 bps
round-trip cost; this setup made **+$11.86 on 3 round trips, 0.44% max
drawdown**. The bot sits in cash the rest of the day, which is what keeps
it out of the window's −2.8% drift. All house baselines lose on dev
(buy-and-hold −$31.63, momentum −$23.87, ema-cross −$148.17,
rsi-bollinger −$39.92, adx-momentum −$75.57).

## Files

- `main.py` — the bot (speaks `agent-fun/bars-replay/v1` via the shim).
- `vendor/makefun_bars.py` — byte-for-byte copy of the kit's Python shim.
- `LICENSE` — MIT.

## Local validation

No Docker on this machine, so `grade-local` cannot run the Python sandbox
(`--driver process` runs node22 only). Validated instead with a standalone
replay driver (`driver.py` in the work dir, not in this repo) that feeds the
kit's dev window through the real protocol: **dev net PnL +$11.86, 3 round
trips, max drawdown 0.44%, two runs byte-for-byte identical replies**.
The driver's fill model reproduces the harness exactly on buy-and-hold
(−$31.63, matching `grade-local`).
