#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - FEATURE ENGINEERING ENGINE
# ════════════════════════════════════════════════════════
# Generador automático de 100+ features para ML
# Inspirado en Freqtrade FreqAI pero simplificado
# ════════════════════════════════════════════════════════

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import talib.abstract as ta
import json
import warnings
warnings.filterwarnings('ignore')

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
DATA_DIR = WORKSPACE / "backtest" / "data"
FEATURES_DIR = WORKSPACE / "ml" / "features"
LOGS_DIR = Path("/home/overgon/.openclaw/logs")

FEATURES_DIR.mkdir(parents=True, exist_ok=True)

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

# ════════════════════════════════════════════════════════
# FEATURE ENGINEERING ENGINE
# ════════════════════════════════════════════════════════

class FeatureEngineer:
    """
    Genera automáticamente 100+ features a partir de datos OHLCV básicos.
    Categorías:
    1. Lag Features (20 columnas)
    2. Rolling Statistics (30 columnas)
    3. Price Action Features (15 columnas)
    4. Time Features (5 columnas)
    5. Interaction Features (20 columnas)
    6. Volatility Features (10 columnas)
    7. Trend Strength Features (10 columnas)
    8. Volume Profile Features (10 columnas)
    
    Total: ~120 features automáticos
    """
    
    def __init__(self):
        self.feature_names = []
        self.feature_metadata = {}
    
    def generate_all_features(self, df: pd.DataFrame, coin: str = "BTC") -> pd.DataFrame:
        """Generar todos los features automáticamente"""
        
        print(f"\n🔧 Generando features para {coin}...")
        print(f"  Datos iniciales: {len(df.columns)} columnas")
        
        # Asegurar que tenemos OHLCV
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Falta columna requerida: {col}")
        
        # 1. Indicadores técnicos base
        df = self._add_base_indicators(df)
        
        # 2. Lag Features
        df = self._add_lag_features(df)
        
        # 3. Rolling Statistics
        df = self._add_rolling_features(df)
        
        # 4. Price Action Features
        df = self._add_price_action_features(df)
        
        # 5. Time Features
        df = self._add_time_features(df)
        
        # 6. Interaction Features
        df = self._add_interaction_features(df)
        
        # 7. Volatility Features
        df = self._add_volatility_features(df)
        
        # 8. Trend Strength Features
        df = self._add_trend_features(df)
        
        # 9. Volume Profile Features
        df = self._add_volume_features(df)
        
        # 10. Correlation Features (si hay datos de BTC)
        if coin != "BTC":
            df = self._add_correlation_features(df, coin)
        
        # 11. Market Context Features (BTC-based) — required by Fase 5 ML models
        df = self._add_btc_context_features(df, coin)
        
        # Limpiar NaN
        df.dropna(inplace=True)
        
        print(f"  Datos finales: {len(df.columns)} columnas")
        print(f"  Features generados: {len(df.columns) - 5} automáticos")
        
        return df
    
    def _add_base_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar indicadores técnicos base"""
        print("  ├─ Agregando indicadores base...")
        
        # RSI
        df['rsi'] = ta.RSI(df, timeperiod=14)
        
        # MACD
        macd = ta.MACD(df, fastperiod=12, slowperiod=26, signalperiod=9)
        df['macd'] = macd['macd']
        df['macdsignal'] = macd['macdsignal']
        df['macdhist'] = macd['macdhist']
        
        # Bollinger Bands
        bollinger = ta.BBANDS(df, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        df['bb_upper'] = bollinger['upperband']
        df['bb_middle'] = bollinger['middleband']
        df['bb_lower'] = bollinger['lowerband']
        df['bb_percent'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # SMA/EMA
        df['sma_20'] = ta.SMA(df, timeperiod=20)
        df['sma_50'] = ta.SMA(df, timeperiod=50)
        df['ema_12'] = ta.EMA(df, timeperiod=12)
        df['ema_26'] = ta.EMA(df, timeperiod=26)
        
        # ATR
        df['atr'] = ta.ATR(df, timeperiod=14)
        df['atr_percent'] = (df['atr'] / df['close']) * 100
        
        # ADX
        df['adx'] = ta.ADX(df, timeperiod=14)
        
        # Stochastic
        stoch = ta.STOCH(df, fastk_period=14, slowk_period=3, slowd_period=3)
        df['slowk'] = stoch['slowk']
        df['slowd'] = stoch['slowd']
        
        # CCI
        df['cci'] = ta.CCI(df, timeperiod=20)
        
        # Williams %R
        df['willr'] = ta.WILLR(df, timeperiod=14)
        
        # Momentum
        df['momentum'] = df['close'].diff(10)
        df['roc'] = ta.ROC(df, timeperiod=10)
        
        return df
    
    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar Lag Features (valores pasados)"""
        print("  ├─ Agregando lag features...")
        
        cols_to_lag = ['rsi', 'macd', 'macdhist', 'close', 'volume', 'atr_percent']
        lags = [1, 2, 3, 5, 10]
        
        for col in cols_to_lag:
            if col not in df.columns:
                continue
            for lag in lags:
                df[f'{col}_lag_{lag}'] = df[col].shift(lag)
                
                # Diferencia con lag
                df[f'{col}_diff_{lag}'] = df[col] - df[col].shift(lag)
        
        return df
    
    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar Rolling Statistics"""
        print("  ├─ Agregando rolling statistics...")
        
        cols_to_roll = ['rsi', 'close', 'volume', 'macdhist', 'roc']
        windows = [5, 10, 20]
        
        for col in cols_to_roll:
            if col not in df.columns:
                continue
            for window in windows:
                # Media móvil
                df[f'{col}_sma_{window}'] = df[col].rolling(window).mean()
                
                # Desviación estándar
                df[f'{col}_std_{window}'] = df[col].rolling(window).std()
                
                # Mínimo y Máximo
                df[f'{col}_min_{window}'] = df[col].rolling(window).min()
                df[f'{col}_max_{window}'] = df[col].rolling(window).max()
                
                # Mediana
                df[f'{col}_median_{window}'] = df[col].rolling(window).median()
        
        return df
    
    def _add_price_action_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar Price Action Features"""
        print("  ├─ Agregando price action features...")
        
        # Cambios de precio en diferentes períodos
        df['price_change_1h'] = df['close'].pct_change(12) * 100  # 12 velas de 5min = 1h
        df['price_change_4h'] = df['close'].pct_change(48) * 100
        df['price_change_1d'] = df['close'].pct_change(288) * 100
        
        # High-Low Range
        df['high_low_range'] = (df['high'] - df['low']) / df['close'] * 100
        df['body_size'] = abs(df['close'] - df['open']) / df['close'] * 100
        
        # Upper/Lower shadows
        df['upper_shadow'] = (df['high'] - df[['open', 'close']].max(axis=1)) / df['close'] * 100
        df['lower_shadow'] = (df[['open', 'close']].min(axis=1) - df['low']) / df['close'] * 100
        
        # Precio relativo a SMA
        df['close_to_sma20'] = (df['close'] - df['sma_20']) / df['sma_20'] * 100
        df['close_to_sma50'] = (df['close'] - df['sma_50']) / df['sma_50'] * 100
        
        # Golden/Death cross indicator
        df['golden_cross'] = (df['sma_20'] > df['sma_50']).astype(int)
        
        # Higher Highs / Lower Lows
        df['higher_high'] = (df['high'] > df['high'].shift(1)).astype(int)
        df['lower_low'] = (df['low'] < df['low'].shift(1)).astype(int)
        
        return df
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar Time Features"""
        print("  ├─ Agregando time features...")
        
        df['hour'] = df.index.hour if hasattr(df.index, 'hour') else 12
        df['day_of_week'] = df.index.dayofweek if hasattr(df.index, 'dayofweek') else 0
        df['day_of_month'] = df.index.day if hasattr(df.index, 'day') else 1
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['is_asian_session'] = df['hour'].isin([0, 1, 2, 3, 4, 5, 6, 7]).astype(int)
        df['is_european_session'] = df['hour'].isin([8, 9, 10, 11, 12, 13, 14, 15]).astype(int)
        df['is_us_session'] = df['hour'].isin([14, 15, 16, 17, 18, 19, 20, 21, 22]).astype(int)
        
        return df
    
    def _add_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar Interaction Features (combinaciones)"""
        print("  ├─ Agregando interaction features...")
        
        # RSI x Volumen
        if 'rsi' in df.columns and 'volume' in df.columns:
            df['rsi_x_volume'] = df['rsi'] * df['volume']
            df['rsi_x_volume_ratio'] = df['rsi'] * (df['volume'] / df['volume'].rolling(20).mean())
        
        # MACD x RSI
        if 'macd' in df.columns and 'rsi' in df.columns:
            df['macd_x_rsi'] = df['macd'] * df['rsi']
            df['macdhist_x_rsi'] = df['macdhist'] * df['rsi']
        
        # Precio x Volumen
        if 'close' in df.columns and 'volume' in df.columns:
            df['price_x_volume'] = df['close'] * df['volume']
        
        # Bollinger x RSI
        if 'bb_percent' in df.columns and 'rsi' in df.columns:
            df['bb_x_rsi'] = df['bb_percent'] * df['rsi']
        
        # ATR x ADX (volatilidad direccional)
        if 'atr_percent' in df.columns and 'adx' in df.columns:
            df['atr_x_adx'] = df['atr_percent'] * df['adx']
        
        # Momentum x Volumen
        if 'momentum' in df.columns and 'volume' in df.columns:
            df['momentum_x_volume'] = df['momentum'] * df['volume']
        
        # Ratio features
        if 'ema_12' in df.columns and 'ema_26' in df.columns:
            df['ema_ratio'] = df['ema_12'] / df['ema_26']
        
        if 'slowk' in df.columns and 'slowd' in df.columns:
            df['stoch_diff'] = df['slowk'] - df['slowd']
        
        return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar Volatility Features"""
        print("  ├─ Agregando volatility features...")
        
        # Returns
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Volatilidad en diferentes ventanas
        df['volatility_5'] = df['returns'].rolling(5).std()
        df['volatility_10'] = df['returns'].rolling(10).std()
        df['volatility_20'] = df['returns'].rolling(20).std()
        
        # Volatilidad normalizada
        df['volatility_ratio'] = df['volatility_5'] / df['volatility_20']
        
        # Parkinson volatility
        df['parkinson'] = np.sqrt(1/(4*np.log(2)) * np.log(df['high']/df['low']).rolling(20).mean()) * 100
        
        return df
    
    def _add_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar Trend Strength Features"""
        print("  ├─ Agregando trend features...")
        
        # Trend strength
        df['trend_strength'] = abs(df['close'] - df['sma_20']) / df['sma_20'] * 100
        
        # ADX trend
        df['adx_trend'] = df['adx'] / 100  # Normalizado
        
        # Directional movement
        df['plus_dm'] = ta.PLUS_DM(df, timeperiod=14)
        df['minus_dm'] = ta.MINUS_DM(df, timeperiod=14)
        df['dm_ratio'] = df['plus_dm'] / (df['minus_dm'] + 1e-10)
        
        # EMA slope
        df['ema_slope'] = df['ema_12'].diff(5) / df['ema_12'] * 100
        
        # Price above/below EMAs
        df['above_ema12'] = (df['close'] > df['ema_12']).astype(int)
        df['above_ema26'] = (df['close'] > df['ema_26']).astype(int)
        
        return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agregar Volume Profile Features"""
        print("  ├─ Agregando volume features...")
        
        # Volume ratio
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        
        # Volume trend
        df['volume_trend'] = df['volume'].diff(5) / df['volume'].rolling(5).mean()
        
        # OBV (On Balance Volume) - simplificado
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).cumsum()
        df['obv_sma'] = df['obv'].rolling(20).mean()
        
        # Volume volatility
        df['volume_std'] = df['volume'].rolling(20).std() / df['volume'].rolling(20).mean()
        
        # Accumulation/Distribution
        df['adl'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'] + 1e-10) * df['volume']
        
        return df
    
    def _add_correlation_features(self, df: pd.DataFrame, coin: str) -> pd.DataFrame:
        """Agregar Correlation Features vs BTC"""
        print(f"  ├─ Agregando correlation features vs BTC...")
        
        # Intentar cargar datos de BTC
        btc_file = DATA_DIR / "BTC_USDT_5m.csv"
        if btc_file.exists():
            btc_df = pd.read_csv(btc_file, index_col='timestamp', parse_dates=True)
            btc_df['btc_returns'] = btc_df['close'].pct_change()
            
            # Correlación de returns
            df['corr_btc_returns'] = df['returns'].rolling(20).corr(btc_df['btc_returns'])
            
            # Beta vs BTC
            covariance = df['returns'].rolling(20).cov(btc_df['btc_returns'])
            variance = btc_df['btc_returns'].rolling(20).var()
            df['beta_vs_btc'] = covariance / (variance + 1e-10)
            
            # Relative strength vs BTC
            df['relative_strength_btc'] = df['close'] / btc_df['close']
            df['rs_btc_sma'] = df['relative_strength_btc'].rolling(10).mean()
        else:
            print("    ⚠️ No se encontraron datos de BTC para correlación")
        
        return df
    
    def _add_btc_context_features(self, df: pd.DataFrame, coin: str = "BTC") -> pd.DataFrame:
        """
        Agregar Market Context Features basadas en BTC.

        Features: btc_ema_cross, fear_greed, market_mode, confidence_score
        Requeridas por los modelos ML Fase 5 de Perrobotillo.

        Lógica idéntica a PerrobotilloStrategy ml_confidence_proxy / fear_greed_proxy /
        detected_market_mode (Fase 4 Optuna hyperparameters).
        """
        print("  ├─ Agregando market context features (BTC)...")

        # --- Load BTC data (for BTC coin itself, use coin's data) ---
        if coin == "BTC":
            btc_df = df.copy()
        else:
            btc_file = DATA_DIR / "BTC_USDT_5m.csv"
            if not btc_file.exists():
                print("    ⚠️ No BTC data, filling market context defaults")
                df['btc_ema_cross'] = 0.0
                df['fear_greed'] = 50.0
                df['market_mode'] = 1  # LATERAL
                df['confidence_score'] = 50.0
                return df
            btc_df = pd.read_csv(btc_file, index_col='timestamp', parse_dates=True)

        # --- Resample BTC 5m → 1h for market context ---
        btc_1h = btc_df.resample('1h').agg({'open': 'first', 'high': 'max',
                                             'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()

        # --- Compute BTC EMAs and RSI on 1h, map back to 5m index ---
        btc_close_1h = btc_1h['close']
        btc_ema20_1h = btc_close_1h.ewm(span=20, adjust=False).mean()
        btc_ema50_1h = btc_close_1h.ewm(span=50, adjust=False).mean()
        btc_rsi_1h = ta.RSI(btc_1h, timeperiod=14)

        # Forward-fill 1h values to 5m index
        btc_ema20_5m = btc_ema20_1h.reindex(df.index, method='ffill')
        btc_ema50_5m = btc_ema50_1h.reindex(df.index, method='ffill')
        btc_rsi_5m = btc_rsi_1h.reindex(df.index, method='ffill')
        btc_price_5m = btc_close_1h.reindex(df.index, method='ffill')

        # --- 1. btc_ema_cross (EMA20 - EMA50) ---
        df['btc_ema_cross'] = (btc_ema20_5m - btc_ema50_5m).fillna(0).reset_index(drop=True)
        df['btc_ema_cross'].index = df.index

        # --- 2. fear_greed_proxy (0-100) ---
        fg = pd.Series(50.0, index=df.index)
        bullish = (btc_price_5m > btc_ema20_5m) & (btc_ema20_5m > btc_ema50_5m)
        bearish = (btc_price_5m < btc_ema20_5m) & (btc_ema20_5m < btc_ema50_5m)
        fg[bullish] += 20
        fg[bearish] -= 20
        fg[btc_rsi_5m > 70] += 10
        fg[btc_rsi_5m < 30] -= 10
        cross_5m = btc_ema20_5m - btc_ema50_5m
        fg[cross_5m > 0] += 5
        fg[cross_5m <= 0] -= 5
        df['fear_greed'] = fg.clip(0, 100).reset_index(drop=True)
        df['fear_greed'].index = df.index

        # --- 3. market_mode (0-5) ---
        mode = pd.Series(1, index=df.index, dtype=int)  # 1 = LATERAL default
        mode[btc_rsi_5m > 70] = 4       # VOLATILE_BULL
        mode[btc_rsi_5m < 30] = 3       # VOLATILE_BEAR
        mode[(fg < 40) & (btc_price_5m < btc_ema20_5m)] = 0  # BEAR
        mode[(fg > 60) & (btc_price_5m > btc_ema20_5m)] = 2  # BULL
        mode[(btc_price_5m > btc_ema20_5m) & (fg >= 40) & (fg <= 60)] = 5  # LATERAL_BULL
        df['market_mode'] = mode.reset_index(drop=True)
        df['market_mode'].index = df.index

        # --- 4. confidence_score (ML proxy, 0-100) ---
        # Uses Fase 4 Optuna hyperparameters: ema_fast=12, ema_slow=140,
        # rsi_overbought=75, rsi_oversold=30, min_adx=20
        ema_fast = df.get('ema_12', pd.Series(0, index=df.index))
        ema_slow = df['close'].ewm(span=140, adjust=False).mean()
        rsi_val = df.get('rsi', pd.Series(50, index=df.index))
        vol_ratio = df.get('volume_ratio', pd.Series(1.0, index=df.index))
        adx_val = df.get('adx', pd.Series(0, index=df.index))
        btc_bullish = (btc_price_5m > btc_ema20_5m).reset_index(drop=True)
        btc_bullish.index = df.index

        score = pd.Series(50.0, index=df.index)
        score[ema_fast > ema_slow] += 15
        score[ema_fast <= ema_slow] -= 15
        score[(rsi_val > 30) & (rsi_val < 75)] += 10
        score[rsi_val > 75] -= 20
        score[rsi_val < 30] -= 10
        score[vol_ratio >= 1.0] += 5
        score[vol_ratio < 1.0] -= 5
        score[adx_val > 20] += 8
        score[adx_val <= 20] -= 3
        score[btc_bullish] += 7
        score[~btc_bullish] -= 10
        score[df['fear_greed'] > 60] += 5
        score[df['fear_greed'] < 40] -= 10
        df['confidence_score'] = score.clip(0, 100).reset_index(drop=True)
        df['confidence_score'].index = df.index

        return df

    def get_feature_importance_summary(self, df: pd.DataFrame) -> dict:
        """Resumen de features generados"""
        
        summary = {
            "total_features": len(df.columns),
            "categories": {
                "lag_features": len([c for c in df.columns if '_lag_' in c]),
                "rolling_features": len([c for c in df.columns if '_sma_' in c or '_std_' in c or '_min_' in c or '_max_' in c]),
                "price_action": len([c for c in df.columns if 'price_' in c or 'shadow' in c or 'body' in c or 'range' in c]),
                "time_features": len([c for c in df.columns if 'hour' in c or 'day_' in c or 'session' in c or 'weekend' in c]),
                "interaction": len([c for c in df.columns if '_x_' in c or '_ratio' in c or 'ratio_' in c]),
                "volatility": len([c for c in df.columns if 'volatility' in c or 'returns' in c or 'parkinson' in c]),
                "trend": len([c for c in df.columns if 'trend' in c or 'adx' in c or 'slope' in c or 'above_' in c]),
                "volume": len([c for c in df.columns if 'volume' in c or 'obv' in c or 'adl' in c])
            }
        }
        
        return summary


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def generate_features_for_coin(coin: str, timeframe: str = "5m", days: int = 30):
    """Generar features para una moneda específica"""
    
    print(f"\n{'='*60}")
    print(f"🔧 FEATURE ENGINEERING - {coin}")
    print(f"{'='*60}")
    
    # Cargar datos
    data_file = DATA_DIR / f"{coin}_USDT_{timeframe}.csv"
    
    if not data_file.exists():
        print(f"❌ No se encontraron datos para {coin}. Ejecuta backtest primero.")
        return None
    
    df = pd.read_csv(data_file, index_col='timestamp', parse_dates=True)
    print(f"📊 Datos cargados: {len(df)} velas")
    
    # Generar features
    engineer = FeatureEngineer()
    df_features = engineer.generate_all_features(df, coin)
    
    # Resumen
    summary = engineer.get_feature_importance_summary(df_features)
    
    print(f"\n📊 RESUMEN DE FEATURES:")
    print(f"  Total columnas: {summary['total_features']}")
    print(f"  Categorías:")
    for cat, count in summary['categories'].items():
        print(f"    • {cat}: {count}")
    
    # Guardar features
    output_file = FEATURES_DIR / f"features_{coin}_{timeframe}_{days}d.csv"
    df_features.to_csv(output_file)
    print(f"\n💾 Features guardados en: {output_file}")
    
    # Guardar metadata
    metadata_file = FEATURES_DIR / f"metadata_{coin}.json"
    with open(metadata_file, 'w') as f:
        json.dump({
            "coin": coin,
            "timeframe": timeframe,
            "days": days,
            "total_features": summary['total_features'],
            "categories": summary['categories'],
            "generated_at": datetime.now().isoformat(),
            "columns": list(df_features.columns)
        }, f, indent=2)
    
    print(f"💾 Metadata guardada en: {metadata_file}")
    
    return df_features

def generate_all_features(timeframe: str = "5m", days: int = 30):
    """Generar features para todas las monedas"""
    
    print(f"\n{'='*60}")
    print("🔧 FEATURE ENGINEERING - TODAS LAS MONEDAS")
    print(f"{'='*60}\n")
    
    all_summaries = {}
    
    for coin in COINS:
        try:
            df = generate_features_for_coin(coin, timeframe, days)
            if df is not None:
                all_summaries[coin] = {
                    "total_features": len(df.columns),
                    "rows": len(df)
                }
        except Exception as e:
            print(f"❌ Error con {coin}: {str(e)}")
            continue
    
    # Resumen final
    print(f"\n{'='*60}")
    print("🏆 RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"{'Coin':<6} | {'Features':<10} | {'Rows':<10}")
    print("-"*60)
    
    for coin, summary in all_summaries.items():
        print(f"{coin:<6} | {summary['total_features']:<10} | {summary['rows']:<10}")
    
    print(f"{'='*60}\n")
    
    return all_summaries

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        generate_all_features("5m", days)
    elif len(sys.argv) > 1:
        coin = sys.argv[1].upper()
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        generate_features_for_coin(coin, "5m", days)
    else:
        print("Uso: python3 feature_engine.py [--all|<COIN>] [days]")
        print("Ejemplo: python3 feature_engine.py BTC 30")
        print("Ejemplo: python3 feature_engine.py --all 60")
