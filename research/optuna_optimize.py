#!/usr/bin/env python3
"""
Fase 8: Optuna hyperparameter optimization for Perrobotillo strategy (self-contained).

This script REPLACES the original jesse-dependent optuna_optimize.py which
required `jesse.research` (not installed) and Docker (socket blocked).
It uses:
  - pandas / pandas-ta for indicators (no talib needed)
  - Local Binance CSV data from backtest/data/
  - The Perrobotillo strategy logic from strategies/perrobotillo/__init__.py
    and PER_COIN_CONFIG from run_jesse_backtest.py

Key design decisions:
  1. Proper TP/SL exit execution ("fast_mode=False" equivalent):
     - Each candle has OHLC bar.
     - TP1/TP2/TP3 and SL are checked against the candle's HIGH/LOW.
     - If TP is within the bar, the take-profit fires at the exact TP price.
     - If SL is within the bar, stop-loss fires at the exact SL price.
     - This matches Jesse's timestamp_simulator behavior (orders are NOT skipped).
  2. Per-coin config precedence (mirrors per-coin-config.env):
     - PER_COIN_CONFIG values are the defaults.
     - Optuna can override specific HPs; per-coin config still wins for
       position sizing and SL if not in the Optuna search space.
  3. Bull vs bear data period selection via --days flag.
  4. Results saved to workspace/research/ (not /home/research/).

Usage:
  # Single coin (ETH), 30 trials, 1h data
  .openclaw/venv/bin/python3 optuna_optimize.py --coin ETH --trials 30 --tf 1h --days 180

  # All coins, 25 trials each
  .openclaw/venv/bin/python3 optuna_optimize.py --coin ALL --trials 25 --tf 1h --days 180

  # Bear period (90 days starting Jan 2026)
  .openclaw/venv/bin/python3 optuna_optimize.py --coin ETH --trials 30 --days 90
"""

import sys
import os
import json
import argparse
import warnings
import traceback
from datetime import datetime
from pathlib import Path

warnings.filterwarnings('ignore')

# ── Paths ─────────────────────────────────────────────────────────────
WORKSPACE = Path(os.environ.get('WORKSPACE',
                 str(Path.home() / '.openclaw' / 'workspace')))
DATA_DIR = WORKSPACE / 'backtest' / 'data'
RESEARCH_DIR = WORKSPACE / 'research'
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

# ── Per-coin config (mirror of run_jesse_backtest.py PER_COIN_CONFIG) ─
# These are the *live* production overrides from per-coin-config.env.
PER_COIN_CONFIG = {
    "BTC":   {"tp1": 3.0,  "tp2": 6.0,  "tp3": 9.0,  "sl": 3.5, "pos": 10,  "ml_min": 45.0},
    "ETH":   {"tp1": 3.0,  "tp2": 6.0,  "tp3": 9.0,  "sl": 3.0, "pos": 10,  "ml_min": 45.0},
    "BNB":   {"tp1": 2.5,  "tp2": 5.0,  "tp3": 7.5,  "sl": 2.0, "pos": 15,  "ml_min": 40.0},
    "SOL":   {"tp1": 2.5,  "tp2": 5.0,  "tp3": 7.5,  "sl": 2.0, "pos": 15,  "ml_min": 35.0},
    "LINK":  {"tp1": 2.5,  "tp2": 5.0,  "tp3": 7.5,  "sl": 2.0, "pos": 10,  "ml_min": 35.0},
    "XRP":   {"tp1": 2.5,  "tp2": 5.0,  "tp3": 7.5,  "sl": 2.5, "pos": 10,  "ml_min": 35.0},
    "AVAX":  {"tp1": 2.5,  "tp2": 5.0,  "tp3": 7.5,  "sl": 2.0, "pos": 10,  "ml_min": 35.0},
}

# EMA ranges for coin-level validation (entry price disambiguation)
EMA_FAST_DEFAULT = 12
EMA_SLOW_DEFAULT = 140
EMA_TREND_DEFAULT = 200

TP_ALLOCATION = {"tp1": 0.35, "tp2": 0.30, "tp3": 0.35}  # 35% / 30% / 35%

ALL_COINS = list(PER_COIN_CONFIG.keys())


