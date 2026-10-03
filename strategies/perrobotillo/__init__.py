"""
Perrobotillo Strategy for Jesse AI Research Lab
=================================================

Replicates Perrobotillo Trading Bot's production trading logic.

Entry logic:
  1. Market mode detection (F&G proxy + EMA20 + RSI on BTC)
  2. ML validator proxy (technical indicators → confidence score)
  3. Per-coin TP/SL/position sizing overrides

Exit logic:
  - TP1 (35%): primer take profit
  - TP2 (30%): segundo take profit
  - TP3 (30%): tercer take profit
  - SL: stop loss basado en market mode

Per-coin overrides (from per-coin-config.env):
  BTC:  TP1=3.0, TP2=6.0, TP3=9.0,  SL=3.5, POS=10, ML_MIN=45
  ETH:  TP1=3.0, TP2=6.0, TP3=9.0,  SL=3.0, POS=10, ML_MIN=45
  BNB:  TP1=2.5, TP2=5.0, TP3=7.5,  SL=2.0, POS=15, ML_MIN=40
  SOL:  TP1=2.5, TP2=5.0, TP3=7.5,  SL=2.0, POS=15, ML_MIN=35
  LINK: TP1=2.5, TP2=5.0, TP3=7.5,  SL=2.0, POS=10, ML_MIN=35
  XRP:  TP1=2.5, TP2=5.0, TP3=7.5,  SL=2.5, POS=10, ML_MIN=35
  AVAX: TP1=2.5, TP2=5.0, TP3=7.5,  SL=2.0, POS=10, ML_MIN=35
"""

from jesse.strategies import Strategy, cached
import jesse.indicators as ta
from jesse import utils
import os
import numpy as np


# ============================================================================
# MARKET MODE PARAMETERS (mirror de market-sentiment.sh + dynamic-config.env)
# ============================================================================
MODE_PARAMS = {
    'BULL':          {'tp1': 3.0,  'tp2': 6.0,  'tp3': 10.0, 'sl': 4.0,  'pos': 25,  'trailing': False},
    'BEAR':          {'tp1': 1.8,  'tp2': 3.5,  'tp3': 5.5,  'sl': 2.5,  'pos': 10,  'trailing': False},
    'LATERAL':       {'tp1': 1.5,  'tp2': 3.0,  'tp3': 5.0,  'sl': 3.5,  'pos': 10,  'trailing': False},
    'VOLATILE_BULL': {'tp1': 3.5,  'tp2': 7.0,  'tp3': 12.0, 'sl': 5.0,  'pos': 15,  'trailing': False},
    'VOLATILE_BEAR': {'tp1': 1.8,  'tp2': 3.5,  'tp3': 5.5,  'sl': 2.5,  'pos': 10,  'trailing': False},
    'LATERAL_BULL':  {'tp1': 1.5,  'tp2': 3.0,  'tp3': 5.0,  'sl': 3.5,  'pos': 10,  'trailing': False},
}

# Per-coin overrides (from per-coin-config.env)
COIN_OVERRIDES = {
    'BTC':  {'tp1': 3.0,  'tp2': 6.0,  'tp3': 9.0,  'sl': 3.5,  'pos': 10, 'ml_min': 45},
    'ETH':  {'tp1': 3.0,  'tp2': 6.0,  'tp3': 9.0,  'sl': 3.0,  'pos': 10, 'ml_min': 45},
    'BNB':  {'tp1': 2.5,  'tp2': 5.0,  'tp3': 7.5,  'sl': 2.0,  'pos': 15, 'ml_min': 40},
    'SOL':  {'tp1': 2.5,  'tp2': 5.0,  'tp3': 7.5,  'sl': 2.0,  'pos': 15, 'ml_min': 35},
    'LINK': {'tp1': 2.5,  'tp2': 5.0,  'tp3': 7.5,  'sl': 2.0,  'pos': 10, 'ml_min': 35},
    'XRP':  {'tp1': 2.5,  'tp2': 5.0,  'tp3': 7.5,  'sl': 2.5,  'pos': 10, 'ml_min': 35},
    'AVAX': {'tp1': 2.5,  'tp2': 5.0,  'tp3': 7.5,  'sl': 2.0,  'pos': 10, 'ml_min': 35},
}

