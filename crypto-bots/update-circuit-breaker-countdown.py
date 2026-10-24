#!/usr/bin/env python3
"""
🔄 Circuit Breaker Status Check
Verifica si hay circuit breaker activo y actualiza el dashboard con metadata
correcta preservando los valores originales del pause flag.

RACE CONDITION FIX (2026-10-24):
  El CB script (global-circuit-breaker.sh) dejó de escribir el dashboard en el
  path de pause-activo. Este script es la ÚNICA fuente de verdad del dashboard
  durante el pause, y lee triggered_by + triggered_at directamente del pause flag.

  activatedAt se deriva de triggered_at (epoch del pause flag), NO de la hora
  actual. Esto previene que el dashboard muestre una hora de activación que
  cambia cada 5 minutos cada vez que cron ejecuta este script.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

WORKSPACE = Path("/home/overgon/.openclaw")
CRYPTO_BOTS = WORKSPACE / "workspace" / "crypto-bots"
CST = timezone(timedelta(hours=-6))


def update_circuit_breaker_status():
    """Verificar estado del Circuit Breaker y actualizar dashboard con metadata correcta."""

    pause_file = CRYPTO_BOTS / "global-pause-flag.json"
    dashboard_file = CRYPTO_BOTS / "dashboard-circuit-breaker-status.json"

    # Verificar si hay pause global activa
    if not pause_file.exists():
        status = {
            "circuitBreakerActive": False,
            "status": "RESUMED",
            "message": "Trading Normal - Circuit Breaker OFF",
            "lastChecked": datetime.now(CST).isoformat()
        }
        _safe_write_dashboard(dashboard_file, status)
        return status

    with open(pause_file) as f:
        pause_data = json.load(f)

    pause_until_str = pause_data.get('pause_until')

    if not pause_until_str:
        status = {
            "circuitBreakerActive": False,
            "status": "RESUMED",
            "message": "Trading Normal",
            "lastChecked": datetime.now(CST).isoformat()
        }
        _safe_write_dashboard(dashboard_file, status)
        return status

    # Parsear fecha de pausa (formato string: "2026-10-24 13:05:02")
    try:
        pause_until = datetime.strptime(pause_until_str, '%Y-%m-%d %H:%M:%S')
        pause_until = pause_until.replace(tzinfo=CST)  # ✅ FIX: make timezone-aware
    except ValueError:
        try:
            pause_until = datetime.fromisoformat(pause_until_str.replace('Z', '+00:00'))
            if pause_until.tzinfo is None:
                pause_until = pause_until.replace(tzinfo=CST)
        except ValueError:
            pause_until = datetime.now(CST)

    now = datetime.now(CST)
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
        _safe_write_dashboard(dashboard_file, status)
        return status

    # ─────────────────────────────────────────────────────────────
    # Circuit breaker activo — construir dashboard con metadata correcta
    # RACE CONDITION FIX: Leemos triggered_at del pause flag, no usamos "now"
    # ─────────────────────────────────────────────────────────────

    triggered_by = pause_data.get('triggered_by', 'unknown')

    # 🔧 FIX: activatedAt derivado de triggered_at (epoch del pause flag)
    # Esto preserva la hora original del disparador a través de los ciclos de cron
    triggered_at_epoch = pause_data.get('triggered_at')
    if triggered_at_epoch:
        try:
            activated_at = datetime.fromtimestamp(
                int(triggered_at_epoch), tz=CST
            ).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            activated_at = _fallback_activated_at(dashboard_file)
    else:
        activated_at = _fallback_activated_at(dashboard_file)

    # Consolidar loss count: Rule 3 usa 'losses_1h', Rules 1/2/4 usan 'losses_24h'
    losses_count = pause_data.get('losses_24h')
    if losses_count is None:
        losses_count = pause_data.get('losses_1h', 0)

    # Extraer total_loss si está disponible (Rules 1, 2)
    total_loss = pause_data.get('total_loss', '0')

    # Extraer trades_24h si está disponible
    trades_24h = pause_data.get('trades_24h', 0)

    # Calcular tiempo restante formateado
    remaining_hours = int(time_remaining.total_seconds() // 3600)
    remaining_minutes = int((time_remaining.total_seconds() % 3600) // 60)
    time_remaining_str = f"{remaining_hours}h {remaining_minutes}m"

    # Construir mensaje específico según la rule que disparó
    messages = {
        'hourly_losses': f"🔴 CB ON - {losses_count} losses en 1h",
        'drawdown_threshold': f"🔴 CB ON - drawdown ${total_loss} USDT",
        'loss_rate': f"🔴 CB ON - {pause_data.get('loss_rate', '?')}% loss rate",
        'losses_count': f"🔴 CB ON - {losses_count} losses en 24h",
    }
    message = messages.get(triggered_by, f"🔴 Circuit Breaker ON ({triggered_by})")

    status = {
        "circuitBreakerActive": True,
        "status": "GLOBAL_PAUSE",
        "triggeredBy": triggered_by,
        "triggeredAt": activated_at,          # ← Derivado de triggered_at (epoch del pause flag)
        "activatedAt": activated_at,           # ← Mismo valor, preservado a través de cron cycles
        "pauseUntil": pause_until_str,
        "timeRemaining": time_remaining_str,
        "losses24h": losses_count,
        "totalLoss": str(total_loss),
        "trades24h": trades_24h,
        "message": message,
        "allowedOperations": ["SL Management", "TP Management", "Emergency Close"],
        "blockedOperations": ["New Entries", "DCA Operations"],
        "lastChecked": now.isoformat()
    }

    _safe_write_dashboard(dashboard_file, status)
    return status


def _fallback_activated_at(dashboard_file):
    """Leer activatedAt del dashboard existente como fallback."""
    try:
        with open(dashboard_file) as f:
            old_dashboard = json.load(f)
        return old_dashboard.get('activatedAt', 'unknown')
    except Exception:
        return 'unknown'


def _safe_write_dashboard(dashboard_file, status):
    """Escribir dashboard de forma segura con manejo de errores."""
    try:
        with open(dashboard_file, 'w') as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        print(f"⚠️ Error writing dashboard: {e}", file=__import__('sys').stderr)


def print_dashboard_summary(status):
    """Imprimir resumen simple."""
    if status.get('circuitBreakerActive'):
        print(f"🔴 CIRCUIT BREAKER: ACTIVO - {status['message']} | {status.get('timeRemaining', '?')}")
    else:
        print(f"🟢 CIRCUIT BREAKER: INACTIVO - {status.get('message', 'Trading Normal')}")


if __name__ == "__main__":
    status = update_circuit_breaker_status()
    print_dashboard_summary(status)