# ── Data loading ──────────────────────────────────────────────────────
def load_csv(coin: str, timeframe: str, days: int) -> "pandas.DataFrame | None":
    """Load 1h CSV and expand to 1m if timeframe='1m'."""
    tf_suffix = f"_{timeframe}"
    path_180 = DATA_DIR / f"{coin}USDT_1h_180days.csv"
    path_90 = DATA_DIR / f"{coin}USDT_1h_90days.csv"

    # Choose file based on days requested
    if days >= 180 and path_180.exists():
        path = path_180
    elif path_90.exists():
        path = path_90
    elif path_180.exists():
        path = path_180
    else:
        print(f"  ⚠️  No CSV for {coin}, skipping")
        return None

    import pandas as pd
    df = pd.read_csv(path)
    # CSV columns: timestamp,open,high,low,close,volume
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df = df.sort_values('timestamp').reset_index(drop=True)

    # Truncate to requested days
    if days < 180:
        max_rows = int(days * 24)  # 24 candles/day at 1h
        df = df.tail(max_rows).reset_index(drop=True)

    if timeframe == '1m':
        df = expand_to_1m(df)

    return df


def expand_to_1m(df):
    """Expand hourly OHLCV to 1-minute candles (60×)."""
    import numpy as np
    import pandas as pd
    from datetime import timedelta

    rows = []
    for _, row in df.iterrows():
        o, h, l, c = float(row['open']), float(row['high']), float(row['low']), float(row['close'])
        v = float(row['volume']) / 60.0
        t_base = row['timestamp']
        prev_close = o

        for minute in range(60):
            t = t_base + timedelta(minutes=minute)
            if minute == 0:
                o_m, c_m = o, o
            elif minute == 59:
                o_m, c_m = prev_close, c
            else:
                o_m = prev_close
                frac = (minute + 1) / 60.0
                c_m = o + (c - o) * frac

            h_m = max(h, o_m, c_m)
            l_m = min(l, o_m, c_m)
            rows.append({
                'timestamp': t, 'open': o_m, 'high': h_m,
                'low': l_m, 'close': c_m, 'volume': v,
            })
            prev_close = c_m

    result = pd.DataFrame(rows)
    return result


# ── Indicators (pandas-ta) ────────────────────────────────────────────
def add_indicators(df, ema_fast=None, ema_slow=None, ema_trend=None):
    """Add EMA, RSI, MACD, ATR, ADX using pandas-ta module-level functions."""
    import numpy as np
    import pandas as pd
    import pandas_ta as ta

    ef = ema_fast or EMA_FAST_DEFAULT
    es = ema_slow or EMA_SLOW_DEFAULT
    et = ema_trend or EMA_TREND_DEFAULT

    df['ema_fast'] = ta.ema(df['close'], length=ef)
    df['ema_slow'] = ta.ema(df['close'], length=es)
    df['ema_trend'] = ta.ema(df['close'], length=et)
    df['rsi'] = ta.rsi(df['close'], length=14)

    macd_df = ta.macd(df['close'], fast=12, slow=26, signal=9)
    # pandas-ta returns DataFrame with 3 cols: MACD, MACD_Signal, MACD_Hist
    if macd_df is not None and macd_df.shape[1] >= 3:
        df['macd_hist'] = macd_df.iloc[:, 2]
    else:
        df['macd_hist'] = 0.0

    # Volume SMA + ratio
    df['vol_sma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_sma20'].replace(0, np.nan)
    df['vol_ratio'] = df['vol_ratio'].fillna(1.0)

    # Drop NaN rows from indicator warmup
    df = df.dropna(subset=['ema_fast', 'ema_slow', 'ema_trend', 'rsi']).reset_index(drop=True)
    return df


def ml_confidence_proxy(row, ema_fast_val, ema_slow_val, rsi_val, vol_ratio, ema_trend_val):
    """
    Proxy for Perrobotillo's ML validator confidence score (0-100).
    Mirrors ml_confidence_proxy() from strategies/perrobotillo/__init__.py.
    """
    import numpy as np
    score = 50.0  # base

    # EMA alignment
    if ema_fast_val > ema_slow_val:
        score += 15
    else:
        score -= 15

    # RSI in healthy range
    if 30 < rsi_val < 70:
        score += 10
    elif rsi_val > 70:
        score -= 20
    elif rsi_val < 30:
        score -= 10

    # Volume confirmation
    if vol_ratio >= 1.0:
        score += 5
    else:
        score -= 5

    # EMA trend (price above EMA200 = bullish bias)
    close = row['close']
    if close > ema_trend_val:
        score += 7
    else:
        score -= 10

    return float(np.clip(score, 0, 100))


