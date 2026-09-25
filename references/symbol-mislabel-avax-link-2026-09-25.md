# Symbol Mislabel: AVAX Trades Registered as LINK — 2026-09-25

## Summary
The price-range-based symbol resolver in `crypto-trade-moneda-v3-slots.sh` used
overlapping, too-narrow ranges that caused all AVAX trades with entry price > \$8.0
to be misidentified as LINK. This is a recurrence of the root cause documented in
issue #45.

## Root Cause
Bash `log_trade_to_history()` function (line ~292) spawned a temp Python resolver
with **narrow ranges**:
```python
RANGES = {'AVAX':(4.0, 8.0), 'LINK':(8.0, 30.0)}
```
AVAX traded at \$9–\$13 in late Aug–Sep 2026, so every AVAX entry > \$8.0 fell
into LINK's range → both `symbol` and `coin` fields were set to `LINK`.

## Evidence (cron-AVAX.log)
The AVAX cron job (not the LINK cron job) executed these trades:

| Trade # | Entry | Exit  | PnL   | Close Type  | Date          |
|---------|-------|-------|-------|-------------|---------------|
| #480    | 11.116| 10.815| -$1.02| CLOSED_SL   | 2026-09-23    |
| #481    | 11.101| 10.817| -$0.58| CLOSED_SL   | 2026-09-23    |
| #482    | 11.107| 10.819| -$0.37| CLOSED_SL   | 2026-09-23    |
| #493    | 10.481| 10.219| -$1.15| CLOSED_SL   | 2026-09-25    |

All four show `Resolved symbol: LINK` in `logs/cron-AVAX.log` despite being AVAX
cron executions. The `coin` field was also set to `LINK` (same resolved value).

## Why the Inline History Check Didn't Catch It

The inline resolver at line ~1853 (added in the #45 fix) used wider ranges
`{'AVAX':(5,30), 'LINK':(5,30)}` with a `for...break` loop that should have
resolved to AVAX (first dict match). However the inline Python **crashed silently**
(`2>/dev/null`) — likely because `float('$entry')` failed when `$entry` was
empty/null at runtime — and the fallback `echo "$SYMBOL"` returned a stale/leaked
value. The history check then looked for that stale symbol, found a match, and
passed — allowing the mislabeled trade to persist.

## Fix Applied (2026-09-25)

### 1. Bash function resolver (~line 292)
- Widened AVAX and LINK ranges from `(4.0, 8.0)` / `(8.0, 30.0)` to `(4.0, 30.0)` / `(4.0, 30.0)`
- Added `local_symbol` (authoritative, from cron arg) trust + disambiguation:
  - If `local_symbol` is a known coin AND price is plausible → trust it
  - If price is outside `local_symbol` range → use price for definitive single match; otherwise keep `local_symbol`

### 2. Inline SL-close resolver (~line 1853)
- Same widened ranges `(4.0, 30.0)` for both AVAX and LINK
- Same `local_symbol` trust + disambiguation logic (mirrors the main resolver)

### 3. Python script (`scripts/log_trade_to_history.py`, ~line 84)
- Same range widening and `local_symbol` logic applied to `_resolve_symbol_from_price()`

## Backfill
- All 4 mislabeled trades (#480, #481, #482, #493) corrected in
  `crypto-bots/trade-history.json` from `LINK`→`AVAX` (both `symbol` and `coin` fields)
- `bySymbol` and `byDay` aggregates fully recalculated from trades array
- Stale `exitPrice`/`closeType` removed from AVAX slot 3 state (leftover from Aug 22 SL)

## Verification
- `bash -n` syntax: PASS
- Trade history: 0 mislabeled trades remaining (symbol == coin for all 491 trades)
- Aggregates: AVAX=90 trades, LINK=81 trades (was 86 AVAX, 84 LINK before backfill)

## Files Changed
- `crypto-trade-moneda-v3-slots.sh` — both resolvers fixed (bash function + inline)
- `scripts/log_trade_to_history.py` — Python resolver fixed
- `crypto-bots/trade-history.json` — 4 trades backfilled, aggregates recalculated
- `crypto-bots/AVAX-trade-state.json` — stale close metadata cleaned

## Note on Cron Log Rotation
The cron-AVAX.log only covers Sep 22–25, 2026. Older log files from Aug 2026
have been rotated/archived and are unavailable. Earlier AVAX-as-LINK mislabeling
is visible in the trade history (87 LINK trades with entries in \$8–\$15 range dated
Aug 20–27), but without the original cron logs we cannot authoritatively attribute
each to AVAX vs LINK cron. The 4 trades confirmed via cron-AVAX.log are the ones
backfilled here.

— Perrobotron Aterrorrizando!!
