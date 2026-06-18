#!/usr/bin/env python3
"""
🐕 PERROBOTILLO - BNB FEE DETECTOR
Detecta si el usuario tiene BNB para pagar fees con 25% de descuento
Monitorea balance y calcula ahorro potencial

Autor: Perrobotillo Trading Bot
"""

import requests
import hmac
import hashlib
import time
import json
from pathlib import Path
from datetime import datetime

# Configuración
WORKSPACE = Path("/home/overgon/.openclaw/workspace")
SECRETS_FILE = WORKSPACE.parent / "secrets" / "binance.env"
OUTPUT_FILE = WORKSPACE / "crypto-bots" / "bnb-fee-status.json"
LOG_FILE = WORKSPACE / "logs" / "bnb-fee-detector.log"

# Mínimo recomendado de BNB (cubre ~400 trades)
MIN_BNB_RECOMMENDED = 0.1

class BNBFeeDetector:
    def __init__(self):
        self.api_key = None
        self.api_secret = None
        self.base_url = 'https://api.binance.com'
        self.load_credentials()
    
    def load_credentials(self):
        """Carga API keys desde el archivo de secretos"""
        if not SECRETS_FILE.exists():
            raise FileNotFoundError(f"Secrets file not found: {SECRETS_FILE}")
        
        with open(SECRETS_FILE) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    if key == 'BINANCE_API_KEY':
                        self.api_key = value
                    elif key == 'BINANCE_API_SECRET':
                        self.api_secret = value
        
        if not self.api_key or not self.api_secret:
            raise ValueError("API keys not found in secrets file")
    
    def get_signature(self, query_string):
        """Genera firma HMAC para la request"""
        return hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def get_account_info(self):
        """Obtiene información completa de la cuenta"""
        timestamp = int(time.time() * 1000)
        query = 'timestamp=' + str(timestamp)
        signature = self.get_signature(query)
        
        headers = {'X-MBX-APIKEY': self.api_key}
        url = self.base_url + '/api/v3/account?' + query + '&signature=' + signature
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'API Error {response.status_code}', 'details': response.text[:200]}
        except Exception as e:
            return {'error': 'Connection error', 'details': str(e)}
    
    def get_bnb_price(self):
        """Obtiene precio actual de BNB en USDT"""
        try:
            response = requests.get(
                f'{self.base_url}/api/v3/ticker/price?symbol=BNBUSDT',
                timeout=5
            )
            if response.status_code == 200:
                return float(response.json()['price'])
        except:
            pass
        return 70.0  # Precio fallback
    
    def check_bnb_status(self):
        """Verifica el status de BNB para fee discount"""
        account = self.get_account_info()
        
        if 'error' in account:
            return {
                'success': False,
                'error': account['error'],
                'details': account.get('details', ''),
                'timestamp': time.time()
            }
        
        # Buscar balance de BNB
        bnb_free = 0.0
        bnb_locked = 0.0
        
        for asset in account.get('balances', []):
            if asset['asset'] == 'BNB':
                bnb_free = float(asset['free'])
                bnb_locked = float(asset['locked'])
                break
        
        total_bnb = bnb_free + bnb_locked
        bnb_price = self.get_bnb_price()
        bnb_value_usdt = total_bnb * bnb_price
        
        # Calcular métricas
        has_enough = total_bnb >= MIN_BNB_RECOMMENDED
        discount_active = has_enough  # Asumimos que si tiene BNB, activó el discount
        
        # Fee rates
        base_fee_rate = 0.001  # 0.1%
        discounted_fee_rate = 0.00075  # 0.075% con BNB
        effective_fee_rate = discounted_fee_rate if discount_active else base_fee_rate
        
        # Trades cubiertos
        avg_fee_per_trade_usdt = 0.15  # Fee promedio por trade
        trades_coverable = int(bnb_value_usdt / avg_fee_per_trade_usdt) if has_enough else 0
        
        # Estimado de ahorro mensual (50 trades/mes)
        estimated_monthly_trades = 50
        monthly_savings = 0.0
        if discount_active:
            monthly_volume = estimated_monthly_trades * 100  # $100 USDT por trade promedio
            monthly_savings = monthly_volume * (base_fee_rate - discounted_fee_rate)
        
        result = {
            'success': True,
            'timestamp': time.time(),
            'timestamp_iso': datetime.now().isoformat(),
            
            # Balances
            'bnb_free': bnb_free,
            'bnb_locked': bnb_locked,
            'bnb_total': total_bnb,
            'bnb_price_usdt': bnb_price,
            'bnb_value_usdt': bnb_value_usdt,
            
            # Status
            'has_enough_bnb': has_enough,
            'min_recommended': MIN_BNB_RECOMMENDED,
            'discount_likely_active': discount_active,
            
            # Fees
            'base_fee_rate': base_fee_rate,
            'discounted_fee_rate': discounted_fee_rate,
            'effective_fee_rate': effective_fee_rate,
            'discount_percent': 25 if discount_active else 0,
            
            # Métricas
            'trades_coverable': trades_coverable,
            'estimated_monthly_savings_usdt': monthly_savings,
            'estimated_annual_savings_usdt': monthly_savings * 12,
            
            # Recomendación
            'recommendation': self.get_recommendation(total_bnb, bnb_price, has_enough),
            
            # Raw data (opcional, para debug)
            'account_balances_count': len(account.get('balances', []))
        }
        
        return result
    
    def get_recommendation(self, bnb_total, bnb_price, has_enough):
        """Genera recomendación basada en el status actual"""
        if has_enough:
            return {
                'action': 'MAINTAIN',
                'message': '✅ Tienes suficiente BNB para fee discount',
                'bnb_needed': 0,
                'cost_usdt': 0
            }
        else:
            bnb_needed = MIN_BNB_RECOMMENDED - bnb_total
            cost_usdt = bnb_needed * bnb_price
            
            return {
                'action': 'BUY_BNB',
                'message': f'⚠️  BNB insuficiente. Necesitas {bnb_needed:.4f} BNB más (~${cost_usdt:.2f} USDT)',
                'bnb_needed': bnb_needed,
                'cost_usdt': cost_usdt,
                'payback_months': 2-3 if cost_usdt > 0 else 0
            }
    
    def save_status(self, status):
        """Guarda el status en archivo JSON"""
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(status, f, indent=2)
        
        return OUTPUT_FILE
    
    def log_status(self, status):
        """Loguea el status"""
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(LOG_FILE, 'a') as f:
            f.write(f"\n[{timestamp}] BNB Fee Detector Check\n")
            f.write(f"  BNB Total: {status.get('bnb_total', 0):.8f}\n")
            f.write(f"  Value: ${status.get('bnb_value_usdt', 0):.2f} USDT\n")
            f.write(f"  Discount Active: {status.get('discount_likely_active', False)}\n")
            f.write(f"  Trades Coverable: {status.get('trades_coverable', 0)}\n")
            
            rec = status.get('recommendation', {})
            f.write(f"  Recommendation: {rec.get('action', 'UNKNOWN')} - {rec.get('message', '')}\n")


