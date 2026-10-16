#!/usr/bin/env python3
"""
🔄 Circuit Breaker Status Check
Solo verifica si hay circuit breaker activo - SIN countdown
El dashboard lee este archivo on-demand cuando carga
"""

import json
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
CRYPTO_BOTS = WORKSPACE / "crypto-bots"

def update_circuit_breaker_status():
    """Verificar estado del Circuit Breaker - Solo status básico"""
    
    pause_file = CRYPTO_BOTS / "global-pause-flag.json"
    dashboard_file = CRYPTO_BOTS / "dashboard-circuit-breaker-status.json"
    
    # Verificar si hay pause global
    if not pause_file.exists():
        # No hay circuit breaker activo
        status = {
            "circuitBreakerActive": False,
            "status": "RESUMED",
            "message": "Trading Normal - Circuit Breaker OFF",
            "lastChecked": datetime.now().isoformat()
        }
    else:
        with open(pause_file) as f:
            pause_data = json.load(f)
        
        pause_until_str = pause_data.get('pause_until')
        
        if not pause_until_str:
            status = {
                "circuitBreakerActive": False,
                "status": "RESUMED",
                "message": "Trading Normal",
                "lastChecked": datetime.now().isoformat()
            }
        else:
            # Parsear fecha de pausa
            try:
                pause_until = datetime.strptime(pause_until_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pause_until = datetime.fromisoformat(pause_until_str.replace('Z', '+00:00'))
            
            now = datetime.now()
            time_remaining = pause_until - now
            
            if time_remaining.total_seconds() <= 0:
                # La pausa ya terminó
                status = {
                    "circuitBreakerActive": False,
                    "status": "RESUMED",
                    "message": "Circuit Breaker OFF - Trading Reanudado",
                    "resumedAt": now.isoformat(),
                    "lastChecked": now.isoformat()
                }
            else:
                # Circuit breaker activo - datos básicos para el dashboard
                status = {
                    "circuitBreakerActive": True,
                    "status": "GLOBAL_PAUSE",
                    "triggeredBy": pause_data.get('triggered_by', 'unknown'),
                    "activatedAt": pause_data.get('activated_at', 'unknown'),
                    "pauseUntil": pause_until_str,
                    "losses24h": pause_data.get('losses_24h', 0),
                    "message": f"🔴 Circuit Breaker ON",
                    "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
                    "blockedOperations": ["New Entries", "DCA Operations"],
                    "lastChecked": now.isoformat()
                }
    
    # Guardar estado actualizado
    with open(dashboard_file, 'w') as f:
        json.dump(status, f, indent=2)
    
    return status

def print_dashboard_summary(status):
    """Imprimir resumen simple"""
    
    if status.get('circuitBreakerActive'):
        print(f"🔴 CIRCUIT BREAKER: ACTIVO - {status['message']}")
    else:
        print(f"🟢 CIRCUIT BREAKER: INACTIVO - {status.get('message', 'Trading Normal')}")

if __name__ == "__main__":
    status = update_circuit_breaker_status()
    print_dashboard_summary(status)
