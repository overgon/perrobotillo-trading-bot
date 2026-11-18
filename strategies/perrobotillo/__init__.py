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
  - TP2 (35%): segundo take profit
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
from pathlib import Path
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

# ============================================================================
# CONFIG DE PRODUCCIÓN (fuente autoritativa)
# ============================================================================
# Lee crypto-bots/per-coin-config.env y crypto-bots/market-mode.conf. Si no
# existen, se usan los COIN_OVERRIDES/MODE_PARAMS de arriba.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _parse_env_file(path: Path) -> dict:
    values = {}
    try:
        text = path.read_text()
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _load_production_config() -> tuple:
    per_coin_raw = _parse_env_file(_PROJECT_ROOT / 'crypto-bots' / 'per-coin-config.env')
    market_raw = _parse_env_file(_PROJECT_ROOT / 'crypto-bots' / 'market-mode.conf')

    coin_keys = {'tp1': 'TP1', 'tp2': 'TP2', 'tp3': 'TP3',
                 'sl': 'SL', 'pos': 'POSITION_SIZE', 'ml_min': 'ML_MIN_CONFIDENCE'}
    prod_coin = {}
    for coin in ('BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX', 'ZEC'):
        entry = {}
        for cfg_key, env_key in coin_keys.items():
            raw = per_coin_raw.get(f'{coin}_{env_key}')
            if raw is None:
                continue
            try:
                entry[cfg_key] = float(raw)
            except ValueError:
                continue
        if entry:
            prod_coin[coin] = entry

    prod_global = {}
    for cfg_key, env_key in (('tp1', 'TP1'), ('tp2', 'TP2'), ('tp3', 'TP3'),
                             ('sl', 'SL'), ('pos', 'POSITION_SIZE')):
        raw = market_raw.get(env_key)
        if raw is None:
            continue
        try:
            prod_global[cfg_key] = float(raw)
        except ValueError:
            continue
    prod_global['trailing'] = market_raw.get('TRAILING_STOP', '').lower() in ('true', '1', 'yes')
    return prod_coin, prod_global


_PROD_COIN, _PROD_GLOBAL = _load_production_config()

# ============================================================================
# MODELO ML REAL (research lab)
# ============================================================================
# Los modelos se entrenan en strategies/perrobotillo/ml_data/model_{COIN}/.
# Se cachean por moneda; si faltan o fallan, se cae al proxy técnico.
_ML_MODEL_CACHE = {}


def _load_ml_model(coin: str):
    if coin in _ML_MODEL_CACHE:
        return _ML_MODEL_CACHE[coin]
    model_dir = _PROJECT_ROOT / 'strategies' / 'perrobotillo' / 'ml_data' / f'model_{coin}'
    model_path = model_dir / 'model.pkl'
    scaler_path = model_dir / 'scaler.pkl'
    if not model_path.exists():
        _ML_MODEL_CACHE[coin] = None
        return None
    try:
        import joblib
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path) if scaler_path.exists() else None
        _ML_MODEL_CACHE[coin] = (model, scaler)
    except Exception:  # noqa: BLE001
        _ML_MODEL_CACHE[coin] = None
    return _ML_MODEL_CACHE[coin]


