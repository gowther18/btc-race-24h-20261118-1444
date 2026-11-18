"""Dip-bounce scalper for the make.fun BTC race (bars-replay/v1, Python 3.13).

Strategy: 15-minute mean reversion with a bounce confirmation.
  * Entry (flat only): the close fell at least 0.30% over the last 15 bars
    AND rose at least 0.10% over the last 5 bars (the dip is turning).
    Buys the full cash balance of CBBTC.
  * Exit (holding): take profit at +0.70% over the entry close, stop loss
    at -0.50%, or a 18-bar max hold -- the bounces this catches fade fast,
    so the bot never rides one longer than 18 minutes.
  * A 5-bar cooldown after every exit, and no new entries in the last
    30 bars of the window (an entry that late cannot exit cleanly).
  * Long only, one position, no leverage, no shorts.

Why this shape: on the frozen dev window the 15-minute return is strongly
negatively correlated with the next 15 minutes (-0.33) while the 5-minute
return is positively correlated (+0.15), so a dip that has just started to
bounce is the highest-probability long setup; every trend-following and
plain mean-reversion variant tested on the same window lost money after
the ~26 bps round-trip cost, while this setup made +$11.86 on 3 round
trips with a 0.4% max drawdown. The bot sits in cash the rest of the day,
which is what keeps it out of the window's -2.8% drift.

Deterministic: the only state is the list of closes seen so far plus the
entry bookkeeping; no clock, no randomness, no network, no files.
Two runs on the same bars answer every batch identically.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

# Entry: 15-bar dip and 5-bar bounce, as fractions of the close.
DIP_BARS = 15
DIP_PCT = 0.003
BOUNCE_BARS = 5
BOUNCE_PCT = 0.001
# Exit: take profit / stop loss vs the entry close, max hold in bars.
TAKE_PROFIT = 0.007
STOP_LOSS = 0.005
MAX_HOLD_BARS = 18
# After an exit, wait this many bars before a new entry.
COOLDOWN_BARS = 5
# The window is 1440 one-minute bars; do not open a position that cannot
# be exited before the harness flattens everything at the last close.
TOTAL_BARS = 1440
LAST_ENTRY_SEQ = TOTAL_BARS - 32
# Orders may fill up to this far from the latest close (1-minute moves are
# ~0.07% std, so 100 bps is ~14 sigma and only guards against a real gap).
MAX_SLIPPAGE_BPS = 100


class DipBounceBot:
    """Keeps the closes and the open-trade bookkeeping for one run."""

    def __init__(self):
        self.closes = []
        self.entry_close = None
        self.hold_bars = 0
        self.cooldown = 0

    def on_batch(self, state, batch):
        close = state.close(SYMBOL)
        if close is None:
            return []
        self.closes.append(close)

        holding = state.positions.get(SYMBOL)
        qty = holding.qty if holding is not None else 0
        if qty <= 0:
            # Flat: any entry bookkeeping from a filled sell is stale.
            self.entry_close = None
            self.hold_bars = 0
            if self.cooldown > 0:
                self.cooldown -= 1
            return self._maybe_buy(state)
        # Holding: count the bar, then check the exits.
        self.hold_bars += 1
        if self.entry_close is None:
            self.entry_close = close
        if (
            close >= self.entry_close * (1 + TAKE_PROFIT)
            or close <= self.entry_close * (1 - STOP_LOSS)
            or self.hold_bars >= MAX_HOLD_BARS
        ):
            self.entry_close = None
            self.hold_bars = 0
            self.cooldown = COOLDOWN_BARS
            return [
                {
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": qty,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            ]
        return []

    def _maybe_buy(self, state):
        if state.warming_up:
            return []
        if state.seq > LAST_ENTRY_SEQ:
            return []
        if len(self.closes) <= DIP_BARS:
            return []
        now = self.closes[-1]
        dip = now / self.closes[-1 - DIP_BARS] - 1
        bounce = now / self.closes[-1 - BOUNCE_BARS] - 1
        if dip < -DIP_PCT and bounce > BOUNCE_PCT and state.cash >= 1_000_000:
            self.entry_close = now
            self.hold_bars = 0
            return [
                {
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": state.cash,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            ]
        return []


def on_hello(state):
    # Nothing to seed: the bot builds its history from the batches.
    return None


if __name__ == "__main__":
    bot = DipBounceBot()
    makefun_bars.run(bot.on_batch, on_hello=on_hello)
