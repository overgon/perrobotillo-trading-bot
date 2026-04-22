#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════╗
║  🤖 PERROBOTILLO TRADING BOT - BACKTEST ENGINE       ║
║  FASE 1 v2 - Validación de Estrategia                ║
╚═══════════════════════════════════════════════════════╝
"""

import json
import csv
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import sys

# ============================================
# 📊 CONFIGURACIÓN FASE 1 v2
# ============================================

class CoinConfig:
    """Configuración por moneda"""
    def __init__(self, symbol: str, stop_loss: float, volatility: str):
        self.symbol = symbol
        self.stop_loss = stop_loss  # Porcentaje
        self.volatility = volatility

COINS = {
    'BTC': CoinConfig('BTC', 3.5, '2-4%'),
    'ETH': CoinConfig('ETH', 4.5, '3-5%'),
    'BNB': CoinConfig('BNB', 3.5, '2-4%'),
    'SOL': CoinConfig('SOL', 7.0, '5-8%'),
    'LINK': CoinConfig('LINK', 5.5, '4-6%'),
    'XRP': CoinConfig('XRP', 4.5, '3-5%'),
    'AVAX': CoinConfig('AVAX', 6.0, '4-7%'),
}

# Parámetros FASE 1 v2
TRADE_PERCENT = 30  # Tamaño de posición
TP1_PERCENT = 1.5
TP2_PERCENT = 3.0
TP3_PERCENT = 3.5
TP1_PORTION = 0.35
TP2_PORTION = 0.30
TP3_PORTION = 0.30
ACCUMULATION_PERCENT = 5

TRAILING_AFTER_TP1 = 0.2  # Breakeven
TRAILING_AFTER_TP2 = 2.0  # Trailing stop 2%

MAX_SLOTS = 3
DAILY_LOSS_LIMIT = 3.0  # 3% del portfolio

# ============================================
# 📁 CLASES DE DATOS
# ============================================

class SlotStatus(Enum):
    READY = "READY"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"

@dataclass
class Slot:
    """Representa un slot de trading"""
    slot_id: int
    status: SlotStatus = SlotStatus.READY
    entry_price: float = 0.0
    quantity: float = 0.0
    usdt_spent: float = 0.0
    stop_loss: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    tp1_done: bool = False
    tp2_done: bool = False
    tp3_done: bool = False
    highest_price: float = 0.0
    trailing_active: bool = False
    entry_time: datetime = None
    exit_time: datetime = None
    exit_reason: str = ""
    pnl: float = 0.0
    fee: float = 0.0

@dataclass
class Trade:
    """Registro de trade completado"""
    coin: str
    slot_id: int
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    quantity: float
    pnl: float
    pnl_percent: float
    exit_reason: str
    fee: float

@dataclass
class DailyStats:
    """Estadísticas diarias"""
    date: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    profit: float = 0.0
    loss: float = 0.0
    net_pnl: float = 0.0
    daily_limit_hit: bool = False

# ============================================
#  MOTOR DE BACKTEST
# ============================================

class BacktestEngine:
    """Motor principal de backtesting"""
    
    def __init__(self, initial_capital: float = 2000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.portfolio_value = initial_capital
        self.slots: Dict[str, List[Slot]] = {}
        self.trades: List[Trade] = []
        self.daily_stats: Dict[str, DailyStats] = {}
        self.current_date: str = ""
        
        # Inicializar slots por coin
        for coin in COINS.keys():
            self.slots[coin] = [Slot(slot_id=i+1) for i in range(MAX_SLOTS)]
    
    def load_data(self, filepath: str) -> List[Dict]:
        """Cargar datos históricos desde CSV"""
        print(f"📥 Cargando datos desde: {filepath}")
        data = []
        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ts = row['timestamp']
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    data.append({
                        'timestamp': ts,
                        'coin': row['coin'],
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row.get('volume', 0))
                    })
            print(f"✅ {len(data)} velas cargadas")
            return data
        except FileNotFoundError:
            print(f"❌ Archivo no encontrado: {filepath}")
            return []
        except Exception as e:
            print(f"❌ Error cargando datos: {e}")
            return []
    
    def get_available_slot(self, coin: str) -> Optional[Slot]:
        """Obtener slot disponible"""
        for slot in self.slots[coin]:
            if slot.status == SlotStatus.READY:
                return slot
        return None
    
    def calculate_position_size(self, price: float) -> float:
        """Calcular tamaño de posición"""
        # USAR CAPITAL DISPONIBLE, NO PORTFOLIO VALUE INFLADO
        # El portfolio_value incluye posiciones abiertas (unrealized P&L)
        # Para cálculo de posición, solo usamos el capital en cash disponible
        usdt_amount = self.capital * (TRADE_PERCENT / 100)
        quantity = usdt_amount / price
        return quantity
    
    def open_position(self, coin: str, price: float, timestamp: datetime) -> bool:
        """Abrir posición"""
        slot = self.get_available_slot(coin)
        if not slot:
            return False
        
        config = COINS[coin]
        quantity = self.calculate_position_size(price)
        usdt_spent = quantity * price
        fee = usdt_spent * 0.00015  # 0.015% Binance fee
        
        # Calcular niveles
        sl_price = price * (1 - config.stop_loss / 100)
        tp1_price = price * (1 + TP1_PERCENT / 100)
        tp2_price = price * (1 + TP2_PERCENT / 100)
        tp3_price = price * (1 + TP3_PERCENT / 100)
        
        # Configurar slot
        slot.status = SlotStatus.ACTIVE
        slot.entry_price = price
        slot.quantity = quantity
        slot.usdt_spent = usdt_spent + fee
        slot.stop_loss = sl_price
        slot.tp1 = tp1_price
        slot.tp2 = tp2_price
        slot.tp3 = tp3_price
        slot.entry_time = timestamp
        slot.highest_price = price
        slot.fee = fee
        
        # Actualizar capital
        self.capital -= usdt_spent
        
        print(f"  🟢 {coin} Slot {slot.slot_id}: OPEN @ ${price:.4f} | Qty: {quantity:.4f} | SL: ${sl_price:.4f}")
        
        return True
    
    def check_exit_conditions(self, coin: str, candle: Dict) -> bool:
        """Verificar condiciones de salida"""
        exited = False
        
        for slot in self.slots[coin]:
            if slot.status != SlotStatus.ACTIVE:
                continue
            
            high = candle['high']
            low = candle['low']
            current_price = candle['close']
            
            # Actualizar precio máximo
            if high > slot.highest_price:
                slot.highest_price = high
            
            # Verificar TP1
            if not slot.tp1_done and high >= slot.tp1:
                slot.tp1_done = True
                # Mover SL a breakeven
                slot.stop_loss = slot.entry_price * (1 + TRAILING_AFTER_TP1 / 100)
                slot.trailing_active = True
                print(f"    🎯 {coin} Slot {slot.slot_id}: TP1 HIT @ ${slot.tp1:.4f} | SL → Breakeven")
            
            # Verificar TP2
            if not slot.tp2_done and high >= slot.tp2:
                slot.tp2_done = True
                # Activar trailing stop 2%
                slot.trailing_active = True
                print(f"    🎯 {coin} Slot {slot.slot_id}: TP2 HIT @ ${slot.tp2:.4f} | Trailing 2% ACTIVO")
            
            # Verificar TP3
            if not slot.tp3_done and high >= slot.tp3:
                self.close_position(slot, current_price, candle['timestamp'], "TP3")
                exited = True
                continue
            
            # Verificar Trailing Stop
            if slot.trailing_active:
                trailing_sl = slot.highest_price * (1 - TRAILING_AFTER_TP2 / 100)
                if low <= trailing_sl:
                    self.close_position(slot, trailing_sl, candle['timestamp'], "TRAILING_STOP")
                    exited = True
                    continue
            
            # Verificar Stop Loss
            if low <= slot.stop_loss:
                self.close_position(slot, slot.stop_loss, candle['timestamp'], "STOP_LOSS")
                exited = True
                continue
        
        return exited
    
    def close_position(self, slot: Slot, exit_price: float, timestamp: datetime, reason: str):
        """Cerrar posición"""
        # Calcular P&L
        sell_value = slot.quantity * exit_price
        fee = sell_value * 0.00015
        pnl = sell_value - slot.usdt_spent - fee
        pnl_percent = (pnl / slot.usdt_spent) * 100
        
        # Actualizar slot
        slot.status = SlotStatus.CLOSED
        slot.exit_time = timestamp
        slot.exit_price = exit_price
        slot.exit_reason = reason
        slot.pnl = pnl
        slot.fee += fee
        
        # Actualizar capital
        self.capital += sell_value - fee
        
        # Encontrar la coin del slot
        slot_coin = None
        for coin, slots in self.slots.items():
            if slot in slots:
                slot_coin = coin
                break
        
        # Registrar trade
        trade = Trade(
            coin=slot_coin,
            slot_id=slot.slot_id,
            entry_price=slot.entry_price,
            exit_price=exit_price,
            entry_time=slot.entry_time,
            exit_time=timestamp,
            quantity=slot.quantity,
            pnl=pnl,
            pnl_percent=pnl_percent,
            exit_reason=reason,
            fee=slot.fee
        )
        self.trades.append(trade)
        
        # Actualizar estadísticas diarias
        date_str = timestamp.strftime('%Y-%m-%d')
        if date_str not in self.daily_stats:
            self.daily_stats[date_str] = DailyStats(date=date_str)
        
        stats = self.daily_stats[date_str]
        stats.trades += 1
        if pnl > 0:
            stats.wins += 1
            stats.profit += pnl
        else:
            stats.losses += 1
            stats.loss += abs(pnl)
        stats.net_pnl += pnl
        
        status = "✅" if pnl > 0 else "❌"
        print(f"    {status} {slot.exit_reason}: ${exit_price:.4f} | P&L: ${pnl:.2f} ({pnl_percent:.2f}%)")
    
    def run(self, data: List[Dict]) -> Dict:
        """Ejecutar backtest"""
        print(f"\n🚀 INICIANDO BACKTEST...")
        print(f"   Capital inicial: ${self.initial_capital:.2f}")
        print(f"   Datos: {len(data)} velas")
        
        # Ordenar datos por timestamp
        data.sort(key=lambda x: x['timestamp'])
        
        # Procesar cada vela
        for i, candle in enumerate(data):
            timestamp = candle['timestamp']
            # Asegurar que timestamp sea datetime
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                candle['timestamp'] = timestamp
            
            date_str = timestamp.strftime('%Y-%m-%d')
            coin = candle['coin']
            
            # Actualizar fecha actual
            if date_str != self.current_date:
                self.current_date = date_str
                self.portfolio_value = self.capital + sum(
                    slot.quantity * candle['close']
                    for slots in self.slots.values()
                    for slot in slots
                    if slot.status == SlotStatus.ACTIVE
                )
            
            # Verificar salidas primero
            self.check_exit_conditions(coin, candle)
            
            # Verificar entradas (señal simplificada: 30% probabilidad cada vela)
            # En producción usaríamos indicadores técnicos reales
            import random
            if random.random() < 0.003:  # 0.3% probabilidad = ~45 señales en 15000 velas
                self.open_position(coin, candle['close'], timestamp)
        
        # Generar reporte
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generar reporte de resultados"""
        if not self.trades:
            return {"error": "No trades executed"}
        
        total_trades = len(self.trades)
        wins = sum(1 for t in self.trades if t.pnl > 0)
        losses = total_trades - wins
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        total_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        total_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        net_pnl = total_profit - total_loss
        
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        final_capital = self.capital + sum(
            slot.quantity * 0  # Asumimos que cerramos todo al final
            for slots in self.slots.values()
            for slot in slots
            if slot.status == SlotStatus.ACTIVE
        )
        
        # Calcular drawdown máximo
        peak = self.initial_capital
        max_drawdown = 0
        current_capital = self.initial_capital
        for trade in sorted(self.trades, key=lambda x: x.exit_time):
            current_capital += trade.pnl
            if current_capital > peak:
                peak = current_capital
            drawdown = (peak - current_capital) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        report = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'net_pnl': net_pnl,
            'profit_factor': profit_factor,
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'return_percent': ((self.capital - self.initial_capital) / self.initial_capital) * 100,
            'max_drawdown': max_drawdown,
            'avg_win': total_profit / wins if wins > 0 else 0,
            'avg_loss': total_loss / losses if losses > 0 else 0,
            'trades_by_coin': {},
            'trades_by_reason': {},
        }
        
        # Trades por coin
        for coin in COINS.keys():
            coin_trades = [t for t in self.trades if t.coin == coin]
            if coin_trades:
                report['trades_by_coin'][coin] = {
                    'count': len(coin_trades),
                    'wins': sum(1 for t in coin_trades if t.pnl > 0),
                    'net_pnl': sum(t.pnl for t in coin_trades),
                }
        
        # Trades por razón de salida
        for reason in ['TP1', 'TP2', 'TP3', 'STOP_LOSS', 'TRAILING_STOP']:
            reason_trades = [t for t in self.trades if reason in t.exit_reason]
            if reason_trades:
                report['trades_by_reason'][reason] = {
                    'count': len(reason_trades),
                    'win_rate': sum(1 for t in reason_trades if t.pnl > 0) / len(reason_trades) * 100,
                }
        
        return report
    
    def print_report(self, report: Dict):
        """Imprimir reporte formateado"""
        print("\n" + "="*60)
        print("╔═══════════════════════════════════════════════════════╗")
        print("║  📊 REPORTE DE BACKTEST - PERROBOTILLO               ║")
        print("╚═══════════════════════════════════════════════════════╝")
        print("="*60)
        
        print(f"\n📈 ESTADÍSTICAS GENERALES:")
        print(f"   Total Trades:        {report['total_trades']}")
        print(f"   Wins:                {report['wins']}")
        print(f"   Losses:              {report['losses']}")
        print(f"   Win Rate:            {report['win_rate']:.2f}%")
        
        print(f"\n💰 RESULTADOS FINANCIEROS:")
        print(f"   Capital Inicial:     ${report['initial_capital']:.2f}")
        print(f"   Capital Final:       ${report['final_capital']:.2f}")
        print(f"   P&L Neto:            ${report['net_pnl']:.2f}")
        print(f"   Retorno:             {report['return_percent']:.2f}%")
        print(f"   Profit Factor:       {report['profit_factor']:.2f}")
        print(f"   Max Drawdown:        {report['max_drawdown']:.2f}%")
        
        print(f"\n📊 PROMEDIOS:")
        print(f"   Avg Win:             ${report['avg_win']:.2f}")
        print(f"   Avg Loss:            ${report['avg_loss']:.2f}")
        print(f"   Win/Loss Ratio:      {report['avg_win']/report['avg_loss']:.2f}" if report['avg_loss'] > 0 else "   Win/Loss Ratio: N/A")
        
        print(f"\n🪙 POR MONEDA:")
        for coin, stats in report['trades_by_coin'].items():
            win_rate = (stats['wins'] / stats['count']) * 100 if stats['count'] > 0 else 0
            print(f"   {coin:4s}: {stats['count']:3d} trades | {stats['wins']:2d} wins ({win_rate:5.1f}%) | P&L: ${stats['net_pnl']:+.2f}")
        
        print(f"\n🎯 POR RAZÓN DE SALIDA:")
        for reason, stats in report['trades_by_reason'].items():
            print(f"   {reason:15s}: {stats['count']:3d} trades | Win Rate: {stats['win_rate']:.1f}%")
        
        print("\n" + "="*60)
        
        # Validación FASE 1 v2
        print("\n🎯 VALIDACIÓN FASE 1 v2:")
        if report['win_rate'] >= 25:
            print(f"   ✅ Win Rate: {report['win_rate']:.1f}% (META: >25%)")
        else:
            print(f"   ❌ Win Rate: {report['win_rate']:.1f}% (META: >25%)")
        
        if report['net_pnl'] > 0:
            print(f"   ✅ P&L Positivo: ${report['net_pnl']:.2f}")
        else:
            print(f"   ❌ P&L Negativo: ${report['net_pnl']:.2f}")
        
        if report['profit_factor'] >= 1.5:
            print(f"   ✅ Profit Factor: {report['profit_factor']:.2f} (META: >1.5)")
        else:
            print(f"   ⚠️  Profit Factor: {report['profit_factor']:.2f} (META: >1.5)")
        
        if report['max_drawdown'] <= 15:
            print(f"   ✅ Drawdown Controlado: {report['max_drawdown']:.1f}%")
        else:
            print(f"   ⚠️  Drawdown Alto: {report['max_drawdown']:.1f}%")
        
        print("="*60)


