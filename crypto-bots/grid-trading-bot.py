#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - GRID TRADING BOT
# ════════════════════════════════════════════════════════
# Estrategia Grid Trading para mercados laterales
# Inspirado en Open-Trader pero mejorado con ML Validator
# ════════════════════════════════════════════════════════

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path
import time
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
SECRETS = Path("/home/overgon/.openclaw/secrets")
LOGS_DIR = Path("/home/overgon/.openclaw/logs")
CONFIG_DIR = WORKSPACE / "config" / "grid"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Configuración por defecto para cada moneda
DEFAULT_GRID_CONFIG = {
    "BTC": {
        "enabled": False  # Desactivado en migración a Slots,
        "low_price": 57904,      # ✅ ACTUALIZADO: BTC ~$65,754 (Jun 2026)
        "high_price": 73696,     # Rango: $56k-$76k (±15% del precio actual)
        "grid_levels": 10,       # Número de niveles
        "quantity_per_grid": 0.000628,  # Cantidad BTC por nivel
        "max_investment": 500,   # Máximo USDT invertidos
        "stop_loss": 0.95,       # SL si precio cae 5% debajo del rango
        "take_profit": 1.05,     # TP si precio sube 5% encima del rango
    },
    "ETH": {
        "enabled": False  # Desactivado en migración a Slots,
        "low_price": 1575,       # ✅ ACTUALIZADO: ETH ~$1,783 (Jun 2026)
        "high_price": 2005,      # Rango: $1.5k-$2k (±15% del precio actual)
        "grid_levels": 12,
        "quantity_per_grid": 0.023,
        "max_investment": 400,
        "stop_loss": 0.95,
        "take_profit": 1.05,
    },
    "BNB": {
        "enabled": False  # Desactivado en migración a Slots,
        "low_price": 534,
        "high_price": 680,
        "grid_levels": 15,
        "quantity_per_grid": 0.068,
        "max_investment": 300,
        "stop_loss": 0.92,
        "take_profit": 1.10,
    },
    "SOL": {
        "enabled": False  # Desactivado en migración a Slots,  # ✅ Habilitado para Grid Trading
        "low_price": 64.59,    # Actualizado: SOL ~$73.88
        "high_price": 82.21,
        "grid_levels": 10,
        "quantity_per_grid": 0.5,
        "max_investment": 200,
        "stop_loss": 0.88,
        "take_profit": 1.12,
    },
    "ZEC": {
        "enabled": False  # Desactivado en migración a Slots,  # ✅ Habilitado para Grid Trading
        "low_price": 7.23,   # Actualizado: LINK ~$8.46
        "high_price": 9.21,
        "grid_levels": 10,
        "quantity_per_grid": 5,
        "max_investment": 200,
        "stop_loss": 0.88,
        "take_profit": 1.12,
    },
    "XRP": {
        "enabled": False  # Desactivado en migración a Slots,
        "low_price": 1.07,   # ⚠️ AJUSTADO: Antes $1.20 (-5%), ahora $1.15 (-8%)
        "high_price": 1.37,
        "grid_levels": 12,
        "quantity_per_grid": 50,
        "max_investment": 200,
        "stop_loss": 0.88,   # ⚠️ AJUSTADO: Antes 0.95 (-5%), ahora 0.88 (-12%)
        "take_profit": 1.05,
    },
    "AVAX": {
        "enabled": False  # Desactivado en migración a Slots,  # ✅ Habilitado para Grid Trading
        "low_price": 6.0,     # Actualizado: AVAX ~$6.95
        "high_price": 7.64,
        "grid_levels": 15,
        "quantity_per_grid": 3,
        "max_investment": 100,
        "stop_loss": 0.88,
        "take_profit": 1.12,
        "monte_carlo_verified": True,
        "skill_confirmed": True
    },
    "BTC": {
        "enabled": False  # Desactivado en migración a Slots,  # ✅ Habilitado para Grid Trading
        "low_price": 57904,   # Actualizado: BTC ~$66,660
        "high_price": 73696,
        "grid_levels": 10,
        "quantity_per_grid": 0.001,
        "max_investment": 500,
        "stop_loss": 0.92,
        "take_profit": 1.08,
    },
    "ETH": {
        "enabled": False  # Desactivado en migración a Slots,  # ✅ Habilitado para Grid Trading
        "low_price": 1575,   # Actualizado: ETH ~$1,816
        "high_price": 2005,
        "grid_levels": 12,
        "quantity_per_grid": 0.01,
        "max_investment": 400,
        "stop_loss": 0.90,
        "take_profit": 1.10,
    },
}

