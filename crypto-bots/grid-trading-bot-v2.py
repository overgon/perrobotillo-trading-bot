#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - GRID TRADING BOT v2 (CON PAPER TRADING)
# ════════════════════════════════════════════════════════
# Estrategia Grid Trading con modo Paper Trading integrado
# Para validar sin riesgo antes de usar dinero real
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

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
SECRETS = Path("/home/overgon/.secrets")
LOGS_DIR = Path("/home/overgon/.openclaw/logs")

DEFAULT_GRID_CONFIG = {
    "BNB": {
        "enabled": True,
        "low_price": 650,
        "high_price": 800,
        "grid_levels": 15,
        "quantity_per_grid": 0.05,
        "max_investment": 300,
        "stop_loss": 0.95,
        "take_profit": 1.05,
    },
    # ... más monedas ...
}

# ════════════════════════════════════════════════════════
# GRID TRADING BOT CON PAPER TRADING
# ════════════════════════════════════════════════════════

class GridTradingBot:
    def __init__(self, coin: str, config: dict = None, dry_run: bool = True):
        self.coin = coin
        self.symbol = f"{coin}/USDT"
        self.config = config or DEFAULT_GRID_CONFIG.get(coin, {})
        self.dry_run = dry_run  # True = Paper Trading, False = Live
        
        # Inicializar cliente Binance (solo para obtener precios)
        try:
            self.client = ccxt.binance({'enableRateLimit': True})
        except:
            self.client = None
        
        # Balances (reales o simulados)
        if self.dry_run:
            self.paper_balance_usdt = 1000.0  # $1000 virtuales iniciales
            self.paper_balance_coin = 0.0
            self.paper_orders = []
            self.paper_trades = []
        
        self.active_orders = []
        self.total_profit = 0
        self.trades_count = 0
        
        self.log_file = LOGS_DIR / f"grid-{coin}-{'paper' if dry_run else 'live'}.log"
    
    def log(self, message: str):
        """Log con indicador de modo"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mode = "🧪 PAPER" if self.dry_run else "💰 LIVE"
        log_line = f"[{timestamp}] {mode} {message}"
        print(log_line)
        
        with open(self.log_file, 'a') as f:
            f.write(log_line + '\n')
    
    def get_current_price(self) -> float:
        """Obtener precio actual"""
        try:
            ticker = self.client.fetch_ticker(self.symbol)
            return float(ticker['last'])
        except:
            # Precio fallback si falla API
            prices = {"BTC": 73700, "ETH": 2032, "BNB": 737, "SOL": 83, "LINK": 9.24, "XRP": 1.34, "AVAX": 9.03}
            return prices.get(self.coin, 100)
    
    def calculate_grid_levels(self, current_price: float) -> List[dict]:
        """Calcular niveles de la grilla"""
        
        low_price = self.config.get('low_price', current_price * 0.9)
        high_price = self.config.get('high_price', current_price * 1.1)
        grid_levels = self.config.get('grid_levels', 10)
        
        # Ajustar rango si es necesario
        if current_price < low_price:
            low_price = current_price * 0.95
        elif current_price > high_price:
            high_price = current_price * 1.05
        
        grid_spacing = (high_price - low_price) / grid_levels
        
        levels = []
        
        # Buy orders (debajo del precio actual)
        price = current_price - grid_spacing
        while price >= low_price:
            levels.append({
                'type': 'buy',
                'price': round(price, 2),
                'amount': self.config.get('quantity_per_grid', 0.01)
            })
            price -= grid_spacing
        
        # Sell orders (encima del precio actual)
        price = current_price + grid_spacing
        while price <= high_price:
            levels.append({
                'type': 'sell',
                'price': round(price, 2),
                'amount': self.config.get('quantity_per_grid', 0.01)
            })
            price += grid_spacing
        
        return levels
    
    def place_order(self, side: str, amount: float, price: float) -> dict:
        """Colocar orden (real o simulada)"""
        
        if self.dry_run:
            # PAPER TRADING: Simular orden
            total = amount * price
            
            if side == 'buy' and total > self.paper_balance_usdt:
                return {}
            if side == 'sell' and amount > self.paper_balance_coin:
                return {}
            
            # Actualizar balances simulados
            if side == 'buy':
                self.paper_balance_usdt -= total
                self.paper_balance_coin += amount
            else:
                self.paper_balance_coin -= amount
                self.paper_balance_usdt += total
            
            order = {
                'id': f"paper_{len(self.paper_orders) + 1}",
                'side': side,
                'amount': amount,
                'price': price,
                'status': 'open',
                'type': side
            }
            
            self.paper_orders.append(order)
            return order
        
        else:
            # LIVE TRADING: Orden real en Binance
            try:
                order = self.client.create_limit_order(self.symbol, side, amount, price)
                return order
            except Exception as e:
                self.log(f"❌ Error orden real: {e}")
                return {}
    
    def setup_grid(self):
        """Configurar grilla inicial"""
        
        self.log("╔═══════════════════════════════════════════════════════╗")
        self.log(f"║  🐕 GRID TRADING BOT - {self.coin}")
        self.log("╚═══════════════════════════════════════════════════════╝")
        
        # Obtener precio actual
        current_price = self.get_current_price()
        self.log(f"💰 Precio actual: ${current_price}")
        
        # Calcular niveles
        grid_levels = self.calculate_grid_levels(current_price)
        buy_count = len([l for l in grid_levels if l['type'] == 'buy'])
        sell_count = len([l for l in grid_levels if l['type'] == 'sell'])
        
        self.log(f"📊 Grid calculado: {buy_count} buys, {sell_count} sells")
        self.log(f"   Rango: ${self.config.get('low_price')} - ${self.config.get('high_price')}")
        
        # Mostrar balances
        if self.dry_run:
            self.log(f"💵 Balance USDT (virtual): ${self.paper_balance_usdt:.2f}")
            self.log(f"🪙 Balance {self.coin} (virtual): {self.paper_balance_coin}")
        else:
            self.log(f"💵 Balance USDT (real): ${self.get_balance('USDT'):.2f}")
            self.log(f"🪙 Balance {self.coin} (real): {self.get_balance(self.coin)}")
        
        # Colocar órdenes
        self.log("\n📋 Colocando órdenes...")
        placed_count = 0
        
        for level in grid_levels:
            order = self.place_order(level['type'], level['amount'], level['price'])
            
            if order and 'id' in order:
                self.active_orders.append(order)
                symbol = "✅" if level['type'] == 'buy' else "✅"
                self.log(f"  {symbol} {level['type'].upper()} {level['amount']} @ ${level['price']}")
                placed_count += 1
            
            time.sleep(0.1)
        
        self.log(f"\n✅ Grid configurado: {placed_count} órdenes activas")
        
        return placed_count > 0
    
    def get_balance(self, currency: str) -> float:
        """Obtener balance real de Binance"""
        try:
            balance = self.client.fetch_balance()
            return float(balance[currency]['free'])
        except:
            return 0.0
    
    def monitor_and_rebalance(self):
        """Monitorear y rebalancear (simulado en paper trading)"""
        
        current_price = self.get_current_price()
        filled_count = 0
        
        # Simular fills basados en precio actual
        for order in self.active_orders[:]:
            should_fill = False
            
            if order['type'] == 'buy' and current_price <= order['price']:
                should_fill = True
            elif order['type'] == 'sell' and current_price >= order['price']:
                should_fill = True
            
            if should_fill:
                filled_count += 1
                self.trades_count += 1
                
                # Calcular profit (simplificado)
                if order['type'] == 'sell':
                    profit = (order['price'] - order['price'] * 0.99) * order['amount']
                    self.total_profit += profit
                
                # Remover orden fillada
                self.active_orders.remove(order)
                
                self.log(f"🎯 {order['type'].upper()} ejecutada: {order['amount']} @ ${order['price']}")
                
                # Re-colocar orden opuesta
                self._replenish_order(order)
        
        return filled_count
    
    def _replenish_order(self, filled_order: dict):
        """Re-colocar orden después de ejecución"""
        
        if filled_order['type'] == 'buy':
            # Fue buy → colocar sell 1% arriba
            sell_price = filled_order['price'] * 1.01
            order = self.place_order('sell', filled_order['amount'], sell_price)
            
            if order:
                self.active_orders.append(order)
                self.log(f"  🔄 Re-colocada SELL @ ${sell_price:.2f}")
        
        elif filled_order['type'] == 'sell':
            # Fue sell → colocar buy 1% abajo
            buy_price = filled_order['price'] * 0.99
            order = self.place_order('buy', filled_order['amount'], buy_price)
            
            if order:
                self.active_orders.append(order)
                self.log(f"  🔄 Re-colocada BUY @ ${buy_price:.2f}")
    
    def show_status(self):
        """Mostrar status actual"""
        
        current_price = self.get_current_price()
        
        self.log("\n╔═══════════════════════════════════════════════════════╗")
        self.log("║  📊 STATUS DEL GRID")
        self.log("╚═══════════════════════════════════════════════════════╝")
        
        if self.dry_run:
            total_value = self.paper_balance_usdt + (self.paper_balance_coin * current_price)
            self.log(f"💵 USDT Virtual:    ${self.paper_balance_usdt:.2f}")
            self.log(f"🪙 {self.coin} Virtual: {self.paper_balance_coin}")
            self.log(f"📊 Total Value:    ${total_value:.2f}")
        else:
            self.log(f"💵 USDT Real:      ${self.get_balance('USDT'):.2f}")
            self.log(f"🪙 {self.coin} Real:       {self.get_balance(self.coin)}")
        
        self.log(f"\n📈 Trades:         {self.trades_count}")
        self.log(f"💰 Profit Total:   ${self.total_profit:.2f}")
        self.log(f"📊 Precio Actual:  ${current_price}")
        self.log(f"📋 Órdenes Activas: {len(self.active_orders)}")
        self.log("╔═══════════════════════════════════════════════════════╗")
    
    def run(self, duration_hours: int = 24, check_interval_min: int = 2):
        """Ejecutar bot por X horas"""
        
        self.log(f"🚀 Iniciando Grid Trading Bot ({'PAPER' if self.dry_run else 'LIVE'}) por {duration_hours} horas...")
        
        # Setup inicial
        if not self.setup_grid():
            self.log("❌ Error en setup inicial")
            return False
        
        # Loop principal
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        
        while datetime.now() < end_time:
            try:
                # Monitorear y rebalancear
                filled = self.monitor_and_rebalance()
                
                if filled > 0:
                    self.log(f"💰 Profit acumulado: ${self.total_profit:.2f}")
                
                # Mostrar status cada hora
                if int((datetime.now() - start_time).total_seconds() / 3600) > int((datetime.now() - start_time).total_seconds() / 3600 - 1/60):
                    self.show_status()
                
                # Wait next check
                time.sleep(check_interval_min * 60)
                
            except KeyboardInterrupt:
                self.log("\n⌨️ Interrumpido por usuario")
                break
            except Exception as e:
                self.log(f"❌ Error: {e}")
                time.sleep(60)
        
        # Final
        self.show_status()
        self.log("\n⏰ Tiempo completado")
        
        return True

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Perrobotillo Grid Trading Bot v2")
    parser.add_argument("--coin", type=str, default="BNB", help="Moneda para grid trading")
    parser.add_argument("--hours", type=int, default=1, help="Duración en horas")
    parser.add_argument("--interval", type=int, default=2, help="Intervalo de chequeo en minutos")
    parser.add_argument("--dry-run", action="store_true", help="Modo Paper Trading (default)")
    parser.add_argument("--live", action="store_true", help="Modo Live Trading (dinero real)")
    
    args = parser.parse_args()
    
    coin = args.coin.upper()
    dry_run = not args.live  # Default es paper trading
    
    if coin not in DEFAULT_GRID_CONFIG:
        print(f"❌ Moneda no soportada: {coin}")
        print(f"Disponibles: {', '.join(DEFAULT_GRID_CONFIG.keys())}")
        sys.exit(1)
    
    config = DEFAULT_GRID_CONFIG[coin]
    
    if not config.get('enabled', False):
        print(f"⚠️ Grid trading no habilitado para {coin}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"🐕 GRID TRADING BOT - {'PAPER TRADING' if dry_run else 'LIVE TRADING'}")
    print(f"{'='*60}")
    print(f"Moneda: {coin}")
    print(f"Duración: {args.hours} horas")
    print(f"Intervalo: {args.interval} minutos")
    print(f"Modo: {'🧪 Paper Trading (sin riesgo)' if dry_run else '💰 Live Trading (dinero real)'}")
    print(f"{'='*60}\n")
    
    bot = GridTradingBot(coin, config, dry_run=dry_run)
    bot.run(duration_hours=args.hours, check_interval_min=args.interval)

if __name__ == "__main__":
    main()
