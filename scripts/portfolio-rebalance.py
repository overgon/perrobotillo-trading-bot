#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - PORTFOLIO REBALANCING BOT
# ════════════════════════════════════════════════════════
# Rebalancea automáticamente el portfolio a targets definidos
# Estrategia: "Vender caro, comprar barato" sistemáticamente
# ════════════════════════════════════════════════════════

import ccxt
import json
import sys
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List
import time

# ════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
SECRETS = Path("/home/overgon/.openclaw/secrets")
LOGS_DIR = WORKSPACE / "logs"
CONFIG_DIR = WORKSPACE / "config"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'portfolio-rebalance.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════
# TARGETS DEL PORTFOLIO
# ════════════════════════════════════════════════════════

# Configuración por defecto (editable en config/portfolio_targets.json)
DEFAULT_TARGETS = {
    "BTC": 20.0,  # 20% del portfolio
    "ETH": 20.0,  # 20% del portfolio
    "BNB": 20.0,  # 20% del portfolio
    "SOL": 20.0,  # 20% del portfolio
    "XRP": 20.0,  # 20% del portfolio
}

# Thresholds de rebalanceo
REBALANCE_THRESHOLD_PERCENT = 5.0  # Rebalancear si una moneda se desvía >5% del target
MIN_TRADE_USDT = 10.0  # Trade mínimo $10 USDT

# ════════════════════════════════════════════════════════
# PORTFOLIO REBALANCER CLASS
# ════════════════════════════════════════════════════════