# ============================================
# 🚀 MAIN
# ============================================

if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🤖 PERROBOTILLO BACKTEST ENGINE v1.0                ║")
    print("╚═══════════════════════════════════════════════════════╝")
    
    # Crear engine
    engine = BacktestEngine(initial_capital=2000.0)
    
    # Intentar cargar datos de ejemplo (si existen)
    import os
    test_data = []
    
    # Generar datos sintéticos para prueba
    print("\n📝 Generando datos sintéticos para prueba...")
    from datetime import datetime, timedelta
    import random
    
    coins = list(COINS.keys())
    start_date = datetime(2026, 1, 1)
    
    for coin in coins:
        price = {
            'BTC': 75000, 'ETH': 2400, 'BNB': 630,
            'SOL': 90, 'LINK': 9.5, 'XRP': 1.45, 'AVAX': 9.5
        }[coin]
        
        volatility = {
            'BTC': 0.02, 'ETH': 0.03, 'BNB': 0.025,
            'SOL': 0.05, 'LINK': 0.04, 'XRP': 0.035, 'AVAX': 0.045
        }[coin]
        
        for day in range(90):  # 90 días
            for hour in range(24):  # 24 horas
                timestamp = start_date + timedelta(days=day, hours=hour)
                
                # Simular movimiento de precio
                change = random.gauss(0, volatility)
                price = price * (1 + change)
                
                high = price * (1 + abs(random.gauss(0, volatility/2)))
                low = price * (1 - abs(random.gauss(0, volatility/2)))
                open_price = price * (1 + random.gauss(0, volatility/3))
                close_price = price
                
                test_data.append({
                    'timestamp': timestamp.isoformat(),
                    'coin': coin,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close_price,
                    'volume': random.uniform(1000, 10000)
                })
    
    print(f"✅ {len(test_data)} velas generadas")
    
    # Guardar datos de prueba
    output_file = '/home/overgon/.openclaw/workspace/backtest/test_data.csv'
    with open(output_file, 'w', newline='') as f:
        fieldnames = ['timestamp', 'coin', 'open', 'high', 'low', 'close', 'volume']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_data)
    print(f"💾 Datos guardados en: {output_file}")
    
    # Ejecutar backtest
    report = engine.run(test_data)
    
    # Imprimir reporte
    if 'error' not in report:
        engine.print_report(report)
        
        # Guardar reporte en JSON
        report_file = '/home/overgon/.openclaw/workspace/backtest/backtest_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n💾 Reporte guardado en: {report_file}")
    else:
        print(f"\n❌ Error: {report['error']}")