# ── Backtest engine ───────────────────────────────────────────────────
class PerrobotilloBacktest:
    """
    Self-contained backtest engine implementing Perrobotillo's strategy:

    Entry:
      - EMA fast > EMA slow (bullish alignment)
      - Price > EMA slow (trend filter)
      - ML proxy confidence >= threshold
    Exit (multi-TP + SL):
      - TP1: 35% of position closed at entry * (1 + tp1_pct/100)
      - TP2: 30% of position closed at entry * (1 + tp2_pct/100)
      - TP3: 35% of position closed at entry * (1 + tp3_pct/100)
      - SL:  full exit at entry * (1 - sl_pct/100)

    "fast_mode=False" equivalent: each candle bar (OHLC) is checked.
    If TP/SL price falls within [low, high] of the candle, the exit
    executes at the exact TP/SL price (LIMIT fill).
    """

    def __init__(self, hp: dict, coin_config: dict, initial_capital: float = 10000.0, fee: float = 0.001):
        self.hp = hp
        self.coin_config = coin_config
        self.initial_capital = initial_capital
        self.fee = fee
        self.trades = []
        self.equity_curve = [initial_capital]

    def run(self, df):
        cash = self.initial_capital
        active_position = None  # {'entry_price', 'qty', 'remaining_qty', 'tp1_done', 'tp2_done', 'tp3_done', 'entry_time'}

        for i in range(len(df)):
            row = df.iloc[i]
            ohlc = [row['open'], row['high'], row['low'], row['close']]
            o, h, l, c = ohlc

            # ── Manage active position ──
            if active_position is not None:
                ep = active_position['entry_price']
                remaining = active_position['remaining_qty']
                pos_value = remaining * c  # current value (unused but kept for debug)

                # Check SL (highest priority — happens first)
                sl_price = ep * (1 - self.hp['stop_loss_percent'] / 100)
                if l <= sl_price <= h:
                    exit_value = active_position['remaining_qty'] * sl_price
                    fee_cost = exit_value * self.fee
                    cash += exit_value - fee_cost
                    self.trades.append(self._make_trade(
                        active_position, 'SL', sl_price, exit_value, fee_cost, i, row
                    ))
                    active_position = None
                    self.equity_curve.append(cash)
                    continue

                # Check TP1
                tp1_price = ep * (1 + self.hp['tp1_percent'] / 100)
                if not active_position['tp1_done'] and l <= tp1_price <= h:
                    portion = TP_ALLOCATION['tp1']
                    exit_qty = active_position['orig_qty'] * portion
                    exit_value = exit_qty * tp1_price
                    fee_cost = exit_value * self.fee
                    cash += exit_value - fee_cost
                    active_position['remaining_qty'] -= exit_qty
                    active_position['remaining_stake'] -= active_position['orig_stake'] * portion
                    active_position['tp1_done'] = True
                    self.trades.append(self._make_trade(
                        active_position, 'TP1', tp1_price, exit_value, fee_cost, i, row,
                        partial=True, portion=portion
                    ))
                    if active_position['remaining_qty'] <= 1e-9:
                        active_position = None
                        self.equity_curve.append(cash)
                        continue

                # Check TP2
                tp2_price = ep * (1 + self.hp['tp2_percent'] / 100)
                if not active_position['tp2_done'] and l <= tp2_price <= h:
                    portion = TP_ALLOCATION['tp2']
                    exit_qty = active_position['orig_qty'] * portion
                    exit_value = exit_qty * tp2_price
                    fee_cost = exit_value * self.fee
                    cash += exit_value - fee_cost
                    active_position['remaining_qty'] -= exit_qty
                    active_position['remaining_stake'] -= active_position['orig_stake'] * portion
                    active_position['tp2_done'] = True
                    self.trades.append(self._make_trade(
                        active_position, 'TP2', tp2_price, exit_value, fee_cost, i, row,
                        partial=True, portion=portion
                    ))
                    if active_position['remaining_qty'] <= 1e-9:
                        active_position = None
                        self.equity_curve.append(cash)
                        continue

                # Check TP3
                tp3_price = ep * (1 + self.hp['tp3_percent'] / 100)
                if not active_position['tp3_done'] and l <= tp3_price <= h:
                    portion = TP_ALLOCATION['tp3']
                    exit_qty = active_position['orig_qty'] * portion
                    exit_value = exit_qty * tp3_price
                    fee_cost = exit_value * self.fee
                    cash += exit_value - fee_cost
                    active_position['remaining_qty'] -= exit_qty
                    active_position['remaining_stake'] -= active_position['orig_stake'] * portion
                    active_position['tp3_done'] = True
                    self.trades.append(self._make_trade(
                        active_position, 'TP3', tp3_price, exit_value, fee_cost, i, row,
                        partial=True, portion=portion
                    ))
                    if active_position['remaining_qty'] <= 1e-9:
                        active_position = None
                        self.equity_curve.append(cash)
                        continue

            # ── Check entry signal ──
            if active_position is None:
                ema_fast = float(row.get('ema_fast', 0))
                ema_slow = float(row.get('ema_slow', 0))
                ema_trend = float(row.get('ema_trend', 0))
                rsi = float(row.get('rsi', 50))
                vol_ratio = float(row.get('vol_ratio', 1.0))

                # Entry logic from perrobotillo strategy (should_long)
                if ema_fast > ema_slow and c > ema_slow:
                    confidence = ml_confidence_proxy(
                        row, ema_fast, ema_slow, rsi, vol_ratio, ema_trend
                    )
                    ml_min = self.hp.get('ml_min_confidence',
                                         self.coin_config.get('ml_min', 40.0))
                    if confidence >= ml_min:
                        # Position size
                        pos_pct = self.hp.get('position_size_percent',
                                              self.coin_config.get('pos', 10.0))
                        stake = cash * (pos_pct / 100)
                        if stake >= 10:  # min $10
                            qty = stake / c
                            active_position = {
                                'entry_price': c,
                                'remaining_qty': qty,
                                'orig_qty': qty,
                                'tp1_done': False,
                                'tp2_done': False,
                                'tp3_done': False,
                                'entry_time': row['timestamp'],
                                'entry_idx': i,
                                'stake': stake,
                                'orig_stake': stake,
                                'remaining_stake': stake,
                            }
                            fee_cost = stake * self.fee
                            cash -= stake + fee_cost  # buy fee deducted from cash

            self.equity_curve.append(cash)

        # Close any remaining position at last price
        if active_position is not None:
            exit_value = active_position['remaining_qty'] * c
            fee_cost = exit_value * self.fee
            cash += exit_value - fee_cost
            self.trades.append(self._make_trade(
                active_position, 'MARKET_CLOSE', c, exit_value, fee_cost, i, row
            ))

        return self._calculate_results()

    def _make_trade(self, pos, exit_type, exit_price, exit_value, fee, idx, row,
                    partial=False, portion=0.0):
        return {
            'coin': self.coin_config.get('coin', ''),
            'entry_time': pos['entry_time'],
            'exit_time': row['timestamp'],
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'stake': pos['orig_stake'] * portion if partial else pos['remaining_stake'],
            'exit_type': exit_type,
            'pnl_usdt': exit_value - (pos['orig_stake'] * portion if partial else pos['remaining_stake']) - fee,
            'pnl_pct': ((exit_price / pos['entry_price']) - 1) * 100,
            'is_partial': partial,
        }

    def _calculate_results(self):
        import numpy as np
        if not self.trades:
            return {
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                'win_rate': 0, 'net_profit': 0, 'net_profit_pct': 0,
                'max_drawdown': 0, 'sharpe_ratio': 0, 'final_value': self.initial_capital,
                'trades': [],
            }

        total_trades = len(self.trades)
        winning = [t for t in self.trades if t['exit_type'] in ('TP1', 'TP2', 'TP3')]
        losing = [t for t in self.trades if t['exit_type'] == 'SL']

        total_pnl = sum(t['pnl_usdt'] for t in self.trades)
        win_rate = len(winning) / total_trades * 100 if total_trades > 0 else 0

        # Sharpe ratio (per-trade returns, annualized at ~252 trades/year)
        returns = [t['pnl_usdt'] / self.initial_capital for t in self.trades]
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(252))
        else:
            sharpe = 0.0

        # Max drawdown from equity curve
        eq = np.array(self.equity_curve)
        peak = np.maximum.accumulate(eq)
        drawdown = (peak - eq) / peak * 100
        max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        return {
            'total_trades': total_trades,
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': round(win_rate, 2),
            'net_profit': round(total_pnl, 2),
            'net_profit_pct': round(total_pnl / self.initial_capital * 100, 2),
            'max_drawdown': round(max_dd, 2),
            'sharpe_ratio': round(float(sharpe), 4),
            'final_value': round(self.equity_curve[-1], 2),
            'avg_trade_pnl': round(total_pnl / total_trades, 2) if total_trades > 0 else 0,
            'trades': self.trades,
        }


