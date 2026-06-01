#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - TRAILING STOP DINÁMICO CON ATR
# ════════════════════════════════════════════════════════
# Calcula trailing stop óptimo basado en Average True Range
# Se integra con crypto-trade-moneda-v3-slots.sh
# ════════════════════════════════════════════════════════

import ccxt
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
from typing import Dict
import sys
import logging

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
SECRETS = Path("/home/overgon/.openclaw/secrets")
LOGS_DIR = WORKSPACE / "logs"
CACHE_DIR = WORKSPACE / "cache"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'trailing-stop-atr.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN DE TRAILING STOP
# ════════════════════════════════════════════════════════

# Multiplicadores de ATR (ajustables)
ATR_MULTIPLIER_LOW_VOL = 2.0   # Baja volatilidad → stop más tight
ATR_MULTIPLIER_HIGH_VOL = 3.5  # Alta volatilidad → stop más wide
ATR_PERIOD = 14                # Período estándar para ATR
VOLATILITY_THRESHOLD = 0.03    # 3% para considerar "alta volatilidad"

# Mínimos y máximos absolutos
MIN_TRAILING_PERCENT = 2.0     # Mínimo 2%
MAX_TRAILING_PERCENT = 15.0    # Máximo 15%

# ════════════════════════════════════════════════════════
# ATR TRAILING STOP CALCULATOR
# ════════════════════════════════════════════════════════

