#!/usr/bin/env python3
"""
🐕 Slot Health Manager - Unificado
Reemplaza: slot-healbot.py + auto-reset-closed-slots.sh

Propósito: Verificar y reparar el estado de los slots cada 10 minutos.

REGLAS DE SEGURIDAD:
- NUNCA limpiar slots con orderId + entryPrice (posición activa)
- Si status es READY pero tiene posición → corregir a ACTIVE
- Solo limpiar slots CLOSED_* o AVAILABLE
- Estados CLOSED_TRAILING, CLOSED_TP1/2/3, CLOSED_SL → READY limpio

Estados válidos:
- READY: Slot disponible (sin posición)
- ACTIVE: Posición abierta (IN TRADE)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Configuración
CRYPTO_BOTS = Path("/home/overgon/.openclaw/workspace/crypto-bots")
COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]
TELEGRAM_CHAT_ID = "7543955537"  # Rull Ox

def load_trade_state(coin):
    """Carga el estado de trading de una moneda."""
    path = CRYPTO_BOTS / f"{coin}-trade-state.json"
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)

def save_trade_state(coin, data):
    """Guarda el estado de trading de una moneda."""
    path = CRYPTO_BOTS / f"{coin}-trade-state.json"
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def clean_slot_data(slot):
    """Limpia los datos de posición de un slot."""
    slot["orderId"] = None
    slot["entryPrice"] = None
    slot["quantity"] = None
    slot["usdtSpent"] = None
    slot["stopLoss"] = None
    slot["tp1"] = None
    slot["tp2"] = None
    slot["tp3"] = None
    slot["tp1Done"] = False
    slot["tp2Done"] = False
    slot["tp3Done"] = False
    slot["timestamp"] = None
    slot["feeBuy"] = None
    slot["totalCost"] = None
    slot["highestPrice"] = None
    slot["trailingStop"] = None
    
    # Limpiar campos de cierre si existen
    for field in ["closedAt", "closeType", "exitPrice", "exitReason", "exitTimestamp", "pnlUSDT"]:
        if field in slot:
            del slot[field]

def has_active_position(slot):
    """Verifica si un slot tiene una posición activa basada en campos de cierre."""
    status = slot.get("status", "UNKNOWN")
    # Estado cerrado explícito: no hay posición activa
    if status.startswith("CLOSED_") or status == "READY":
        return False

    order_id = slot.get("orderId")
    entry_price = slot.get("entryPrice")

    # Sin orderId o entryPrice = no hay posición
    if order_id is None or entry_price is None:
        return False

    # Verificar si tiene información de cierre
    closed_fields = ['closedAt', 'closeType', 'exitPrice', 'exitReason', 'exitTimestamp']
    has_close_info = any(slot.get(f) for f in closed_fields if f in slot and slot.get(f) is not None)

    # Si tiene info de cierre, la posición ya no existe
    if has_close_info:
        return False

    # Tiene orderId, entryPrice, y NO tiene info de cierre = posición activa
    return True

def repair_slot(slot, coin, slot_id):
    """Repara un slot con estado inválido o inconsistente."""
    repairs = []
    
    current_status = slot.get("status", "UNKNOWN")
    has_position = has_active_position(slot)
    tp3_done = slot.get("tp3Done", False)
    
    # Caso -1: Slot ACTIVE pero sin posición abierta → limpiar a READY (zombi sin trade)
    if current_status == "ACTIVE" and slot.get("entryPrice") is None:
        repairs.append(f"ACTIVE sin entryPrice → READY")
        slot["status"] = "READY"
        slot["lastUpdate"] = __import__("datetime").datetime.now().isoformat()
        print(f"🔧 {coin} slot {slot_id}: ACTIVE zombie → READY")
        continue

    # Caso 0: Estados CLOSED_* o CLOSED sin guion bajo → trade terminado, reconvertir a READY limpio
    # Esto incluye: CLOSED_TRAILING, CLOSED_TP1, CLOSED_TP2, CLOSED_TP3, CLOSED_SL, y CLOSED sin suffix
    if current_status.startswith("CLOSED_") or current_status == "CLOSED":
        repairs.append(f"Estado '{current_status}' → 'READY'")
        slot["status"] = "READY"
        # Limpiar flags de TP al cerrar
        for key in ["tp1Done", "tp2Done", "tp3Done"]:
            if key in slot:
                slot[key] = False
        clean_slot_data(slot)
        return slot, repairs

    # Caso 0b: Slots pausados/atorados → reparar a READY
    if current_status in ("PAUSED", "PAUSE"):
        repairs.append(f"Estado '{current_status}' → 'READY'")
        slot["status"] = "READY"
        clean_slot_data(slot)
        return slot, repairs
    
    # Caso 1: Status ACTIVE con TP3 completado → trade terminado, cerrar
    if current_status == "ACTIVE" and has_position and tp3_done:
        repairs.append(f"TP3 completado - cerrando trade")
        slot["status"] = "CLOSED"
        slot["exitPrice"] = slot.get("tp3")
        slot["exitReason"] = "TP3_COMPLETED"
        slot["closedAt"] = datetime.now().isoformat()
        return slot, repairs
    
    # ⚠️ REGLA DE ORO: NUNCA tocar slots ACTIVE con posición REAL (excepto TP3 completado)
    if current_status == "ACTIVE" and has_position:
        return None, []  # Todo bien, no hacer nada
    
    # Caso 2: Estado AVAILABLE → convertir a READY limpio
    if current_status == "AVAILABLE":
        repairs.append(f"Estado 'AVAILABLE' → 'READY'")
        slot["status"] = "READY"
        clean_slot_data(slot)
        return slot, repairs
    
    # Caso 3: Status READY pero tenía posición que YA NO EXISTE → LIMPIAR
    if current_status == "READY" and has_position:
        repairs.append(f"READY con posición cerrada → limpiando datos")
        clean_slot_data(slot)
        return slot, repairs
    
    # Caso 4: Status READY sin posición → está bien
    if current_status == "READY" and not has_position:
        return None, []
    
    # Caso 5: Status ACTIVE sin posición → inconsistencia grave
    if current_status == "ACTIVE" and not has_position:
        repairs.append(f"ACTIVE sin posición - marcando como READY")
        clean_slot_data(slot)
        return slot, repairs
    
    return None, repairs

def check_slot_consistency(slot, coin, slot_id):
    """Verifica inconsistencias menores para logging."""
    issues = []
    
    status = slot.get("status", "UNKNOWN")
    has_position = has_active_position(slot)
    
    # ACTIVE sin orderId/entryPrice
    if status == "ACTIVE" and not has_position:
        issues.append("ACTIVE sin posición (orderId/entryPrice)")
    
    # READY con posición ya fue reparado arriba, pero lo registramos
    if status == "READY" and has_position:
        issues.append("READY con posición activa (ya corregido)")
    
    return issues

def send_telegram_notification(message):
    """Envía notificación por Telegram."""
    try:
        import subprocess
        
        escaped_message = message.replace("'", "'\\''").replace('"', '\\"')
        
        cmd = f"""
curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \\
  -d chat_id="{TELEGRAM_CHAT_ID}" \\
  -d text='{escaped_message}' \\
  -d parse_mode="HTML"
"""
        env = os.environ.copy()
        result = subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return True
        else:
            print(f"Error enviando Telegram: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error enviando Telegram: {e}")
        return False

def main():
    """Función principal del health manager."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] 🐕 Slot Health Manager iniciado")
    print(f"🔒 Modo SEGURO: No se borrarán posiciones activas")
    print(f"📋 Reemplaza: slot-healbot.py + auto-reset-closed-slots.sh")
    
    total_slots = 0
    repaired_slots = []
    inconsistent_slots = []
    
    for coin in COINS:
        state = load_trade_state(coin)
        if not state:
            print(f"⚠️ {coin}: No se encontró archivo de estado")
            continue
        
        slots = state.get("slots", [])
        coin_changed = False
        
        for slot in slots:
            total_slots += 1
            slot_id = slot.get("slotId", "?")
            has_position = has_active_position(slot)
            
            # Debug: mostrar estado actual
            position_info = f"(posición: {slot.get('orderId', 'N/A')})" if has_position else "(sin posición)"
            print(f"  {coin} Slot {slot_id}: {slot.get('status', 'UNKNOWN')} {position_info}")
            
            # Verificar y reparar
            repaired_slot, repairs = repair_slot(slot, coin, slot_id)
            
            if repaired_slot:
                slot.update(repaired_slot)
                coin_changed = True
                repaired_slots.append({
                    "coin": coin,
                    "slot": slot_id,
                    "repairs": repairs
                })
                print(f"  🔧 {coin} Slot {slot_id}: {', '.join(repairs)}")
            
            # Verificar inconsistencias menores
            issues = check_slot_consistency(slot, coin, slot_id)
            if issues:
                inconsistent_slots.append({
                    "coin": coin,
                    "slot": slot_id,
                    "issues": issues
                })
        
        # Guardar cambios si hubo modificaciones
        if coin_changed:
            save_trade_state(coin, state)
            print(f"  💾 {coin}: Estado guardado")
    
    # Resumen
    print(f"\n📊 Resumen: {total_slots} slots verificados")
    
    if repaired_slots:
        print(f"✅ {len(repaired_slots)} slots reparados")
        
        # Notificar por Telegram SOLO si hubo reparaciones reales
        notification = build_telegram_notification(repaired_slots, inconsistent_slots)
        send_telegram_notification(notification)
        print("📱 Notificación enviada a Telegram")
    else:
        print("✅ Todos los slots están en estado válido (sin notificación)")
    
    if inconsistent_slots:
        print(f"⚠️ {len(inconsistent_slots)} slots con inconsistencias")
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🐕 Slot Health Manager completado")

def build_telegram_notification(repaired_slots, inconsistent_slots):
    """Construye mensaje compacto para Telegram."""
    lines = ["🐕 **Slot Health Manager**", ""]

    if repaired_slots:
        lines.append("🔧 **Reparaciones:**")
        for repair in repaired_slots:
            lines.append(f"├ {repair['coin']} Slot {repair['slot']}")
            for r in repair['repairs']:
                lines.append(f"│  • {r}")
        lines.append("")

    if inconsistent_slots:
        lines.append("⚠️ **Inconsistencias:**")
        for inc in inconsistent_slots:
            lines.append(f"├ {inc['coin']} Slot {inc['slot']}")
            for i in inc['issues']:
                lines.append(f"│  • {i}")
        lines.append("")

    lines.append(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 🐕")

    return "\n".join(lines)

if __name__ == "__main__":
    main()
