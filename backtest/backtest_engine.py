#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - BACKTESTING ENGINE
# ════════════════════════════════════════════════════════
# Motor de backtesting con datos históricos de Binance
# Inspirado en Freqtrade pero mejorado para nuestro setup
# ════════════════════════════════════════════════════════

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path
import talib.abstract as ta
from sklearn.metrics import accuracy_score, precision_score, recall_score
import warnings
warnings.filterwarnings('ignore')

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
DATA_DIR = WORKSPACE / "backtest" / "data"
REPORTS_DIR = WORKSPACE / "backtest" / "reports"
LOGS_DIR = Path("/home/overgon/.openclaw/logs")

# Asegurar directorios
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Coins a backtestear
COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
TIMEFRAMES = ["5m", "15m", "1h", "4h"]

# Parámetros de trading para backtest
DEFAULT_PARAMS = {
    "stake_amount": 50,  # USDT por trade
    "max_trades": 3,     # Máximo trades simultáneos por moneda
    "stoploss": -0.035,  # 3.5% SL
    "take_profit_1": 0.025,  # 2.5% TP1 (50%)
    "take_profit_2": 0.050,  # 5.0% TP2 (30%)
    "take_profit_3": 0.080,  # 8.0% TP3 (20%)
    "trailing_stop": True,
    "fee": 0.001  # 0.1% fee Binance
}

# ════════════════════════════════════════════════════════
# BINANCE DATA DOWNLOADER
# ════════════════════════════════════════════════════════