# ── Optuna objective ──────────────────────────────────────────────────
def objective(trial, coin: str, df, timeframe: str, days: int):
    """Optuna objective: maximize Sharpe ratio."""
    cfg = PER_COIN_CONFIG.get(coin, PER_COIN_CONFIG['ETH'])

    # Search space — mirrors perrobotillo strategy hyperparameters
    hp = {
        'ema_fast':           trial.suggest_int('ema_fast', 8, 30),
        'ema_slow':           trial.suggest_int('ema_slow', 50, 200),
        'ema_trend':          trial.suggest_int('ema_trend', 100, 300),
        'tp1_percent':        trial.suggest_float('tp1_percent', 1.0, 6.0),
        'tp2_percent':        trial.suggest_float('tp2_percent', 2.0, 12.0),
        'tp3_percent':        trial.suggest_float('tp3_percent', 3.0, 18.0),
        'stop_loss_percent':  trial.suggest_float('stop_loss_percent', 1.5, 6.0),
        'ml_min_confidence':  trial.suggest_float('ml_min_confidence', 30.0, 60.0),
        'position_size_percent': trial.suggest_float('position_size_percent', 5.0, 25.0),
    }

    # Ensure ema_fast < ema_slow
    if hp['ema_fast'] >= hp['ema_slow'] - 10:
        # Penalize overlapping EMAs
        hp['ema_slow'] = hp['ema_fast'] + 20

    # Add indicators with current HPs (pass EMA values directly, no globals)
    df_with_ind = add_indicators(df.copy(),
                                 ema_fast=hp['ema_fast'],
                                 ema_slow=hp['ema_slow'],
                                 ema_trend=hp['ema_trend'])

    coin_config = {**cfg, 'coin': coin}
    engine = PerrobotilloBacktest(hp=hp, coin_config=coin_config,
                                  initial_capital=10000.0, fee=0.001)

    try:
        result = engine.run(df_with_ind)
        sharpe = result['sharpe_ratio']
        total_trades = result['total_trades']

        # Penalty for 0 trades
        if total_trades == 0:
            trial.set_user_attr('total_trades', 0)
            trial.set_user_attr('net_profit', 0)
            trial.set_user_attr('win_rate', 0)
            trial.set_user_attr('max_drawdown', 0)
            return -999.0

        trial.set_user_attr('total_trades', total_trades)
        trial.set_user_attr('net_profit', result['net_profit'])
        trial.set_user_attr('win_rate', result['win_rate'])
        trial.set_user_attr('max_drawdown', result['max_drawdown'])
        trial.set_user_attr('tp_hits', result['winning_trades'])
        trial.set_user_attr('sl_hits', result['losing_trades'])
        return sharpe

    except Exception as e:
        trial.set_user_attr('error', str(e))
        return -999.0