# TP allocation percentages (35% / 35% / 30% = 100%)
TP1_PCT = 0.35
TP2_PCT = 0.35
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
        """
        Config efectiva por moneda. Jerarquía:
          1. MODE_PARAMS según el modo detectado
          2. COIN_OVERRIDES (hardcodeado, respaldo)
          3. market-mode.conf (global de producción)
          4. per-coin-config.env (por moneda, gana sobre el global)
          5. self.hp SOLO si JESSE_HP_OVERRIDE=1 (Optuna/investigación)
        """
        coin = self.coin
        mode = self.detected_market_mode
        cfg = dict(MODE_PARAMS.get(mode, MODE_PARAMS['LATERAL']))
        cfg.update(COIN_OVERRIDES.get(coin, {}))
        cfg.update(_PROD_GLOBAL)
        cfg.update(_PROD_COIN.get(coin, {}))

        if os.environ.get('JESSE_HP_OVERRIDE') == '1':
            hp = getattr(self, 'hp', None) or {}
            for cfg_key, hp_key in (('tp1', 'tp1_percent'), ('tp2', 'tp2_percent'),
                                    ('tp3', 'tp3_percent'), ('sl', 'stop_loss_percent'),
                                    ('pos', 'position_size_percent'),
                                    ('ml_min', 'ml_min_confidence')):
                if hp_key in hp:
                    cfg[cfg_key] = hp[hp_key]
        return cfg

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

    def ml_model_confidence(self) -> float:
        """
        Confianza 0-100 del modelo ML real (model_{COIN}).
        Si no hay modelo o el feature vector no coincide, cae al proxy.
        """
        loaded = _load_ml_model(self.coin)
        if loaded is None:
            return self.ml_confidence_proxy()
        model, scaler = loaded
        try:
            features = self.get_ml_features()
            names = sorted(features.keys())
            X = np.array([[float(features[n]) for n in names]], dtype=float)
            if scaler is not None:
                X = scaler.transform(X)
            proba = np.asarray(model.predict_proba(X))[0]
            classes = list(getattr(model, 'classes_', [0, 1]))
            idx = classes.index(1) if 1 in classes else len(proba) - 1
            return float(np.clip(proba[idx] * 100.0, 0.0, 100.0))
        except Exception:  # noqa: BLE001
            return self.ml_confidence_proxy()

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
        """ML validator: modelo real con fallback al proxy técnico."""
        score = self.ml_model_confidence()
        ml_min = self.per_coin_config['ml_min']
        return score >= ml_min

    def should_long(self) -> bool:
        """Entry logic mirroring Perrobotillo's execute_long -> ML validator approval."""
        coin = self.coin

        if not self.is_coin_enabled(coin):
            return False

        # No piramidar: una sola posición abierta por símbolo
        if self.position.is_long:
            return False

        # ML validator (modelo real / proxy)
        score = self.ml_model_confidence()
        ml_min = self.per_coin_config['ml_min']

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
        """Cancelar la entrada pendiente si el setup deja de ser válido."""
        if not getattr(self, 'entry_orders', None):
            return False
        return self.ml_model_confidence() < self.per_coin_config['ml_min']

    def is_coin_enabled(self, coin: str) -> bool:
        """Check per-coin enabled status."""
        if coin == 'BTC' and not ENABLE_BTC:
            return False
        return True

    def go_long(self):
        """
        Entry: market order at current price.
        Sets TP1 (35%), TP2 (35%), TP3 (30%), and SL.
        For spot trading, TPs and SL go in on_open_position(), not go_long().
        """
        entry_price = self.price
        balance = self.balance
        position_percent = self.per_coin_config['pos']

        # Calculate order value and quantity
        order_value = balance * (position_percent / 100)
        qty = utils.size_to_qty(order_value, entry_price, fee_rate=self.fee_rate)

        # Entry (spot trading: only buy here)
        self.buy = qty, entry_price

    def on_open_position(self, order):
        """Set TP/SL after position is opened (spot trading requirement)."""
        entry_price = self.average_entry_price
        qty = self.position.qty

        cfg = self.per_coin_config

        # TP levels (config de producción / JESSE_HP_OVERRIDE)
        tp1_price = entry_price * (1 + cfg['tp1'] / 100)
        tp2_price = entry_price * (1 + cfg['tp2'] / 100)
        tp3_price = entry_price * (1 + cfg['tp3'] / 100)

        # Stop loss
        sl_price = entry_price * (1 - cfg['sl'] / 100)

        # Partial take profits: 35% / 35% / 30%
        qty_tp1 = qty * TP1_PCT
        qty_tp2 = qty * TP2_PCT
        qty_tp3 = qty * TP3_PCT

        self.take_profit = [
            (qty_tp1, tp1_price),
            (qty_tp2, tp2_price),
            (qty_tp3, tp3_price),
        ]
        self.stop_loss = qty, sl_price

        # Seguimiento para stop a breakeven tras TP1
        self._initial_qty = qty
        self._entry_price = entry_price
        self._current_sl_price = sl_price
        self._tp1_filled = False

    def on_close_position(self, order, closed_trade):
        """En modo gather el label es la dirección futura; no etiquetamos por trade."""
        pass

    def go_short(self):
        pass

    def update_position(self):
        """Stop a breakeven tras TP1 + trailing stop (ATR) si está habilitado."""
        if not self.position.is_long:
            return

        cfg = self.per_coin_config

        # 1) Tras el primer take profit, mover el stop a breakeven (entry + fee)
        if not getattr(self, '_tp1_filled', False) and getattr(self, '_initial_qty', 0) > 0:
            if self.position.qty <= self._initial_qty * (1 - TP1_PCT) + 1e-6:
                self._tp1_filled = True
                be_price = self._entry_price * (1 + self.fee_rate)
                # Solo re-submetemos el SL si queda por debajo del precio actual
                # (STOP). Si el precio ya está por debajo del SL original, deja
                # que el STOP original dispare: re-submetir como LIMIT solaparía
                # con los TP y Jesse lo rechaza con InsufficientBalance.
                if be_price < self.price and self.price > self._current_sl_price:
                    self._current_sl_price = be_price
                    self.stop_loss = self.position.qty, be_price
                    return

        # 2) Trailing stop (opcional): nunca bajar el stop actual
        if cfg.get('trailing', False):
            current_atr = self.atr
            current_price = self.price
            trailing_sl = current_price - (current_atr * 2)
            if trailing_sl > self._current_sl_price:
                self._current_sl_price = trailing_sl
                self.stop_loss = self.position.qty, trailing_sl

    def before(self):
        """Called before each candle. Record ML features in gather mode.

        Las features se registran en la vela t y la etiqueta es la dirección de
        la vela t+1 (label futura): el punto abierto en t se etiqueta en el
        siguiente before() con close[t] > close[t-1]. Así el modelo predice y
        no memoriza el cierre actual (sin fuga de `price_change_1h`).
        """
        if self.ml_mode == "gather":
            pending = getattr(self, '_pending_ml_point', None)
            if pending is not None and len(self.candles) >= 2:
                prev_close = float(self.candles[-2][2])
                cur_close = float(self.candles[-1][2])
                pending['label'] = {'name': 'price_direction', 'value': cur_close > prev_close}
                self._ml_data_points.append(pending)
                self._pending_ml_point = None

            self.record_features(self.get_ml_features())
            self._pending_ml_point = self._current_ml_point
            self._current_ml_point = None

    def after(self):
        """Sin label contemporáneo: la etiqueta es futura (ver before())."""
        pass

    def hyperparameters(self):
        """
        Hyperparameters para Optuna/investigación.

        Nota: los TP/SL/posición/ml_min de producción mandan a menos que
        JESSE_HP_OVERRIDE=1. Los de indicadores (ema/rsi/adx) sí se usan.
        """
        return [
            {'name': 'tp1_percent', 'type': float, 'min': 1.0, 'max': 10.0, 'default': 3.0},
            {'name': 'tp2_percent', 'type': float, 'min': 2.0, 'max': 15.0, 'default': 6.0},
            {'name': 'tp3_percent', 'type': float, 'min': 3.0, 'max': 20.0, 'default': 9.0},
            {'name': 'stop_loss_percent', 'type': float, 'min': 1.0, 'max': 10.0, 'default': 3.5},
            {'name': 'position_size_percent', 'type': float, 'min': 5.0, 'max': 30.0, 'default': 10.0},
            {'name': 'ml_min_confidence', 'type': float, 'min': 40.0, 'max': 90.0, 'default': 45.0},
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

        return features