class ATRTrailingStop:
    """
    Calcula trailing stop dinámico basado en ATR
    
    Proceso:
    1. Obtener velas OHLCV recientes
    2. Calcular ATR (Average True Range)
    3. Determinar volatilidad actual
    4. Calcular trailing stop óptimo (ATR × multiplicador)
    5. Aplicar límites mínimos/máximos
    """
    
    def __init__(self, symbol: str, timeframe: str = '1h'):
        """
        symbol: Símbolo de la moneda (ej: 'BTCUSDT')
        timeframe: Timeframe para análisis (ej: '1h', '4h', '1d')
        """
        self.symbol = symbol.upper()
        self.timeframe = timeframe
        self.exchange = self._init_binance()
        
        logger.info(f"🎯 ATR Trailing Stop Calculator")
        logger.info(f"   Symbol: {self.symbol}")
        logger.info(f"   Timeframe: {self.timeframe}")
        logger.info(f"   ATR Period: {ATR_PERIOD}")
    
    def _init_binance(self):
        """Inicializar conexión con Binance"""
        
        try:
            exchange = ccxt.binance({
                'enableRateLimit': True,
            })
            # Test connection
            exchange.fetch_ticker(self.symbol)
            return exchange
        except Exception as e:
            logger.error(f"❌ Error conectando a Binance: {e}")
            raise
    
    def get_ohlcv_data(self, limit: int = 100) -> pd.DataFrame:
        """Obtener datos OHLCV recientes"""
        
        logger.info(f"📊 Obteniendo {limit} velas de {self.symbol}...")
        
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            logger.info(f"   ✅ {len(df)} velas obtenidas")
            
            return df
        except Exception as e:
            logger.error(f"❌ Error obteniendo datos: {e}")
            raise
    
    def calculate_atr(self, df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
        """
        Calcular ATR (Average True Range)
        
        True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
        ATR = Media móvil del True Range
        """
        
        logger.info(f"📈 Calculando ATR({period})...")
        
        # Calcular True Range
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calcular ATR como media móvil
        atr = true_range.rolling(window=period).mean()
        
        # Obtener ATR actual (último valor)
        current_atr = atr.iloc[-1]
        
        logger.info(f"   ✅ ATR actual: ${current_atr:.4f}")
        
        return current_atr
    
    def calculate_volatility_ratio(self, df: pd.DataFrame) -> float:
        """
        Calcular ratio de volatilidad actual vs histórica
        
        Returns: Ratio > 1 = alta volatilidad, < 1 = baja volatilidad
        """
        
        logger.info(f"📊 Calculando ratio de volatilidad...")
        
        # Calcular ATR actual (últimas 14 velas)
        recent_atr = self.calculate_atr(df.tail(14))
        
        # Calcular ATR histórico (últimas 100 velas)
        historical_atr = self.calculate_atr(df)
        
        # Ratio
        volatility_ratio = recent_atr / historical_atr if historical_atr > 0 else 1.0
        
        logger.info(f"   Recent ATR: ${recent_atr:.4f}")
        logger.info(f"   Historical ATR: ${historical_atr:.4f}")
        logger.info(f"   Volatility Ratio: {volatility_ratio:.2f}x")
        
        return volatility_ratio
    
    def calculate_optimal_trailing_stop(self) -> Dict:
        """
        Calcular trailing stop óptimo basado en ATR
        
        Returns: Dict con trailing stop y metadata
        """
        
        logger.info("\n" + "="*60)
        logger.info("🎯 CALCULANDO TRAILING STOP ÓPTIMO")
        logger.info("="*60)
        
        # 1. Obtener datos OHLCV
        df = self.get_ohlcv_data()
        
        # 2. Calcular ATR actual
        current_price = df['close'].iloc[-1]
        current_atr = self.calculate_atr(df)
        
        # 3. Calcular ATR como porcentaje del precio
        atr_percent = (current_atr / current_price) * 100
        
        logger.info(f"\n💰 Precio actual: ${current_price:.4f}")
        logger.info(f"📊 ATR en %: {atr_percent:.2f}%")
        
        # 4. Determinar multiplicador según volatilidad
        volatility_ratio = self.calculate_volatility_ratio(df)
        
        if atr_percent >= VOLATILITY_THRESHOLD * 100 or volatility_ratio > 1.2:
            # Alta volatilidad → stop más wide
            multiplier = ATR_MULTIPLIER_HIGH_VOL
            vol_status = "ALTA"
        else:
            # Baja volatilidad → stop más tight
            multiplier = ATR_MULTIPLIER_LOW_VOL
            vol_status = "BAJA"
        
        logger.info(f"\n🌪️ Volatilidad: {vol_status}")
        logger.info(f"   Volatility Ratio: {volatility_ratio:.2f}x")
        logger.info(f"   Multiplicador ATR: {multiplier}x")
        
        # 5. Calcular trailing stop
        trailing_atr = current_atr * multiplier
        trailing_percent = (trailing_atr / current_price) * 100
        
        # 6. Aplicar límites mínimos/máximos
        if trailing_percent < MIN_TRAILING_PERCENT:
            trailing_percent = MIN_TRAILING_PERCENT
            logger.info(f"⚠️  Aplicado mínimo: {MIN_TRAILING_PERCENT}%")
        elif trailing_percent > MAX_TRAILING_PERCENT:
            trailing_percent = MAX_TRAILING_PERCENT
            logger.info(f"⚠️  Aplicado máximo: {MAX_TRAILING_PERCENT}%")
        
        # Recalcular valor en USDT
        trailing_value = current_price * (trailing_percent / 100)
        
        logger.info(f"\n🎯 TRAILING STOP RECOMENDADO:")
        logger.info(f"   Porcentaje: {trailing_percent:.2f}%")
        logger.info(f"   Valor: ${trailing_value:.4f}")
        logger.info(f"   Basado en: {multiplier}x ATR (${current_atr:.4f})")
        
        # 7. Calcular niveles de ejemplo
        if current_price > 100:
            step_display = 1.0
        elif current_price > 10:
            step_display = 0.10
        else:
            step_display = 0.01
        
        logger.info(f"\n📈 EJEMPLO DE TRAILING:")
        logger.info(f"   Si precio sube a ${current_price * 1.01:.2f} (+1%)")
        logger.info(f"   → Stop sube a ${current_price * 1.01 - trailing_value:.2f}")
        logger.info(f"   Si precio sube a ${current_price * 1.05:.2f} (+5%)")
        logger.info(f"   → Stop sube a ${current_price * 1.05 - trailing_value:.2f}")
        
        logger.info("\n" + "="*60)
        
        result = {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'timestamp': datetime.now().isoformat(),
            'current_price': current_price,
            'atr': current_atr,
            'atr_percent': atr_percent,
            'volatility_ratio': volatility_ratio,
            'volatility_status': vol_status,
            'multiplier': multiplier,
            'trailing_stop_percent': trailing_percent,
            'trailing_stop_value': trailing_value,
            'min_trailing': MIN_TRAILING_PERCENT,
            'max_trailing': MAX_TRAILING_PERCENT,
            'recommendation': f"Usar trailing stop de {trailing_percent:.1f}% ({vol_status} volatilidad)"
        }
        
        # Guardar en cache para uso del bot
        self._save_to_cache(result)
        
        return result
    
    def _save_to_cache(self, result: Dict):
        """Guardar resultado en cache para que el bot lo use"""
        
        cache_file = CACHE_DIR / f"trailing_stop_{self.symbol}.json"
        
        with open(cache_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"💾 Resultado guardado en: {cache_file}")


# ════════════════════════════════════════════════════════
# FUNCIONES DE UTILIDAD
# ════════════════════════════════════════════════════════

def get_trailing_stop_for_coin(coin: str, timeframe: str = '1h') -> Dict:
    """
    Obtener trailing stop recomendado para una moneda
    
    Args:
        coin: Nombre de la moneda (BTC, ETH, etc.)
        timeframe: Timeframe para análisis
    
    Returns: Dict con trailing stop recomendado
    """
    
    symbol = f"{coin}USDT"
    
    try:
        calculator = ATRTrailingStop(symbol, timeframe)
        result = calculator.calculate_optimal_trailing_stop()
        return result
    except Exception as e:
        logger.error(f"❌ Error calculando trailing stop para {coin}: {e}")
        return {
            'error': str(e),
            'symbol': symbol,
            'fallback_trailing_percent': 5.0  # Default si falla
        }


def show_all_coins_trailing_stops():
    """Mostrar trailing stops recomendados para todas las monedas"""
    
    coins = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
    
    print("\n" + "="*80)
    print("🐕 Perrobotillo - Trailing Stops Dinámicos con ATR")
    print("="*80)
    print(f"{'Moneda':<10} | {'Precio':<12} | {'ATR %':<10} | {'Volatilidad':<12} | {'Trailing':<10} | {'Recomendación'}")
    print("-"*80)
    
    results = {}
    
    for coin in coins:
        try:
            result = get_trailing_stop_for_coin(coin)
            
            if 'error' not in result:
                vol_status = result['volatility_status']
                trailing = result['trailing_stop_percent']
                
                print(f"{coin:<10} | ${result['current_price']:<11.4f} | {result['atr_percent']:>6.2f}%  | {vol_status:<12} | {trailing:>6.1f}%    | {result['recommendation']}")
                
                results[coin] = result
        except Exception as e:
            print(f"{coin:<10} | ❌ Error: {str(e)[:40]}")
    
    print("="*80)
    print(f"\n💾 Resultados guardados en cache para uso del bot principal")
    print("="*80 + "\n")
    
    return results


# ════════════════════════════════════════════════════════
# INTEGRACIÓN CON BOT PRINCIPAL
# ════════════════════════════════════════════════════════

def get_cached_trailing_stop(coin: str) -> Dict:
    """
    Obtener trailing stop desde cache (para usar en el bot principal)
    
    El bot principal puede llamar esto para obtener el trailing stop actual
    sin tener que recalcularlo cada vez.
    """
    
    cache_file = CACHE_DIR / f"trailing_stop_{coin.upper()}USDT.json"
    
    if not cache_file.exists():
        logger.warning(f"⚠️  No hay cache para {coin}, calculando...")
        return get_trailing_stop_for_coin(coin)
    
    # Leer cache
    with open(cache_file, 'r') as f:
        cached = json.load(f)
    
    # Verificar si cache es reciente (< 1 hora)
    cached_time = datetime.fromisoformat(cached['timestamp'])
    age_minutes = (datetime.now() - cached_time).total_seconds() / 60
    
    if age_minutes > 60:
        logger.info(f"⚠️  Cache viejo ({age_minutes:.0f} min), recalculando...")
        return get_trailing_stop_for_coin(coin)
    
    logger.info(f"✅ Cache válido para {coin} ({age_minutes:.0f} min)")
    return cached


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='ATR Trailing Stop Calculator')
    parser.add_argument('--coin', type=str, help='Calcular para una moneda específica')
    parser.add_argument('--all', action='store_true', help='Calcular para todas las monedas')
    parser.add_argument('--timeframe', type=str, default='1h', help='Timeframe (default: 1h)')
    
    args = parser.parse_args()
    
    if args.all:
        show_all_coins_trailing_stops()
        sys.exit(0)
    
    if args.coin:
        result = get_trailing_stop_for_coin(args.coin.upper(), args.timeframe)
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            sys.exit(1)
        
        print(f"\n🎯 Trailing Stop Recomendado para {args.coin.upper()}")
        print("="*60)
        print(f"Precio actual: ${result['current_price']:.4f}")
        print(f"ATR: ${result['atr']:.4f} ({result['atr_percent']:.2f}%)")
        print(f"Volatilidad: {result['volatility_status']}")
        print(f"Multiplicador: {result['multiplier']}x")
        print(f"\n✅ TRAILING STOP: {result['trailing_stop_percent']:.1f}%")
        print(f"   Valor: ${result['trailing_stop_value']:.4f}")
        print("="*60)
        
        sys.exit(0)
    
    # Default: mostrar ayuda
    parser.print_help()
    print("\nEjemplos:")
    print("  python3 trailing-stop-atr.py --all")
    print("  python3 trailing-stop-atr.py --coin BTC")
    print("  python3 trailing-stop-atr.py --coin ETH --timeframe 4h")