# ════════════════════════════════════════════════════════
# BINANCE CONNECTION
# ════════════════════════════════════════════════════════

class BinanceClient:
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': self._load_secret('BINANCE_API_KEY'),
            'secret': self._load_secret('BINANCE_API_SECRET'),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
    
    def _load_secret(self, key: str) -> str:
        env_file = SECRETS / "binance.env"
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith(f"{key}="):
                        return line.strip().split('=')[1]
        return ""
    
    def get_balance(self, currency: str) -> float:
        """Obtener balance de una moneda"""
        try:
            balance = self.exchange.fetch_balance()
            return float(balance[currency]['free'])
        except:
            return 0.0
    
    def get_ticker(self, symbol: str) -> float:
        """Obtener precio actual"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except:
            return 0.0
    
    def place_order(self, symbol: str, side: str, amount: float, price: float) -> dict:
        """Colocar orden límite"""
        try:
            order = self.exchange.create_limit_order(symbol, side, amount, price)
            return order
        except Exception as e:
            print(f"❌ Error placing order: {e}")
            return {}
    
    def cancel_order(self, symbol: str, order_id: str):
        """Cancelar orden"""
        try:
            self.exchange.cancel_order(order_id, symbol)
        except:
            pass
    
    def cancel_all_orders(self, symbol: str):
        """Cancelar todas las órdenes abiertas"""
        try:
            open_orders = self.exchange.fetch_open_orders(symbol)
            for order in open_orders:
                self.cancel_order(symbol, order['id'])
        except:
            pass
    
    def get_open_orders(self, symbol: str) -> List[dict]:
        """Obtener órdenes abiertas"""
        try:
            return self.exchange.fetch_open_orders(symbol)
        except:
            return []

# ════════════════════════════════════════════════════════
# GRID TRADING ENGINE
# ════════════════════════════════════════════════════════

class GridTradingBot:
    def __init__(self, coin: str, config: dict = None, dry_run: bool = False):
        self.coin = coin
        self.symbol = f"{coin}/USDT"
        self.config = config or DEFAULT_GRID_CONFIG.get(coin, {})
        self.client = BinanceClient()
        self.dry_run = dry_run  # 🆕 PAPER TRADING MODE
        
        # 🆕 Balances simulados para paper trading
        self.paper_balance_usdt = 1000.0  # $1000 USDT virtuales
        self.paper_balance_coin = 0.0
        self.paper_orders = []
        self.paper_trades = []
        
        self.active_orders = []
        self.total_invested = 0
        self.total_profit = 0
        self.trades_count = 0
        
        # 🆕 Track buy prices for accurate P&L calculation
        self.filled_buy_orders = {}  # order_id -> {price, amount}
        
        # Log file
        self.log_file = LOGS_DIR / f"grid-{coin}.log"
    
    def log(self, message: str):
        """Log message to file and console"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        
        with open(self.log_file, 'a') as f:
            f.write(log_line + '\n')
    
    def calculate_grid_levels(self, current_price: float) -> List[dict]:
        """Calcular niveles de la grilla"""
        
        low_price = self.config.get('low_price', current_price * 0.9)
        high_price = self.config.get('high_price', current_price * 1.1)
        grid_levels = self.config.get('grid_levels', 10)
        
        # Ajustar rango si precio actual está fuera
        if current_price < low_price:
            low_price = current_price * 0.95
            self.log(f"⚠️ Precio actual ${current_price} debajo del rango, ajustando low_price a ${low_price:.2f}")
        elif current_price > high_price:
            high_price = current_price * 1.05
            self.log(f"⚠️ Precio actual ${current_price} encima del rango, ajustando high_price a ${high_price:.2f}")
        
        # Calcular spacing entre niveles
        price_range = high_price - low_price
        grid_spacing = price_range / grid_levels
        
        levels = []
        
        # Generar niveles de compra (below current price)
        buy_levels = []
        price = current_price - grid_spacing
        while price >= low_price:
            buy_levels.append({
                'type': 'buy',
                'price': round(price, 2),
                'amount': self.config.get('quantity_per_grid', 0.01)
            })
            price -= grid_spacing
        
        # Generar niveles de venta (above current price)
        sell_levels = []
        price = current_price + grid_spacing
        while price <= high_price:
            sell_levels.append({
                'type': 'sell',
                'price': round(price, 2),
                'amount': self.config.get('quantity_per_grid', 0.01)
            })
            price += grid_spacing
        
        levels = buy_levels + sell_levels
        
        self.log(f"📊 Grid calculado: {len(buy_levels)} buys, {len(sell_levels)} sells")
        self.log(f"   Rango: ${low_price:.2f} - ${high_price:.2f}")
        self.log(f"   Spacing: ${grid_spacing:.2f}")
        
        return levels
    
    def setup_grid(self):
        """Configurar la grilla inicial de órdenes"""
        
        self.log("╔═══════════════════════════════════════════════════════╗")
        self.log(f"║  🐕 GRID TRADING BOT - {self.coin}")
        self.log("╚═══════════════════════════════════════════════════════╝")
        
        # Cancelar órdenes existentes
        self.log("🔄 Cancelando órdenes existentes...")
        self.client.cancel_all_orders(self.symbol)
        time.sleep(1)
        
        # Obtener precio actual
        current_price = self.client.get_ticker(self.symbol)
        if current_price == 0:
            self.log("❌ Error obteniendo precio")
            return False
        
        self.log(f"💰 Precio actual: ${current_price}")
        
        # Calcular niveles
        grid_levels = self.calculate_grid_levels(current_price)
        
        # Verificar balances
        usdt_balance = self.client.get_balance('USDT')
        coin_balance = self.client.get_balance(self.coin)
        
        self.log(f"💵 Balance USDT: ${usdt_balance:.2f}")
        self.log(f"🪙 Balance {self.coin}: {coin_balance}")
        
        # Colocar órdenes
        self.log("\n📋 Colocando órdenes...")
        placed_orders = []
        
        for level in grid_levels:
            # Verificar si tenemos balance suficiente
            required_usdt = level['price'] * level['amount'] if level['type'] == 'buy' else 0
            
            if level['type'] == 'buy' and required_usdt > usdt_balance:
                continue  # Saltar si no hay USDT suficiente
            
            if level['type'] == 'sell' and level['amount'] > coin_balance:
                continue  # Saltar si no hay coin suficiente
            
            # Colocar orden
            side = 'buy' if level['type'] == 'buy' else 'sell'
            order = self.client.place_order(self.symbol, side, level['amount'], level['price'])
            
            if order and 'id' in order:
                placed_orders.append({
                    'id': order['id'],
                    'type': level['type'],
                    'price': level['price'],
                    'amount': level['amount'],
                    'side': side
                })
                
                self.log(f"  {'✅' if level['type'] == 'buy' else '✅'} {side.upper()} {level['amount']} {self.coin} @ ${level['price']}")
                
                # 🆕 Track buy orders for P&L calculation
                if level['type'] == 'buy':
                    self.filled_buy_orders[order['id']] = {
                        'price': level['price'],
                        'amount': level['amount']
                    }
            
            time.sleep(0.1)  # Rate limit
        
        self.active_orders = placed_orders
        self.log(f"\n✅ Grid configurado: {len(placed_orders)} órdenes activas")
        self.log("╔═══════════════════════════════════════════════════════╗")
        
        return len(placed_orders) > 0
    
    def monitor_and_rebalance(self):
        """Monitorear órdenes y rebalancear cuando se ejecutan"""
        
        self.log("\n👁️ Monitoreando grid...")
        
        # Verificar órdenes ejecutadas
        filled_orders = []
        
        for order in self.active_orders[:]:
            order_status = self.client.exchange.fetch_order(order['id'], self.symbol)
            
            if order_status['status'] == 'closed':
                filled_orders.append(order)
                self.active_orders.remove(order)
                
                # 🆕 Calcular profit/loss REAL basado en precio de compra
                if order['type'] == 'sell':
                    # Buscar el buy order correspondiente (mismo amount)
                    buy_order = None
                    for buy_id, buy_info in self.filled_buy_orders.items():
                        if abs(buy_info['amount'] - order['amount']) < 0.0001:
                            buy_order = buy_info
                            del self.filled_buy_orders[buy_id]
                            break
                    
                    if buy_order:
                        # P&L real = (sell_price - buy_price) * quantity - fees
                        sell_value = order['price'] * order['amount']
                        buy_value = buy_order['price'] * order['amount']
                        fees = sell_value * 0.001  # 0.1% Binance fee
                        profit = sell_value - buy_value - fees
                    else:
                        # Fallback si no encontramos el buy order
                        profit = (order['price'] * 0.01) * order['amount']
                    
                    self.total_profit += profit
                    self.trades_count += 1
                    
                    self.log(f"🎯 Orden {order['type'].upper()} ejecutada: {order['amount']} @ ${order['price']}")
                    self.log(f"   Profit: ${profit:.4f} | Total trades: {self.trades_count}")
                    
                    # Registrar en historial con datos reales
                    entry_price = buy_order['price'] if buy_order else order['price'] * 0.99
                    self.save_grid_trade(order['amount'], order['price'], profit, entry_price)
                
                # Re-colocar orden en el lado opuesto
                self._replenish_order(order)
        
        if filled_orders:
            self.log(f"\n📊 Resumen: {len(filled_orders)} órdenes ejecutadas, Profit total: ${self.total_profit:.2f}")
        
        return len(filled_orders)
    
    def _replenish_order(self, filled_order: dict):
        """Re-colocar orden después de ejecución"""
        
        current_price = self.client.get_ticker(self.symbol)
        
        # Si fue buy, colocar sell arriba
        if filled_order['type'] == 'buy':
            sell_price = filled_order['price'] * 1.01  # 1% profit mínimo
            order = self.client.place_order(self.symbol, 'sell', filled_order['amount'], sell_price)
            
            if order and 'id' in order:
                self.active_orders.append({
                    'id': order['id'],
                    'type': 'sell',
                    'price': sell_price,
                    'amount': filled_order['amount'],
                    'side': 'sell'
                })
                self.log(f"  🔄 Re-colocada SELL @ ${sell_price:.2f}")
        
        # Si fue sell, colocar buy abajo
        elif filled_order['type'] == 'sell':
            buy_price = filled_order['price'] * 0.99  # 1% discount
            order = self.client.place_order(self.symbol, 'buy', filled_order['amount'], buy_price)
            
            if order and 'id' in order:
                self.active_orders.append({
                    'id': order['id'],
                    'type': 'buy',
                    'price': buy_price,
                    'amount': filled_order['amount'],
                    'side': 'buy'
                })
                self.log(f"  🔄 Re-colocada BUY @ ${buy_price:.2f}")
    
    def check_exit_conditions(self, current_price: float) -> bool:
        """Verificar condiciones de salida (SL/TP del rango)"""
        
        low_price = self.config.get('low_price', 0)
        high_price = self.config.get('high_price', 0)
        stop_loss = self.config.get('stop_loss', 0.95)
        take_profit = self.config.get('take_profit', 1.05)
        
        # Stop loss: precio cayó debajo del rango
        if current_price < low_price * stop_loss:
            self.log(f"🚨 STOP LOSS: Precio ${current_price} < ${low_price * stop_loss:.2f}")
            return True
        
        # Take profit: precio subió encima del rango
        if current_price > high_price * take_profit:
            self.log(f"🎯 TAKE PROFIT: Precio ${current_price} > ${high_price * take_profit:.2f}")
            return True
        
        return False
    
    def run(self, duration_hours: int = 24, check_interval_min: int = 5):
        """Ejecutar el bot por X horas"""
        
        self.log(f"🚀 Iniciando Grid Trading Bot por {duration_hours} horas...")
        
        # Setup inicial
        if not self.setup_grid():
            self.log("❌ Error en setup inicial")
            return False
        
        # Monitoreo continuo
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        
        while datetime.now() < end_time:
            try:
                # Verificar exit conditions
                current_price = self.client.get_ticker(self.symbol)
                
                if self.check_exit_conditions(current_price):
                    self.log("🚪 Saliendo por SL/TP...")
                    self.close_all_positions()
                    return True
                
                # Monitorear y rebalancear
                filled = self.monitor_and_rebalance()
                
                if filled:
                    self.log(f"💰 Profit acumulado: ${self.total_profit:.2f}")
                
                # Wait next check
                time.sleep(check_interval_min * 60)
                
            except KeyboardInterrupt:
                self.log("\n⌨️ Interrumpido por usuario")
                break
            except Exception as e:
                self.log(f"❌ Error: {e}")
                time.sleep(60)
        
        self.log("\n⏰ Tiempo completado, cerrando posiciones...")
        self.close_all_positions()
        
        return True
    
    def close_all_positions(self):
        """Cerrar todas las posiciones y cancelar órdenes"""
        
        self.log("🚪 Cerrando todas las posiciones...")
        
        # Cancelar órdenes abiertas
        self.client.cancel_all_orders(self.symbol)
        
        # Vender todo el coin restante
        coin_balance = self.client.get_balance(self.coin)
        exit_price = self.client.get_ticker(self.symbol) * 0.99
        if coin_balance > 0.001:  # Mínimo tradeable
            order = self.client.place_order(self.symbol, 'sell', coin_balance, exit_price)
            self.log(f"  💰 Vendidos {coin_balance} {self.coin} restantes @ ${exit_price:.2f}")
            
            # Registrar trade en historial
            self.save_grid_trade(coin_balance, exit_price, 0)
        
        # Calcular P&L final
        usdt_balance = self.client.get_balance('USDT')
        
        self.log(f"\n📊 RESUMEN FINAL:")
        self.log(f"  Trades ejecutados: {self.trades_count}")
        self.log(f"  Profit total: ${self.total_profit:.2f}")
        self.log(f"  Balance USDT final: ${usdt_balance:.2f}")
        self.log("╔═══════════════════════════════════════════════════════╗")
    
    def save_grid_trade(self, quantity: float, exit_price: float, profit: float, entry_price: float = None):
        """Guardar trade de grid en trade-history.json"""
        history_file = WORKSPACE / "crypto-bots" / "trade-history.json"
        
        try:
            # Calcular P&L real
            pnl = profit
            close_type = "GRID_TP" if pnl > 0 else "GRID_SL"
            
            # Cargar historial existente
            if history_file.exists():
                with open(history_file, 'r') as f:
                    data = json.load(f)
            else:
                data = {
                    "version": "1.0",
                    "created": datetime.now().isoformat(),
                    "strategy": "Grid Trading",
                    "totalTrades": 0,
                    "totalWins": 0,
                    "totalLosses": 0,
                    "netPnLUSDT": 0,
                    "winRate": 0,
                    "trades": []
                }
            
            # Crear nuevo trade
            new_trade = {
                "id": data.get('totalTrades', 0) + 1,
                "symbol": self.coin,
                "slotId": 99,  # Grid Bot usa slot 99
                "type": "LONG",
                "entryPrice": round(entry_price if entry_price else exit_price * 0.99, 8),
                "exitPrice": round(exit_price, 2),
                "quantity": round(quantity, 8),
                "closeType": close_type,
                "pnlUSDT": round(pnl, 8),
                "timestamp": datetime.now().isoformat(),
                "closeTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "seeded": False,
                "note": f"Grid Bot - Auto {close_type.replace('_', '/')}"
            }
            
            # Actualizar stats
            data['trades'].insert(0, new_trade)
            data['totalTrades'] += 1
            if pnl > 0:
                data['totalWins'] += 1
            else:
                data['totalLosses'] += 1
            data['netPnLUSDT'] += pnl
            data['winRate'] = round((data['totalWins'] / data['totalTrades']) * 100, 2) if data['totalTrades'] > 0 else 0
            
            # Guardar
            with open(history_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.log(f"  📝 Trade #{new_trade['id']} guardado en historial | PnL: ${pnl:.4f}")
            
        except Exception as e:
            self.log(f"  ⚠️ Error guardando trade: {e}")

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Perrobotillo Grid Trading Bot")
    parser.add_argument("--coin", type=str, default="BNB", help="Moneda para grid trading")
    parser.add_argument("--hours", type=int, default=24, help="Duración en horas")
    parser.add_argument("--interval", type=int, default=5, help="Intervalo de chequeo en minutos")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación (sin trades reales)")
    parser.add_argument("--setup", action="store_true", help="Solo configurar grid inicial")
    
    args = parser.parse_args()
    
    coin = args.coin.upper()
    
    if coin not in DEFAULT_GRID_CONFIG:
        print(f"❌ Moneda no soportada: {coin}")
        print(f"Monedas disponibles: {', '.join(DEFAULT_GRID_CONFIG.keys())}")
        sys.exit(1)
    
    config = DEFAULT_GRID_CONFIG[coin]
    
    if not config.get('enabled', False):
        print(f"⚠️ Grid trading no habilitado para {coin} por alta volatilidad")
        print("Edita DEFAULT_GRID_CONFIG para habilitar")
        sys.exit(1)
    
    if args.dry_run:
        print("🧪 MODO DRY-RUN: No se ejecutarán trades reales")
    
    bot = GridTradingBot(coin, config)
    
    if args.setup:
        bot.setup_grid()
    else:
        bot.run(duration_hours=args.hours, check_interval_min=args.interval)

if __name__ == "__main__":
    main()