def optimize_single_coin(coin: str, trials: int, timeframe: str, days: int):
    """Run Optuna optimization for a single coin."""
    import optuna
    import pandas as pd

    print(f"\n{'='*60}")
    print(f"  Optuna Optimization: {coin}-USDT | {trials} trials | {timeframe} | {days}d")
    print(f"{'='*60}\n")

    df = load_csv(coin, timeframe, days)
    if df is None or len(df) == 0:
        print(f"  ❌ No data for {coin}")
        return None

    print(f"  📊 Data: {len(df)} candles ({df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]})")
    print(f"  🚀 Running {trials} Optuna trials (objective = Sharpe)...\n")

    study = optuna.create_study(
        direction='maximize',
        study_name=f'perrobotillo_{coin}_{timeframe}',
    )

    def optuna_obj(trial):
        return objective(trial, coin, df, timeframe, days)

    study.optimize(optuna_obj, n_trials=trials, show_progress_bar=False)

    print(f"\n  ✅ Completed {len(study.trials)} trials")
    print(f"  🏆 Best Sharpe: {study.best_value:.4f}")
    print(f"  🎯 Best HPs:")
    for k, v in study.best_params.items():
        print(f"      {k}: {v}")

    # Get best trial details
    best_trial = study.best_trial
    test_metrics = {
        'total_trades': best_trial.user_attrs.get('total_trades', 0),
        'net_profit': best_trial.user_attrs.get('net_profit', 0),
        'win_rate': best_trial.user_attrs.get('win_rate', 0),
        'max_drawdown': best_trial.user_attrs.get('max_drawdown', 0),
        'tp_hits': best_trial.user_attrs.get('tp_hits', 0),
        'sl_hits': best_trial.user_attrs.get('sl_hits', 0),
    }
    print(f"  📊 Best trial metrics: {test_metrics}")

    # Save results
    results = {
        'coin': coin,
        'timeframe': timeframe,
        'days': days,
        'n_trials': len(study.trials),
        'best_value': study.best_value,
        'best_params': study.best_params,
        'best_trial_metrics': test_metrics,
        'all_trials': [
            {
                'trial': t.number,
                'params': t.params,
                'value': t.value,
                'user_attrs': t.user_attrs,
                'state': str(t.state),
            }
            for t in study.trials
        ],
        'created_at': datetime.now().isoformat(),
    }

    out_path = RESEARCH_DIR / f'optuna_optimize_{coin}_{timeframe}_{days}d.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  💾 Saved: {out_path}")

    return results