def main():
    """Función principal"""
    print('╔═══════════════════════════════════════════════════════╗')
    print('║  🐕 PERROBOTILLO - BNB FEE DETECTOR                   ║')
    print('╚═══════════════════════════════════════════════════════╝')
    print()
    
    detector = BNBFeeDetector()
    status = detector.check_bnb_status()
    
    if status.get('success'):
        # Imprimir resultados
        print('💰 BALANCE DE BNB:')
        print(f"  Disponible: {status['bnb_free']:8.8f} BNB")
        print(f"  En órdenes: {status['bnb_locked']:8.8f} BNB")
        print(f"  Total:      {status['bnb_total']:8.8f} BNB")
        print(f"  Precio:     ${status['bnb_price_usdt']:.2f} USDT")
        print(f"  Valor:      ${status['bnb_value_usdt']:.2f} USDT")
        print()
        
        print('🎫 FEE DISCOUNT STATUS:')
        if status['discount_likely_active']:
            print(f"  ✅ ACTIVO - 25% descuento en fees")
            print(f"  Fee efectivo: {status['effective_fee_rate']*100:.3f}% (normal: {status['base_fee_rate']*100:.3f}%)")
        else:
            print(f"  ❌ INACTIVO - Sin descuento")
            print(f"  Fee actual: {status['effective_fee_rate']*100:.3f}%")
            print(f"  Con BNB sería: {status['discounted_fee_rate']*100:.3f}%")
        print()
        
        print('📊 MÉTRICAS:')
        print(f"  Trades cubiertos: ~{status['trades_coverable']}")
        print(f"  Ahorro mensual est.: ${status['estimated_monthly_savings_usdt']:.2f} USDT")
        print(f"  Ahorro anual est.:   ${status['estimated_annual_savings_usdt']:.2f} USDT")
        print()
        
        print('💡 RECOMENDACIÓN:')
        rec = status['recommendation']
        print(f"  Acción: {rec['action']}")
        print(f"  {rec['message']}")
        if rec['action'] == 'BUY_BNB':
            print(f"  Costo estimado: ${rec['cost_usdt']:.2f} USDT")
            print(f"  Payback: ~{rec['payback_months']} meses")
        print()
        
        # Guardar status
        output_file = detector.save_status(status)
        print(f'✅ Status guardado en: {output_file}')
        
        # Log
        detector.log_status(status)
        
    else:
        print(f"❌ ERROR: {status.get('error', 'Unknown error')}")
        if status.get('details'):
            print(f"   Detalles: {status['details']}")
    
    print()
    print('═══════════════════════════════════════════════════════')
    
    return status


if __name__ == '__main__':
    main()