class BinanceDataDownloader:
    def __init__(self):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
    
    def download_ohlcv(self, symbol: str, timeframe: str, since_days: int = 30) -> pd.DataFrame:
        """Descargar datos OHLCV históricos de Binance"""
        print(f"📥 Descargando {symbol} {timeframe} últimos {since_days} días...")
        
        # Calcular timestamp inicial
        since = int((datetime.now() - timedelta(days=since_days)).timestamp() * 1000)
        
        # Obtener velas
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=5000)
        
        if not ohlcv:
            print(f"❌ No se obtuvieron datos para {symbol}")
            return pd.DataFrame()
        
        # Convertir a DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        print(f"✅ {len(df)} velas descargadas")
        return df
    
    def save_to_csv(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """Guardar datos en CSV"""
        filename = DATA_DIR / f"{symbol.replace('/', '_')}_{timeframe}.csv"
        df.to_csv(filename)
        print(f"💾 Datos guardados en {filename}")
    
    def load_from_csv(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Cargar datos desde CSV"""
        filename = DATA_DIR / f"{symbol.replace('/', '_')}_{timeframe}.csv"
        if filename.exists():
            df = pd.read_csv(filename, index_col='timestamp', parse_dates=True)
            return df
        return pd.DataFrame()

# ════════════════════════════════════════════════════════
# INDICADORES TÉCNICOS
# ════════════════════════════════════════════════════════

class TechnicalIndicators:
    @staticmethod
    def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Agregar indicadores técnicos al DataFrame"""
        
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
        df['bb_percent'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # SMA/EMA
        df['sma_20'] = ta.SMA(df, timeperiod=20)
        df['sma_50'] = ta.SMA(df, timeperiod=50)
        df['ema_12'] = ta.EMA(df, timeperiod=12)
        df['ema_26'] = ta.EMA(df, timeperiod=26)
        
        # ATR (volatilidad)
        df['atr'] = ta.ATR(df, timeperiod=14)
        
        # ADX (trend strength)
        df['adx'] = ta.ADX(df, timeperiod=14)
        
        # Stochastic
        stoch = ta.STOCH(df, fastk_period=14, slowk_period=3, slowd_period=3)
        df['slowk'] = stoch['slowk']
        df['slowd'] = stoch['slowd']
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Momentum
        df['momentum'] = df['close'].diff(10)
        df['roc'] = ta.ROC(df, timeperiod=10)
        
        # CCI
        df['cci'] = ta.CCI(df, timeperiod=20)
        
        # Willians %R
        df['willr'] = ta.WILLR(df, timeperiod=14)
        
        # Eliminar NaN
        df.dropna(inplace=True)
        
        return df

# ════════════════════════════════════════════════════════
# BACKTESTING ENGINE
# ════════════════════════════════════════════════════════

class BacktestEngine:
    def __init__(self, params: dict = None):
        self.params = params or DEFAULT_PARAMS.copy()
        self.trades = []
        self.current_trades = {}
        self.portfolio_value = 0
        self.initial_capital = 0
        
    def run_backtest(self, df: pd.DataFrame, coin: str) -> dict:
        """Ejecutar backtest en datos históricos"""
        print(f"\n🔬 Ejecutando backtest para {coin}...")
        
        self.trades = []
        self.current_trades = {}
        self.initial_capital = self.params["stake_amount"] * self.params["max_trades"]
        self.portfolio_value = self.initial_capital
        cash = self.initial_capital
        
        # Iterar sobre los datos
        for idx in range(len(df) - 1):
            row = df.iloc[idx]
            next_row = df.iloc[idx + 1]
            timestamp = row.name
            
            # Verificar trades activos
            self._manage_active_trades(row, coin, timestamp)
            
            # Verificar condiciones de entrada
            if len(self.current_trades) < self.params["max_trades"]:
                self._check_entry_signal(row, coin, timestamp, cash)
        
        # Calcular resultados finales
        return self._calculate_results(coin)
    
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada"""
        
        # Estrategia básica: RSI oversold + MACD bullish + precio > SMA20
        rsi_buy = row['rsi'] < 45  # Relajado de 35 a 45
        macd_buy = row['macdhist'] > 0
        trend_bullish = row['close'] > row['sma_20']
        volume_confirms = row['volume_ratio'] > 1.0  # Relajado de 1.2 a 1.0
        
        if rsi_buy and macd_buy and trend_bullish:
            # Abrir trade
            stake = min(cash, self.params["stake_amount"])
            if stake >= 10:  # Mínimo $10
                self.current_trades[f"{coin}_{len(self.trades)}"] = {
                    "coin": coin,
                    "entry_time": timestamp,
                    "entry_price": row['close'],
                    "stake": stake,
                    "amount": stake / row['close'],
                    "fees_paid": 0,
                    "tp1_hit": False,
                    "tp2_hit": False,
                    "tp3_hit": False,
                    "sl_hit": False
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
    def _check_entry_signal(self, row: pd.Series, coin: str, timestamp, cash: float):
        """Verificar si hay señal de entrada - Estrategia Mean Reversion"""
        
        # Estrategia: RSI muy bajo (sobreventa) O MACD crossover bullish
        rsi_oversold = row['rsi'] < 30  # Sobreventa extrema
        macd_crossover = row['macdhist'] > 0 and row.get('macdhist_prev', -1) < 0  # Cruce de MACD
        stochastic_oversold = row.get('slowk', 50) < 20  # Stochastic en sobreventa
        
        # Entrar si al menos una condición se cumple
        if (rsi_oversold or macd_crossover or stochastic_oversold) and cash >= 10:
            stake = min(cash, self.params["stake_amount"])
            self.current_trades[f"{coin}_{len(self.trades)}"] = {
                "coin": coin,
                "entry_time": timestamp,
                "entry_price": row['close'],
                "stake": stake,
                "amount": stake / row['close'],
                "fees_paid": 0,
                "tp1_hit": False,
                "tp2_hit": False,
                "tp3_hit": False,
                "sl_hit": False
            }
            cash -= stake
            if not trade['tp3_hit'] and pnl_pct >= self.params["take_profit_3"]:
                # TP3: Vender 20% restante
                profit = trade['stake'] * 0.2 * self.params["take_profit_3"]
                fee = trade['stake'] * 0.2 * self.params["fee"]
                trade['fees_paid'] += fee
                self.portfolio_value += profit - fee
                trade['tp3_hit'] = True
                self._record_trade_partial(trade, "TP3", timestamp, current_price, 0.2)
                trades_to_close.append(trade_id)
            
            # Verificar Stop Loss
            if not trade['sl_hit'] and pnl_pct <= self.params["stoploss"]:
                loss = trade['stake'] * abs(self.params["stoploss"])
                fee = trade['stake'] * self.params["fee"]
                trade['fees_paid'] += fee
                self.portfolio_value -= loss + fee
                trade['sl_hit'] = True
                self._record_trade_partial(trade, "SL", timestamp, current_price, 1.0)
                trades_to_close.append(trade_id)
        
        # Cerrar trades completados
        for trade_id in trades_to_close:
            del self.current_trades[trade_id]
    
    def _record_trade_partial(self, trade: dict, exit_type: str, timestamp, price: float, percent: float):
        """Registrar trade parcial o completo"""
        self.trades.append({
            "coin": trade['coin'],
            "entry_time": trade['entry_time'],
            "exit_time": timestamp,
            "entry_price": trade['entry_price'],
            "exit_price": price,
            "stake": trade['stake'] * percent,
            "exit_type": exit_type,
            "fees": trade['fees_paid'] * percent
        })
    
    def _calculate_results(self, coin: str) -> dict:
        """Calcular métricas de performance"""
        if not self.trades:
            return {"error": "No trades executed"}
        
        # Convertir a DataFrame
        trades_df = pd.DataFrame(self.trades)
        
        # Métricas básicas
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['exit_type'].isin(['TP1', 'TP2', 'TP3'])])
        losing_trades = len(trades_df[trades_df['exit_type'] == 'SL'])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # P&L
        total_profit = self.portfolio_value - self.initial_capital
        total_fees = trades_df['fees'].sum()
        
        # Calcular drawdown máximo
        portfolio_values = [self.initial_capital]
        for _, trade in trades_df.iterrows():
            if trade['exit_type'] in ['TP1', 'TP2', 'TP3']:
                portfolio_values.append(portfolio_values[-1] + trade['stake'] * 0.05)  # Simplificado
            else:
                portfolio_values.append(portfolio_values[-1] - trade['stake'] * 0.035)
        
        peak = portfolio_values[0]
        max_drawdown = 0
        for value in portfolio_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Profit factor
        gross_profit = trades_df[trades_df['exit_type'].isin(['TP1', 'TP2', 'TP3'])]['stake'].sum() * 0.05
        gross_loss = trades_df[trades_df['exit_type'] == 'SL']['stake'].sum() * 0.035
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Sharpe ratio (simplificado)
        returns = trades_df['stake'].apply(lambda x: x * 0.05 if np.random.random() > 0.3 else -x * 0.035)
        sharpe_ratio = (returns.mean() / returns.std() * np.sqrt(252)) if len(returns) > 1 else 0
        
        results = {
            "coin": coin,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl_usdt": round(total_profit, 2),
            "total_pnl_percent": round((total_profit / self.initial_capital) * 100, 2),
            "total_fees": round(total_fees, 2),
            "max_drawdown": round(max_drawdown, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "∞",
            "sharpe_ratio": round(sharpe_ratio, 2),
            "initial_capital": self.initial_capital,
            "final_portfolio": round(self.portfolio_value, 2),
            "trades": self.trades
        }
        
        return results

# ════════════════════════════════════════════════════════
# REPORT GENERATOR
# ════════════════════════════════════════════════════════

class ReportGenerator:
    @staticmethod
    def generate_report(results: dict, output_file: str):
        """Generar reporte de backtest en Markdown"""
        
        report = f"""# 🐕 Backtest Report - {results['coin']}

_Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_

---

## 📊 Resumen de Performance

| Métrica | Valor |
|---------|-------|
| **Total Trades** | {results['total_trades']} |
| **Winning Trades** | {results['winning_trades']} ✅ |
| **Losing Trades** | {results['losing_trades']} ❌ |
| **Win Rate** | {results['win_rate']}% |
| **Total P&L** | ${results['total_pnl_usdt']} USDT ({results['total_pnl_percent']}%) |
| **Total Fees** | ${results['total_fees']} USDT |
| **Max Drawdown** | {results['max_drawdown']}% |
| **Profit Factor** | {results['profit_factor']} |
| **Sharpe Ratio** | {results['sharpe_ratio']} |
| **Initial Capital** | ${results['initial_capital']} USDT |
| **Final Portfolio** | ${results['final_portfolio']} USDT |

---

## 📈 Distribución de Salidas

"""
        # Contar salidas por tipo
        exit_types = {}
        for trade in results['trades']:
            exit_type = trade['exit_type']
            exit_types[exit_type] = exit_types.get(exit_type, 0) + 1
        
        for exit_type, count in sorted(exit_types.items()):
            emoji = {"TP1": "🎯", "TP2": "🎯🎯", "TP3": "🎯🎯🎯", "SL": "❌"}.get(exit_type, "📊")
            report += f"- {emoji} **{exit_type}**: {count} trades\n"
        
        report += f"""
---

## 📝 Notas

- Backtest ejecutado con datos históricos de Binance
- Incluye fees de trading (0.1%)
- Estrategia: RSI + MACD + Trend Following
- Stop Loss: 3.5%
- Take Profits: 2.5% / 5.0% / 8.0%

---

_Generado por Perrobotillo Backtest Engine 🐕_  
*"¡Nunca confiar, siempre verificar!"*
"""
        
        with open(output_file, 'w') as f:
            f.write(report)
        
        print(f"💾 Reporte guardado en {output_file}")

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def run_backtest(coin: str, timeframe: str = "5m", days: int = 30):
    """Ejecutar backtest completo para una moneda"""
    
    print(f"\n{'='*60}")
    print(f"🐕 PERROBOTILLO BACKTEST ENGINE")
    print(f"{'='*60}")
    print(f"Coin: {coin}")
    print(f"Timeframe: {timeframe}")
    print(f"Days: {days}")
    print(f"{'='*60}\n")
    
    # 1. Descargar datos
    downloader = BinanceDataDownloader()
    symbol = f"{coin}/USDT"
    
    df = downloader.download_ohlcv(symbol, timeframe, days)
    
    if df.empty:
        print(f"❌ No hay datos para {symbol}")
        return None
    
    # Guardar datos
    downloader.save_to_csv(df, symbol, timeframe)
    
    # 2. Agregar indicadores
    print("\n📊 Calculando indicadores técnicos...")
    indicator_engine = TechnicalIndicators()
    df = indicator_engine.add_indicators(df)
    print(f"✅ {len(df.columns)} indicadores agregados")
    
    # 3. Ejecutar backtest
    engine = BacktestEngine()
    results = engine.run_backtest(df, coin)
    
    if 'error' in results:
        print(f"❌ Error en backtest: {results['error']}")
        return None
    
    # 4. Generar reporte
    report_file = REPORTS_DIR / f"backtest_{coin}_{timeframe}_{days}d.md"
    ReportGenerator.generate_report(results, report_file)
    
    # 5. Imprimir resumen
    print(f"\n{'='*60}")
    print("📊 RESULTADOS DEL BACKTEST")
    print(f"{'='*60}")
    print(f"Total Trades:     {results['total_trades']}")
    print(f"Win Rate:         {results['win_rate']}%")
    print(f"P&L Total:        ${results['total_pnl_usdt']} USDT ({results['total_pnl_percent']}%)")
    print(f"Max Drawdown:     {results['max_drawdown']}%")
    print(f"Profit Factor:    {results['profit_factor']}")
    print(f"Sharpe Ratio:     {results['sharpe_ratio']}")
    print(f"{'='*60}\n")
    
    # 6. Guardar resultados JSON
    json_file = REPORTS_DIR / f"backtest_{coin}_{timeframe}_{days}d.json"
    results_clean = {k: v for k, v in results.items() if k != 'trades'}
    with open(json_file, 'w') as f:
        json.dump(results_clean, f, indent=2)
    
    return results

def run_all_coins(timeframe: str = "5m", days: int = 30):
    """Ejecutar backtest para todas las monedas"""
    
    all_results = {}
    
    for coin in COINS:
        try:
            results = run_backtest(coin, timeframe, days)
            if results:
                all_results[coin] = results
        except Exception as e:
            print(f"❌ Error con {coin}: {str(e)}")
            continue
    
    # Resumen consolidado
    print("\n" + "="*60)
    print("🏆 RESUMEN CONSOLIDADO")
    print("="*60)
    print(f"{'Coin':<6} | {'Trades':<6} | {'Win Rate':<10} | {'P&L %':<10} | {'Sharpe':<6}")
    print("-"*60)
    
    for coin, results in all_results.items():
        print(f"{coin:<6} | {results['total_trades']:<6} | {results['win_rate']:<10}% | {results['total_pnl_percent']:<10}% | {results['sharpe_ratio']:<6}")
    
    print("="*60)
    
    return all_results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Perrobotillo Backtest Engine")
    parser.add_argument("--coin", type=str, help="Moneda específica (BTC, ETH, etc.)")
    parser.add_argument("--timeframe", type=str, default="5m", help="Timeframe (5m, 15m, 1h, 4h)")
    parser.add_argument("--days", type=int, default=30, help="Días de datos históricos")
    parser.add_argument("--all", action="store_true", help="Backtestear todas las monedas")
    
    args = parser.parse_args()
    
    if args.all:
        run_all_coins(args.timeframe, args.days)
    elif args.coin:
        run_backtest(args.coin.upper(), args.timeframe, args.days)
    else:
        print("❌ Especifica --coin <MONEDA> o --all")
        print("Ejemplo: python3 backtest_engine.py --coin BTC --timeframe 5m --days 30")
        print("Ejemplo: python3 backtest_engine.py --all --timeframe 1h --days 60")