def optimize_all_coins(trials: int, timeframe: str, days: int):
    """Run Optuna for all coins, using per-coin config."""
    all_results = {}

    for coin in ALL_COINS:
        result = optimize_single_coin(coin, trials, timeframe, days)
        if result:
            all_results[coin] = result

    # Summary
    print(f"\n{'='*60}")
    print("  📊 RESUMEN TOTAL")
    print(f"{'='*60}")
    print(f"{'Coin':>6s} | {'Sharpe':>8s} | {'Trades':>6s} | {'Win%':>6s} | {'PnL':>10s} | {'MaxDD':>6s}")
    print(f"{'-'*60}")
    for coin, result in all_results.items():
        print(f"{coin:>6s} | {result['best_value']:>8.4f} | "
              f"{result['best_trial_metrics']['total_trades']:>6d} | "
              f"{result['best_trial_metrics']['win_rate']:>6.1f} | "
              f"${result['best_trial_metrics']['net_profit']:>9.2f} | "
              f"{result['best_trial_metrics']['max_drawdown']:>6.2f}%")

    # Save combined results
    combined_path = RESEARCH_DIR / f'optuna_optimize_all_{timeframe}_{days}d.json'
    with open(combined_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  💾 Combined results: {combined_path}")

    return all_results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Optuna optimization for Perrobotillo strategy')
    parser.add_argument('--coin', default='ETH', choices=ALL_COINS + ['ALL'],
                        help='Coin to optimize (default: ETH)')
    parser.add_argument('--trials', type=int, default=25,
                        help='Number of Optuna trials (default: 25)')
    parser.add_argument('--tf', default='1h', choices=['1h', '1m'],
                        help='Timeframe (default: 1h)')
    parser.add_argument('--days', type=int, default=180,
                        help='Days of data to use (180 for full period, 90 for bear market)')
    args = parser.parse_args()

    if args.coin == 'ALL':
        optimize_all_coins(args.trials, args.tf, args.days)
    else:
        optimize_single_coin(args.coin, args.trials, args.tf, args.days)