# TP allocation percentages (35% / 30% / 30%)
TP1_PCT = 0.35
TP2_PCT = 0.30
TP3_PCT = 0.30

# In production, BTC is suspended due to ML model review (issue #30)
# In research/backtesting, enable all coins for comparison
ENABLE_BTC = True  # Set to False for production parity


class perrobotillo(Strategy):
    # ------------------------------------------------------------------ #
    # ML MODE: "gather" = collect features/labels for ML training (Fase 5)
    #          "trade"  = normal operation (no ML data collection)
    # ------------------------------------------------------------------ #
    ml_mode = os.environ.get("JESSE_ML_MODE", "trade")

    # ------------------------------------------------------------------ #
    # MARKET MODE DETECTION
    # ------------------------------------------------------------------ #
    # Uses BTC technicals as Fear & Greed proxy
    # F&G proxy = EMA cross direction + RSI + price vs EMA

    @property
    def btc_candles(self):
        """Get BTC 1h candles for market mode detection."""
        try:
            c = self.get_candles('Binance Spot', 'BTC-USDT', '1h')
            if c is None or len(c) < 20:
                return None
            return c
        except Exception as e:
            print(f'[DEBUG btc_candles ERROR] {e}')
            return None

    @property
    def btc_ema20(self):
        c = self.btc_candles
        if c is None:
            return 0
        return ta.ema(c, 20)

    @property
    def btc_price(self):
        """Last close price of BTC."""
        c = self.btc_candles
        if c is None:
            return 0
        return c[-1][2]

    @property
    def btc_rsi(self):
        c = self.btc_candles
        if c is None:
            return 50
        return ta.rsi(c, 14)

    @property
    def btc_ema50(self):
        c = self.btc_candles
        if c is None:
            return 0
        return ta.ema(c, 50)

    @property
    def btc_ema_cross(self):
        """EMA20 vs EMA50 cross for F&G proxy"""
        return self.btc_ema20 - self.btc_ema50

    @property
    def fear_greed_proxy(self):
        """
        Proxy for Fear & Greed Index using BTC technicals.
        Maps to 0-100 scale similar to Alternative.me F&G.
        """
        ema20 = self.btc_ema20
        ema50_val = self.btc_ema50
        rsi = self.btc_rsi
        close = self.btc_price

        fg = 50.0  # neutral base

        # EMA cross: bullish if price > EMA20 > EMA50
        if close > ema20 and ema20 > ema50_val:
            fg += 20
        elif close < ema20 and ema20 < ema50_val:
            fg -= 20

        # RSI contribution
        if rsi > 70:
            fg += 10
        elif rsi < 30:
            fg -= 10

        # EMA cross momentum
        cross = self.btc_ema_cross
        if cross > 0:
            fg += 5
        else:
            fg -= 5

        return np.clip(fg, 0, 100)

    @property
    def coin(self):
        """Extract bare coin name from symbol (BTC-USDT -> BTC)."""
        return self.symbol.split('-')[0]

    @property
    def per_coin_config(self):
        """Get per-coin overrides, falling back to market mode defaults."""
        coin = self.coin
        cfg = COIN_OVERRIDES.get(coin, {})
        mode = self.detected_market_mode
        mode_cfg = MODE_PARAMS[mode]

        result = {
            'tp1': cfg.get('tp1', mode_cfg['tp1']),
            'tp2': cfg.get('tp2', mode_cfg['tp2']),
            'tp3': cfg.get('tp3', mode_cfg['tp3']),
            'sl': cfg.get('sl', mode_cfg['sl']),
            'pos': cfg.get('pos', mode_cfg['pos']),
            'ml_min': cfg.get('ml_min', 40),
            'trailing': mode_cfg['trailing'],
        }
        return result

    @property
    def detected_market_mode(self):
        """
        Detect market mode (same logic as market-sentiment.sh):
        - BEAR: F&G < 40 AND price < EMA20
        - BULL: F&G > 60 AND price > EMA20
        - VOLATILE_BULL: RSI > 70
        - VOLATILE_BEAR: RSI < 30
        - LATERAL: default
        - LATERAL_BULL: price above EMA but F&G not strong enough for full BULL
        """
        fg = self.fear_greed_proxy
        btc_close = self.btc_price
        btc_ema20 = self.btc_ema20
        rsi = self.btc_rsi

        # VOLATILE conditions take priority
        if rsi > 70:
            return 'VOLATILE_BULL'
        if rsi < 30:
            return 'VOLATILE_BEAR'

        # BEAR / BULL
        if fg < 40 and btc_close < btc_ema20:
            return 'BEAR'
        if fg > 60 and btc_close > btc_ema20:
            return 'BULL'

        # LATERAL_BULL: price above EMA but FG in neutral range
        if btc_close > btc_ema20 and 40 <= fg <= 60:
            return 'LATERAL_BULL'

        return 'LATERAL'

    # ------------------------------------------------------------------ #
    # ENTRY INDICATORS (proxy para ML validator)
    # ------------------------------------------------------------------ #
    # En Fase 2, usamos indicadores técnicos como proxy del ML validator.
    # En Fase 5, reemplazaremos con el modelo pkl real de Perrobotillo.
    # En esta versión de Jesse, todas las funciones ta.* devuelven el valor
    # final (escalar), no un array completo.

    @cached
    def rsi(self):
        return ta.rsi(self.candles, 14)

    @property
    def ema_fast(self):
        return ta.ema(self.candles, self.hp['ema_fast'])

    @property
    def ema_slow(self):
        return ta.ema(self.candles, self.hp['ema_slow'])

    @property
    def ema_cross(self):
        return self.ema_fast - self.ema_slow

    @property
    def macd_result(self):
        # Returns tuple of 3 scalars: (macd, signal, histogram)
        return ta.macd(self.candles)

    @property
    def macd_hist(self):
        return self.macd_result[2]

    @property
    def adx(self):
        return ta.adx(self.candles, 14)

    @property
    def atr(self):
        return ta.atr(self.candles, 14)

    @property
    def volume_sma(self):
        vol = self.candles[:, 5]
        if len(vol) < 20:
            return vol[-1]
        return float(np.mean(vol[-20:]))

    @property
    def volume_ratio(self):
        """Current volume vs 20-period average"""
        current_vol = self.candles[-1][5]
        avg_vol = self.volume_sma
        if avg_vol == 0:
            return 1.0
        return current_vol / avg_vol

    @property
    def sma_50(self):
        return ta.sma(self.candles, 50)

    @property
    def boll_width(self):
        """Bollinger Bands width (volatility measure)."""
        bb = ta.bollinger_bands(self.candles, 20, 2)
        # bb returns tuple of 3 scalars: (upper, middle, lower)
        upper, middle, lower = bb[0], bb[1], bb[2]
        if middle != 0:
            return (upper - lower) / middle
        return 0

    @property
    def returns(self):
        """Price returns (similar to Perrobotillo's returns feature)."""
        close = self.candles[-1][2]
        open_price = self.candles[-1][1]
        if open_price != 0:
            return (close - open_price) / open_price
        return 0

    @property
    def volatility_20(self):
        """20-period volatility (similar to Perrobotillo's volatility_20 feature)."""
        close = self.candles[-1][2]
        closes = self.candles[-20:, 2]
        if len(closes) > 1 and close != 0:
            return float(np.std(closes) / close * 100)
        return 0

    def ml_confidence_proxy(self):
        """
        Proxy for Perrobotillo's ML validator confidence score.
        Combines technical indicators to produce a 0-100 confidence.
        Uses hyperparameters for RSI/ADX thresholds (optimized by Optuna).
        """
        score = 50.0  # base

        # EMA alignment (strong filter)
        if self.ema_fast > self.ema_slow:
            score += 15  # bullish alignment
        else:
            score -= 15

        # RSI in healthy range (thresholds from hyperparameters)
        rsi_val = self.rsi()
        rsi_overbought = self.hp.get('rsi_overbought', 75)
        rsi_oversold = self.hp.get('rsi_oversold', 30)
        if rsi_oversold < rsi_val < rsi_overbought:
            score += 10
        elif rsi_val > rsi_overbought:
            score -= 20
        elif rsi_val < rsi_oversold:
            score -= 10

        # Volume confirmation
        vr = self.volume_ratio
        if vr >= 1.0:
            score += 5
        else:
            score -= 5

        # ADX trend strength (threshold from hyperparameters)
        adx_val = self.adx
        min_adx = self.hp.get('min_adx', 20)
        if adx_val > min_adx:
            score += 8
        else:
            score -= 3

        # BTC trend filter
        if self.btc_price > self.btc_ema20:
            score += 7
        else:
            score -= 10

        # Fear & Greed proxy
        fg = self.fear_greed_proxy
        if fg > 60:
            score += 5
        elif fg < 40:
            score -= 10

        score = float(np.clip(score, 0, 100))
        return score

    # ------------------------------------------------------------------ #
    # JESSE STRATEGY METHODS
    # ------------------------------------------------------------------ #

    def filters(self):
        """Market mode filters (executed before should_long/should_short)."""
        return [self.filter_market_mode, self.filter_ml_proxy]

    def filter_market_mode(self):
        """Accept all market modes (position sizing handles BEAR mode)."""
        return True

    def filter_ml_proxy(self):
        """ML validator proxy: reject if confidence below threshold."""
        score = self.ml_confidence_proxy()
        ml_min = self.hp.get('ml_min_confidence', 40)
        return score >= ml_min

    def should_long(self) -> bool:
        """Entry logic mirroring Perrobotillo's execute_long -> ML validator approval."""
        coin = self.coin

        if not self.is_coin_enabled(coin):
            return False

        # ML validator proxy
        score = self.ml_confidence_proxy()
        ml_min = self.hp.get('ml_min_confidence', 40)

        if score < ml_min:
            return False

        # EMA cross confirmation
        if self.ema_fast <= self.ema_slow:
            return False

        # Price above EMA (trend filter)
        if self.close <= self.ema_slow:
            return False

        return True

    def should_short(self) -> bool:
        return False

    def should_cancel_entry(self) -> bool:
        return True

    def is_coin_enabled(self, coin: str) -> bool:
        """Check per-coin enabled status."""
        if coin == 'BTC' and not ENABLE_BTC:
            return False
        return True

    def go_long(self):
        """
        Entry: market order at current price.
        Sets TP1 (35%), TP2 (30%), TP3 (30%), and SL.
        For spot trading, TPs and SL go in on_open_position(), not go_long().
        """
        entry_price = self.price
        balance = self.balance
        position_percent = self.hp.get('position_size_percent', 10.0)

        # Calculate order value and quantity
        order_value = balance * (position_percent / 100)
        qty = utils.size_to_qty(order_value, entry_price, fee_rate=self.fee_rate)

        # Entry (spot trading: only buy here)
        self.buy = qty, entry_price

    def on_open_position(self, order):
        """Set TP/SL after position is opened (spot trading requirement)."""
        entry_price = self.average_entry_price
        qty = self.position.qty

        # TP levels (from hyperparameters for Optuna optimization)
        tp1_price = entry_price * (1 + self.hp.get('tp1_percent', 3.0) / 100)
        tp2_price = entry_price * (1 + self.hp.get('tp2_percent', 6.0) / 100)
        tp3_price = entry_price * (1 + self.hp.get('tp3_percent', 9.0) / 100)

        # Stop loss
        sl_price = entry_price * (1 - self.hp.get('stop_loss_percent', 3.5) / 100)

        # Partial take profits: 35% / 30% / 30%
        qty_tp1 = qty * TP1_PCT
        qty_tp2 = qty * TP2_PCT
        qty_tp3 = qty * TP3_PCT

        self.take_profit = [
            (qty_tp1, tp1_price),
            (qty_tp2, tp2_price),
            (qty_tp3, tp3_price),
        ]
        self.stop_loss = qty, sl_price

    def on_close_position(self, order, closed_trade):
        """Record trade-level label in gather mode.

        If after() already consumed the current data point (it has a
        price_direction label), this is a no-op — no warning.
        """
        if self.ml_mode == "gather" and self._current_ml_point is not None:
            self.record_label('is_profitable', closed_trade.pnl > 0)

    def go_short(self):
        pass

    def update_position(self):
        """Trailing stop logic (ATR-based, when enabled)."""
        cfg = self.per_coin_config

        if cfg.get('trailing', False) and self.position.is_long:
            current_atr = self.atr
            entry_price = self.average_entry_price
            current_price = self.price

            # Trailing stop at 2x ATR below current price
            trailing_sl = current_price - (current_atr * 2)

            # Only move SL up, never down
            current_sl = entry_price * (1 - cfg['sl'] / 100)
            if trailing_sl > current_sl:
                self.stop_loss = self.position.qty, trailing_sl

    def before(self):
        """Called before each candle. Record ML features in gather mode."""
        if self.ml_mode == "gather":
            self.record_features(self.get_ml_features())

    def after(self):
        """Called after each candle.

        In gather mode, label each candle's data point with price direction
        (close > prev_close) to maximize data collection.

        Issue #44: with EMA 12/140 entry filter, only ~19 trades close in 2 years
        of 1h data — insufficient for ML training (need ≥50). By labeling EVERY
        candle in after(), we yield ~17k data points per coin from the same
        backtest. Trade-level labels (on_close_position) and candle-level labels
        (after) are compatible: both are booleans, prepare_xy converts to 0/1.

        If a trade closed this candle, on_close_position() already consumed the
        open data point, so _current_ml_point is None here and we skip.
        """
        if self.ml_mode == "gather" and self._current_ml_point is not None:
            if len(self.candles) >= 2:
                close = float(self.candles[-1][2])
                prev_close = float(self.candles[-2][2])
                self.record_label('price_direction', close > prev_close)

    def hyperparameters(self):
        """Hyperparameters para Optuna optimization."""
        return [
            {'name': 'tp1_percent', 'type': float, 'min': 1.0, 'max': 10.0, 'default': 3.0},
            {'name': 'tp2_percent', 'type': float, 'min': 2.0, 'max': 15.0, 'default': 14.4},
            {'name': 'tp3_percent', 'type': float, 'min': 3.0, 'max': 20.0, 'default': 18.2},
            {'name': 'stop_loss_percent', 'type': float, 'min': 1.0, 'max': 10.0, 'default': 7.2},
            {'name': 'position_size_percent', 'type': float, 'min': 5.0, 'max': 30.0, 'default': 18.0},
            {'name': 'ml_min_confidence', 'type': float, 'min': 40.0, 'max': 90.0, 'default': 55.0},
            {'name': 'ema_fast', 'type': int, 'min': 5, 'max': 50, 'default': 12},
            {'name': 'ema_slow', 'type': int, 'min': 20, 'max': 200, 'default': 140},
            {'name': 'rsi_overbought', 'type': int, 'min': 60, 'max': 85, 'default': 75},
            {'name': 'rsi_oversold', 'type': int, 'min': 15, 'max': 45, 'default': 30},
            {'name': 'min_adx', 'type': int, 'min': 15, 'max': 40, 'default': 20},
        ]

    # ------------------------------------------------------------------ #
    # ML FEATURE RECORDING (para Fase 5 — Jesse ML Pipeline)
    # ------------------------------------------------------------------ #

    def get_ml_features(self):
        """Return all ML features matching Perrobotillo's feature set."""
        candles = self.candles
        close = candles[:, 2]
        high = candles[:, 3]
        low = candles[:, 4]
        volume = candles[:, 5]

        features = {}

        # OHLCV
        features['open'] = float(candles[-1][1])
        features['high'] = float(high[-1])
        features['low'] = float(low[-1])
        features['close'] = float(close[-1])
        features['volume'] = float(volume[-1])

        # Core indicators (all return scalars in this Jesse version)
        features['rsi'] = float(ta.rsi(candles, 14))
        macd_result = ta.macd(candles)
        features['macd'] = float(macd_result[0])
        features['macdsignal'] = float(macd_result[1])
        features['macdhist'] = float(macd_result[2])

        bb = ta.bollinger_bands(candles, 20, 2)
        features['bb_upper'] = float(bb[0])
        features['bb_middle'] = float(bb[1])
        features['bb_lower'] = float(bb[2])
        if features['bb_upper'] != features['bb_lower']:
            features['bb_percent'] = (features['close'] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])
            features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / features['bb_middle']
        else:
            features['bb_percent'] = 0
            features['bb_width'] = 0

        features['sma_20'] = float(ta.sma(candles, 20))
        features['sma_50'] = float(ta.sma(candles, 50))
        features['ema_12'] = float(ta.ema(candles, 12))
        features['ema_26'] = float(ta.ema(candles, 26))
        features['atr'] = float(ta.atr(candles, 14))
        features['adx'] = float(ta.adx(candles, 14))

        stoch = ta.stoch(candles, 14, 3, 3)
        features['slowk'] = float(stoch[0])
        features['slowd'] = float(stoch[1])

        features['cci'] = float(ta.cci(candles, 20))
        features['willr'] = float(ta.willr(candles, 14))
        features['roc'] = float(ta.roc(candles, 10))

        # Momentum
        if len(close) > 1:
            features['momentum'] = float((close[-1] / close[-2] - 1) * 100)
        else:
            features['momentum'] = 0

        # Lag features - compute RSI on shifted candle window
        if len(candles) > 15:
            features['rsi_lag_1'] = float(ta.rsi(candles[:-1], 14))
            features['rsi_lag_2'] = float(ta.rsi(candles[:-2], 14))
        else:
            features['rsi_lag_1'] = features['rsi']
            features['rsi_lag_2'] = features['rsi']
        features['rsi_diff_1'] = features['rsi'] - features['rsi_lag_1']

        # Volume stats
        vol_5 = volume[-5:]
        vol_10 = volume[-10:]
        vol_20 = volume[-20:]
        features['volume_max_5'] = float(np.max(vol_5)) if len(vol_5) > 0 else 0
        features['volume_min_5'] = float(np.min(vol_5)) if len(vol_5) > 0 else 0
        features['volume_max_10'] = float(np.max(vol_10)) if len(vol_10) > 0 else 0
        features['volume_min_10'] = float(np.min(vol_10)) if len(vol_10) > 0 else 0
        features['volume_max_20'] = float(np.max(vol_20)) if len(vol_20) > 0 else 0
        features['volume_min_20'] = float(np.min(vol_20)) if len(vol_20) > 0 else 0
        features['volume_median_20'] = float(np.median(vol_20)) if len(vol_20) > 0 else 0

        # Close stats
        close_5 = close[-5:]
        close_10 = close[-10:]
        close_20 = close[-20:]
        features['close_min_5'] = float(np.min(close_5)) if len(close_5) > 0 else 0
        features['close_max_5'] = float(np.max(close_5)) if len(close_5) > 0 else 0
        features['close_min_10'] = float(np.min(close_10)) if len(close_10) > 0 else 0
        features['close_max_10'] = float(np.max(close_10)) if len(close_10) > 0 else 0
        features['close_median_20'] = float(np.median(close_20)) if len(close_20) > 0 else 0
        features['close_min_20'] = float(np.min(close_20)) if len(close_20) > 0 else 0
        features['close_max_20'] = float(np.max(close_20)) if len(close_20) > 0 else 0

        # Price change
        if len(close) >= 2:
            features['price_change_1h'] = (close[-1] / close[-2] - 1) * 100
        else:
            features['price_change_1h'] = 0

        # Volatility
        features['volatility_20'] = float(np.std(close_20) / close[-1] * 100) if len(close_20) > 0 and close[-1] != 0 else 0

        # OBV
        if len(volume) >= 2 and len(close) >= 2:
            obv = 0.0
            for i in range(1, len(close)):
                if close[i] > close[i-1]:
                    obv += volume[i]
                elif close[i] < close[i-1]:
                    obv -= volume[i]
            features['obv'] = float(obv)
            vol_20_arr = volume[-20:]
            features['obv_sma'] = float(np.mean(vol_20_arr)) if len(vol_20_arr) > 0 else 0
        else:
            features['obv'] = 0
            features['obv_sma'] = 0

        # Market context (BTC)
        features['btc_ema_cross'] = float(self.btc_ema_cross)
        features['fear_greed'] = float(self.fear_greed_proxy)
        mode_map = {'BEAR': 0, 'LATERAL': 1, 'BULL': 2, 'VOLATILE_BEAR': 3, 'VOLATILE_BULL': 4, 'LATERAL_BULL': 5}
        features['market_mode'] = mode_map.get(self.detected_market_mode, 1)

        # Confidence score (ML proxy)
        features['confidence_score'] = float(self.ml_confidence_proxy())

        return features