class PortfolioRebalancer:
    """
    Rebalancea el portfolio automáticamente a los targets definidos
    
    Proceso:
    1. Calcular valor actual del portfolio por moneda
    2. Comparar con targets
    3. Si desviación > threshold → rebalancear
    4. Vender monedas sobre-asignadas
    5. Comprar monedas bajo-asignadas
    """
    
    def __init__(self, config_file: str = None):
        """
        config_file: Archivo JSON con configuración custom
        """
        
        # Cargar configuración
        self.config_file = config_file or CONFIG_DIR / "portfolio_targets.json"
        self.targets = self._load_config()
        
        # Inicializar Binance
        self.exchange = self._init_binance()
        
        logger.info("="*60)
        logger.info("🐕 Perrobotillo Portfolio Rebalancer")
        logger.info("="*60)
        logger.info(f"Targets cargados: {self.targets}")
        logger.info(f"Threshold: {REBALANCE_THRESHOLD_PERCENT}%")
        logger.info(f"Min trade: ${MIN_TRADE_USDT} USDT")
        logger.info("="*60)
    
    def _load_config(self) -> Dict:
        """Cargar configuración desde archivo o usar defaults"""
        
        if Path(self.config_file).exists():
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                logger.info(f"📄 Configuración cargada desde: {self.config_file}")
                return config['targets']
        else:
            logger.info("📄 Usando configuración por defecto")
            # Guardar defaults como archivo
            self._save_config(DEFAULT_TARGETS)
            return DEFAULT_TARGETS.copy()
    
    def _save_config(self, targets: Dict):
        """Guardar configuración en archivo"""
        
        config = {
            'targets': targets,
            'rebalance_threshold_percent': REBALANCE_THRESHOLD_PERCENT,
            'min_trade_usdt': MIN_TRADE_USDT,
            'created_at': datetime.now().isoformat()
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"💾 Configuración guardada en: {self.config_file}")
    
    def _init_binance(self):
        """Inicializar conexión con Binance"""
        
        logger.info("🔌 Conectando a Binance...")
        
        # Cargar API keys
        secrets_file = SECRETS / "binance.env"
        
        if not secrets_file.exists():
            raise FileNotFoundError(f"No se encontró {secrets_file}")
        
        # Leer variables de entorno
        env_vars = {}
        with open(secrets_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        api_key = env_vars.get('BINANCE_API_KEY')
        api_secret = env_vars.get('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            raise ValueError("API keys no encontradas en binance.env")
        
        # Crear exchange
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })
        
        # Verificar conexión
        try:
            balance = exchange.fetch_balance()
            logger.info("✅ Conexión Binance exitosa")
            return exchange
        except Exception as e:
            logger.error(f"❌ Error conectando a Binance: {e}")
            raise
    
    def get_portfolio_value(self) -> Dict:
        """
        Calcular valor actual del portfolio
        
        Returns: Dict con valor por moneda y total
        """
        
        logger.info("\n📊 Calculando valor del portfolio...")
        
        # Obtener balance
        balance = self.exchange.fetch_balance()
        
        # Monedas a considerar
        coins = list(self.targets.keys())
        
        # Obtener precios actuales
        prices = {}
        for coin in coins:
            try:
                symbol = f"{coin}/USDT"
                ticker = self.exchange.fetch_ticker(symbol)
                prices[coin] = ticker['last']
                logger.info(f"   {coin}: ${prices[coin]:.4f}")
            except Exception as e:
                logger.warning(f"⚠️  No se pudo obtener precio de {coin}: {e}")
                prices[coin] = 0
        
        # Calcular valores
        portfolio = {
            'holdings': {},
            'values_usdt': {},
            'total_usdt': 0
        }
        
        for coin in coins:
            # Obtener balance de la moneda
            if coin in balance['total']:
                amount = balance['total'][coin]
            else:
                amount = 0
            
            # Calcular valor en USDT
            value_usdt = amount * prices[coin]
            
            portfolio['holdings'][coin] = amount
            portfolio['values_usdt'][coin] = value_usdt
            portfolio['total_usdt'] += value_usdt
        
        # Agregar USDT disponible
        usdt_balance = balance['total'].get('USDT', 0)
        portfolio['holdings']['USDT'] = usdt_balance
        portfolio['values_usdt']['USDT'] = usdt_balance
        portfolio['total_usdt'] += usdt_balance
        
        logger.info(f"\n💰 Valor total del portfolio: ${portfolio['total_usdt']:.2f} USDT")
        
        return portfolio
    
    def calculate_allocation(self, portfolio: Dict) -> Dict:
        """
        Calcular asignación actual vs target
        
        Returns: Dict con comparación actual vs target
        """
        
        logger.info("\n📈 Calculando asignación actual...")
        
        total = portfolio['total_usdt']
        
        if total == 0:
            logger.error("❌ Portfolio vacío, no se puede calcular asignación")
            return {}
        
        allocation = {
            'current': {},
            'target': {},
            'difference': {},
            'needs_rebalance': False
        }
        
        for coin in self.targets.keys():
            current_value = portfolio['values_usdt'].get(coin, 0)
            current_percent = (current_value / total) * 100
            target_percent = self.targets[coin]
            difference = current_percent - target_percent
            
            allocation['current'][coin] = current_percent
            allocation['target'][coin] = target_percent
            allocation['difference'][coin] = difference
            
            # Verificar si necesita rebalanceo
            if abs(difference) > REBALANCE_THRESHOLD_PERCENT:
                allocation['needs_rebalance'] = True
            
            status = "✅" if abs(difference) <= REBALANCE_THRESHOLD_PERCENT else "⚠️"
            logger.info(f"   {status} {coin}: {current_percent:.1f}% (target: {target_percent}%, diff: {difference:+.1f}%)")
        
        return allocation
    
    def generate_rebalance_orders(self, portfolio: Dict, allocation: Dict) -> List[Dict]:
        """
        Generar órdenes para rebalancear
        
        Returns: Lista de órdenes (vender/comprar)
        """
        
        logger.info("\n🔄 Generando órdenes de rebalanceo...")
        
        orders = []
        total = portfolio['total_usdt']
        
        # Separar monedas en "vender" y "comprar"
        to_sell = []
        to_buy = []
        
        for coin in self.targets.keys():
            diff = allocation['difference'][coin]
            current_value = portfolio['values_usdt'].get(coin, 0)
            
            if diff > REBALANCE_THRESHOLD_PERCENT:
                # Sobre-asignado → vender
                excess_percent = diff
                excess_value = current_value * (excess_percent / 100)
                
                if excess_value >= MIN_TRADE_USDT:
                    to_sell.append({
                        'coin': coin,
                        'excess_value': excess_value,
                        'current_amount': portfolio['holdings'][coin]
                    })
                    logger.info(f"   📉 VENDER {coin}: ${excess_value:.2f} USDT ({excess_percent:.1f}% exceso)")
            
            elif diff < -REBALANCE_THRESHOLD_PERCENT:
                # Bajo-asignado → comprar
                deficit_percent = abs(diff)
                target_value = total * (self.targets[coin] / 100)
                deficit_value = target_value - current_value
                
                if deficit_value >= MIN_TRADE_USDT:
                    to_buy.append({
                        'coin': coin,
                        'deficit_value': deficit_value,
                        'target_percent': self.targets[coin]
                    })
                    logger.info(f"   📈 COMPRAR {coin}: ${deficit_value:.2f} USDT ({deficit_percent:.1f}% déficit)")
        
        # Generar órdenes de venta
        for sell in to_sell:
            orders.append({
                'type': 'SELL',
                'coin': sell['coin'],
                'amount_usdt': sell['excess_value'],
                'amount_coin': sell['current_amount'] * (sell['excess_value'] / portfolio['values_usdt'][sell['coin']])
            })
        
        # Generar órdenes de compra
        for buy in to_buy:
            orders.append({
                'type': 'BUY',
                'coin': buy['coin'],
                'amount_usdt': buy['deficit_value']
            })
        
        logger.info(f"\n📋 Total órdenes generadas: {len(orders)}")
        
        return orders
    
    def execute_rebalance(self, dry_run: bool = True) -> Dict:
        """
        Ejecutar rebalanceo del portfolio
        
        dry_run: Si True, solo simula (paper trading)
        
        Returns: Dict con resultados
        """
        
        logger.info("\n" + "="*60)
        logger.info("🚀 INICIANDO REBALANCEO DE PORTFOLIO")
        logger.info(f"Mode: {'DRY RUN (Paper)' if dry_run else 'LIVE'}")
        logger.info("="*60)
        
        # 1. Obtener valor del portfolio
        portfolio = self.get_portfolio_value()
        
        # 2. Calcular asignación actual
        allocation = self.calculate_allocation(portfolio)
        
        if not allocation:
            logger.error("❌ Error calculando asignación")
            return {'success': False, 'reason': 'allocation_error'}
        
        # 3. Verificar si necesita rebalanceo
        if not allocation['needs_rebalance']:
            logger.info("\n✅ Portfolio dentro de thresholds, no requiere rebalanceo")
            return {'success': True, 'rebalanced': False, 'reason': 'within_threshold'}
        
        # 4. Generar órdenes
        orders = self.generate_rebalance_orders(portfolio, allocation)
        
        if not orders:
            logger.info("\n⚠️  No hay órdenes ejecutables (debajo del mínimo)")
            return {'success': True, 'rebalanced': False, 'reason': 'no_orders'}
        
        # 5. Ejecutar órdenes
        results = {
            'orders_executed': 0,
            'orders_failed': 0,
            'total_volume_usdt': 0,
            'details': []
        }
        
        logger.info("\n💼 Ejecutando órdenes...")
        
        for i, order in enumerate(orders, 1):
            logger.info('\n[{}/{}] Orden {} {}'.format(i, len(orders), order['type'], order['coin']))
            
            try:
                if order['type'] == 'SELL':
                    # Vender moneda por USDT
                    symbol = f"{order['coin']}/USDT"
                    amount = order['amount_coin']
                    
                    if dry_run:
                        logger.info(f"   🧪 DRY RUN: Vender {amount:.6f} {order['coin']} @ market")
                        logger.info(f"   💰 Valor estimado: ${order['amount_usdt']:.2f} USDT")
                    else:
                        # Ejecutar orden real
                        order_result = self.exchange.create_market_sell_order(symbol, amount)
                        logger.info(f"   ✅ Vendid{amount:.6f} {order['coin']} @ {order_result['average']:.4f}")
                        logger.info(f"   💰 Total: ${order_result['cost']:.2f} USDT")
                    
                    results['orders_executed'] += 1
                    results['total_volume_usdt'] += order['amount_usdt']
                    
                elif order['type'] == 'BUY':
                    # Comprar moneda con USDT
                    symbol = f"{order['coin']}/USDT"
                    amount_usdt = order['amount_usdt']
                    
                    # Obtener precio actual
                    ticker = self.exchange.fetch_ticker(symbol)
                    price = ticker['last']
                    amount_coin = amount_usdt / price
                    
                    if dry_run:
                        logger.info(f"   🧪 DRY RUN: Comprar {amount_coin:.6f} {order['coin']} @ ${price:.4f}")
                        logger.info(f"   💰 Costo estimado: ${amount_usdt:.2f} USDT")
                    else:
                        # Ejecutar orden real
                        order_result = self.exchange.create_market_buy_order(symbol, amount_usdt)
                        logger.info(f"   ✅ Comprado {order_result['amount']:.6f} {order['coin']} @ {order_result['average']:.4f}")
                        logger.info(f"   💰 Total: ${order_result['cost']:.2f} USDT")
                    
                    results['orders_executed'] += 1
                    results['total_volume_usdt'] += amount_usdt
                
                results['details'].append({
                    'order': order,
                    'status': 'executed'
                })
                
                # Pequeña pausa entre órdenes
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"   ❌ Error ejecutando orden: {e}")
                results['orders_failed'] += 1
                results['details'].append({
                    'order': order,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # 6. Resumen final
        logger.info("\n" + "="*60)
        logger.info("🏆 RESUMEN DEL REBALANCEO")
        logger.info("="*60)
        logger.info(f"Órdenes ejecutadas: {results['orders_executed']}")
        logger.info(f"Órdenes fallidas: {results['orders_failed']}")
        logger.info(f"Volumen total: ${results['total_volume_usdt']:.2f} USDT")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        logger.info("="*60)
        
        results['success'] = results['orders_failed'] == 0
        results['rebalanced'] = results['orders_executed'] > 0
        results['timestamp'] = datetime.now().isoformat()
        
        # Guardar log
        self._save_rebalance_log(results)
        
        return results
    
    def _save_rebalance_log(self, results: Dict):
        """Guardar resultados en log JSON"""
        
        log_file = LOGS_DIR / "portfolio-rebalance-history.json"
        
        history = []
        if log_file.exists():
            with open(log_file, 'r') as f:
                history = json.load(f)
        
        history.append(results)
        
        # Mantener últimos 50 rebalanceos
        history = history[-50:]
        
        with open(log_file, 'w') as f:
            json.dump(history, f, indent=2)
        
        logger.info(f"📝 Log guardado en: {log_file}")


# ════════════════════════════════════════════════════════
# FUNCIONES DE UTILIDAD
# ════════════════════════════════════════════════════════

def show_portfolio_status():
    """Mostrar status actual del portfolio sin ejecutar trades"""
    
    print("\n" + "="*60)
    print("🐕 Perrobotillo Portfolio Status")
    print("="*60)
    
    rebalancer = PortfolioRebalancer()
    portfolio = rebalancer.get_portfolio_value()
    allocation = rebalancer.calculate_allocation(portfolio)
    
    print("\n📊 ASIGNACIÓN ACTUAL:")
    print("-"*60)
    print(f"{'Moneda':<10} | {'Actual':<10} | {'Target':<10} | {'Diff':<10} | {'Status'}")
    print("-"*60)
    
    for coin in rebalancer.targets.keys():
        current = allocation['current'].get(coin, 0)
        target = allocation['target'].get(coin, 0)
        diff = allocation['difference'].get(coin, 0)
        status = "✅" if abs(diff) <= REBALANCE_THRESHOLD_PERCENT else "⚠️"
        
        print(f"{coin:<10} | {current:>8.1f}% | {target:>8.1f}% | {diff:>+8.1f}% | {status}")
    
    print("-"*60)
    print(f"{'TOTAL':<10} | {portfolio['total_usdt']:>10.2f} USDT")
    print("="*60)
    
    needs_rebalance = allocation.get('needs_rebalance', False)
    
    if needs_rebalance:
        print("\n⚠️  Portfolio FUERA de threshold, requiere rebalanceo")
        print("   Ejecutá: python3 portfolio-rebalance.py --rebalance")
    else:
        print("\n✅ Portfolio dentro de thresholds")
    
    print("="*60 + "\n")


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Portfolio Rebalancing Bot')
    parser.add_argument('--status', action='store_true', help='Mostrar status del portfolio')
    parser.add_argument('--rebalance', action='store_true', help='Ejecutar rebalanceo')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Simular sin ejecutar (default)')
    parser.add_argument('--live', action='store_true', help='Ejecutar en modo LIVE (trades reales)')
    parser.add_argument('--config', type=str, help='Archivo de configuración custom')
    
    args = parser.parse_args()
    
    if args.status:
        show_portfolio_status()
        sys.exit(0)
    
    if args.rebalance:
        dry_run = not args.live
        
        rebalancer = PortfolioRebalancer(config_file=args.config)
        results = rebalancer.execute_rebalance(dry_run=dry_run)
        
        if results['success']:
            if results['rebalanced']:
                print(f"\n✅ Rebalanceo completado exitosamente")
                sys.exit(0)
            else:
                print(f"\nℹ️  No se requirió rebalanceo: {results.get('reason', '')}")
                sys.exit(0)
        else:
            print(f"\n❌ Error en rebalanceo: {results.get('reason', '')}")
            sys.exit(1)
    
    # Default: mostrar ayuda
    parser.print_help()
    print("\nEjemplos:")
    print("  python3 portfolio-rebalance.py --status")
    print("  python3 portfolio-rebalance.py --rebalance --dry-run")
    print("  python3 portfolio-rebalance.py --rebalance --live")
    print("\nPara configurar targets, editá: config/portfolio_targets.json")
