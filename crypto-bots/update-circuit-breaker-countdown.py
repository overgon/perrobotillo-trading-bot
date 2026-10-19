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
                # 🐕 FIX (2026-10-18): El pause flag tiene field names inconsistentes
                # según cuál Rule disparó: Rule 3 usa 'losses_1h', Rules 1/2/4 usan
                # 'losses_24h'. También falta 'activated_at' en el pause flag.
                # Este fix mapea correctamente y preserva metadata del dashboard anterior.
                
                triggered_by = pause_data.get('triggered_by', 'unknown')
                
                # Consolidar loss count: try losses_24h, fall back to losses_1h
                losses_count = pause_data.get('losses_24h')
                if losses_count is None:
                    losses_count = pause_data.get('losses_1h', 0)
                
                # Preservar activatedAt del dashboard existente si el pause flag no lo tiene
                activated_at = pause_data.get('activated_at')
                if not activated_at:
                    try:
                        with open(dashboard_file) as f:
                            old_dashboard = json.load(f)
                        activated_at = old_dashboard.get('activatedAt', 'unknown')
                    except Exception:
                        activated_at = 'unknown'
                
                # Construir mensaje específico según la rule
                messages = {
                    'hourly_losses': f"🔴 CB ON - {losses_count} losses en 1h",
                    'drawdown_threshold': f"🔴 CB ON - drawdown > umbral",
                    'loss_rate': f"🔴 CB ON - {pause_data.get('loss_rate', '?')}% loss rate",
                    'losses_count': f"🔴 CB ON - {losses_count} losses en 24h",
                }
                message = messages.get(triggered_by, f"🔴 Circuit Breaker ON ({triggered_by})")
                
                status = {
                    "circuitBreakerActive": True,
                    "status": "GLOBAL_PAUSE",
                    "triggeredBy": triggered_by,
                    "activatedAt": activated_at,
                    "pauseUntil": pause_until_str,
                    "losses24h": losses_count,
                    "message": message,
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
