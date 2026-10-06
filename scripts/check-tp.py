#!/usr/bin/env python3
"""
TP Checker - Verifica si hay TPs que cerrar para una moneda
Uso: python3 check-tp.py COIN CURRENT_PRICE STATE_FILE LOG_FILE

Integrado con On-Chain Pre-Trade Gate (FASE 4):
  - Antes de vender, verifica smart money signals
  - Si smart money está comprando (signal=1, 3+ whales), añade warning
  - Si token audit detectó mintable, confirma venta inmediata (evitar rug pull)
"""

import json
import os
import sys
import time
import hmac
import hashlib
import urllib.parse
import urllib.request
import subprocess
from datetime import datetime, timezone

# ── On-Chain Gate Integration ────────────────────────────────────────────────
WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
ON_CHAIN_GATE = os.path.join(WORKSPACE, "ml/on_chain_pre_trade_gate.py")

def on_chain_sell_check(symbol: str) -> tuple[str, str]:
    """
    Verifica on-chain data antes de vender.
    Returns: (status, reason)
      status: "CONFIRM_SELL", "WARN_SELL", "ABORT_SELL"
    """
    if not os.path.exists(ON_CHAIN_GATE):
        return ("CONFIRM_SELL", "on-chain gate no disponible, proceeding")
    
    try:
        result = subprocess.run(
            ["python3", ON_CHAIN_GATE, symbol, "SELL"],
            capture_output=True, text=True, timeout=30,
            cwd=WORKSPACE
        )
        output = result.stdout.strip()
        
        if "BLOCK_ON_CHAIN_GATE" in output:
            # Si es BLOCK, pero estamos en SELL → confirma venta inmediata
            # (BLOCK en BUY = no comprar; BLOCK en SELL = vender Ya)
            return ("CONFIRM_SELL", f"BLOCK en BUY = vender inmediato: {output}")
        
        if "WARN_ON_CHAIN_GATE" in output:
            # Smart money selling → good timing to sell también
            return ("WARN_SELL", f"On-chain warning presente: {output}")
        
        if "ALLOW_ON_CHAIN_GATE" in output:
            # Verificar si smart money está comprando (contrario a nuestra venta)
            reason = output.split("|")[-1] if "|" in output else "ALLOW"
            if "buying" in reason.lower() or "whales" in reason.lower():
                return ("WARN_SELL", f"Smart money buying, reconsiderar venta parcial: {output}")
            return ("CONFIRM_SELL", "On-chain gate: ALLOW")
            
    except Exception as e:
        return ("CONFIRM_SELL", f"On-chain gate error: {e}, proceeding conservatively")
    
    return ("CONFIRM_SELL", "fallback: proceeding with sell")

# ── Existing imports ─────────────────────────────────────────────────────────
if len(sys.argv) < 5:
    print(f"Usage: {sys.argv[0]} COIN CURRENT_PRICE STATE_FILE LOG_FILE")
    sys.exit(1)

coin = sys.argv[1]
raw_price = sys.argv[2]
state_file = sys.argv[3]
log_file = sys.argv[4]

if raw_price is None or str(raw_price).strip() == '':
    print(f"WARNING: {coin} precio no disponible, se salta este ciclo")
    sys.exit(0)

try:
    current_price = float(raw_price)
except (ValueError, TypeError):
    print(f"ERROR: current_price inválido para {coin}: '{raw_price}'")
    sys.exit(0)

print(f"DEBUG Python: Checking {coin} at ${current_price}")

def load_binance_env():
    env_path = os.path.expanduser('~/.openclaw/secrets/binance.env')
    if not os.path.exists(env_path):
        raise RuntimeError('binance.env no encontrado')
    env = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip()
    return env

def sign_query(query_string: str, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def place_sell_order_market(symbol: str, quantity: str):
    env = load_binance_env()
    api_key = env.get('BINANCE_API_KEY')
    api_secret = env.get('BINANCE_API_SECRET')
    if not api_key or not api_secret:
        raise RuntimeError('Faltan BINANCE_API_KEY/BINANCE_API_SECRET en binance.env')

    base_url = 'https://api.binance.com'
    timestamp = int(time.time() * 1000)
    recv_window = 60000
    params = {
        'symbol': f'{symbol}USDT',
        'side': 'SELL',
        'type': 'MARKET',
        'quantity': quantity,
        'timestamp': timestamp,
        'recvWindow': recv_window,
    }
    query_string = urllib.parse.urlencode(params, doseq=True)
    signature = sign_query(query_string, api_secret)
    url = f"{base_url}/api/v3/order?{query_string}&signature={signature}"

    req = urllib.request.Request(url, headers={'X-MBX-APIKEY': api_key}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        return {'status': 'ERROR', 'msg': str(exc)}

def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

with open(state_file, 'r') as f:
    data = json.load(f)

slots_to_close = []

for slot in data.get('slots', []):
    print(f"DEBUG: Slot {slot.get('slotId')} status={slot.get('status')}")
    if slot.get('status') != 'ACTIVE':
        continue

    tp_targets = [
        ('TP1', safe_float(slot.get('tp1')), slot.get('tp1Done', False), safe_float(slot.get('tp1Pct'), 0.35)),
        ('TP2', safe_float(slot.get('tp2')), slot.get('tp2Done', False), safe_float(slot.get('tp2Pct'), 0.30)),
        ('TP3', safe_float(slot.get('tp3')), slot.get('tp3Done', False), safe_float(slot.get('tp3Pct'), 0.30)),
    ]

    stop_loss = safe_float(slot.get('stopLoss'))
    sl_triggered = stop_loss > 0 and current_price <= stop_loss

    if sl_triggered:
        slots_to_close.append({
            'slot_id': slot['slotId'],
            'tp': 'SL',
            'entry': slot.get('entryPrice', 0),
            'tp_price': stop_loss,
            'current': current_price,
            'quantity': slot.get('quantity', 0),
            'usdt_spent': slot.get('usdtSpent', 0),
            'pct': 1.0,
        })
        continue

    for tp_name, tp_price, tp_done, pct in tp_targets:
        if tp_done or tp_price == 0:
            continue
        if current_price >= tp_price:
            slots_to_close.append({
                'slot_id': slot['slotId'],
                'tp': tp_name,
                'entry': slot.get('entryPrice', 0),
                'tp_price': tp_price,
                'current': current_price,
                'quantity': slot.get('quantity', 0),
                'usdt_spent': slot.get('usdtSpent', 0),
                'pct': pct,
            })

# Cierres
history_dir = os.path.join(os.path.dirname(state_file), 'history')
os.makedirs(history_dir, exist_ok=True)
trade_history_file = os.path.join(history_dir, 'trade-history-closed.json')

if not os.path.exists(trade_history_file):
    with open(trade_history_file, 'w') as f:
        json.dump({"version": "1.1", "closed": [], "cashouts": []}, f, indent=2)

for slot_info in slots_to_close:
    coin_display = coin
    slot_id = slot_info['slot_id']
    pct = slot_info.get('pct', 0.35)

    if slot_info['tp'] == 'SL':
        print(f"🛑 STOP LOSS HIT: {coin} Slot {slot_id}")
    else:
        print(f"🎯 TP HIT DETECTADO: {coin} Slot {slot_id} {slot_info['tp']} ({int(pct*100)}%)")

    print(f"   Entry: ${slot_info['entry']:.2f}")
    print(f"   TP: ${slot_info['tp_price']:.2f}")
    print(f"   Current: ${current_price:.2f}")

    quantity = safe_float(slot_info.get('quantity'), 0.0)
    close_qty = round(quantity * pct, 8) if quantity > 0 else 0.0

    if close_qty <= 0:
        print(f"   ⚠️ Cantidad a cerrar calculada en 0, salteando ejecución")
        continue

    print(f"   Quantity: {quantity:.8f}")
    print(f"   closeQty: {close_qty:.8f} (pct={pct})")
    print(f"   🚀 Ejecutando cierre PARCIAL...")
    
    # ════════════════════════════════════════════════════════
    # 🛡️ FASE 4: ON-CHAIN SELL CONFIRMATION
    # Antes de vender, verificar token audit + smart money
    # - BLOCK → confirma venta inmediata (token risky)
    # - WARN → smart money selling (good timing, proceed)
    # - ALLOW + smart money buying → recomendar venta parcial
    # ════════════════════════════════════════════════════════
    sell_status, sell_reason = on_chain_sell_check(coin)
    print(f"   🔍 On-chain sell check: {sell_status} — {sell_reason}")
    
    if sell_status == "ABORT_SELL":
        print(f"   ⛔ On-chain gate ABORTÓ venta de {coin}: {sell_reason}")
        print(f"   💡 Saltando cierre, trade sigue activo")
        continue
    
    # Ajustar posición si WARN
    if sell_status == "WARN_SELL":
        original_close_qty = close_qty
        close_qty = round(close_qty * 0.5, 8)  # Reducir venta al 50% si warn
        print(f"   ⚠️ On-chain WARN: reduciendo venta del {original_close_qty:.8f} al {close_qty:.8f} (50%)")
        if close_qty <= 0:
            print(f"   ⚠️ Cantidad ajustada en 0 después del warning, saltando")
            continue
    
    execute_order = True
    order_result = None
    try:
        order_result = place_sell_order_market(coin, f"{close_qty:.8f}")
        status = order_result.get('status', '')
        print(f"   Resultado venta: status={status}")
        if status != 'FILLED':
            print(f"   ❌ Venta no ejecutada: {order_result.get('msg', 'unknown')}")
            execute_order = False
    except Exception as exc:
        print(f"   ❌ Error ejecutando venta: {exc}")
        execute_order = False

    if execute_order:
        # Actualizar state con cierre parcial
        for slot in data.get('slots', []):
            if slot.get('slotId') == slot_id:
                remaining = safe_float(slot.get('quantity'), 0.0) - close_qty
                if remaining < 1e-8:
                    remaining = 0.0
                slot['quantity'] = remaining if remaining > 0 else None
                if slot_info['tp'] == 'TP1':
                    slot['tp1Done'] = True
                elif slot_info['tp'] == 'TP2':
                    slot['tp2Done'] = True
                elif slot_info['tp'] == 'TP3':
                    slot['tp3Done'] = True
                    if remaining <= 0:
                        slot['entryPrice'] = None
                        slot['usdtSpent'] = None
                        slot['stopLoss'] = None
                        slot['tp1'] = None
                        slot['tp2'] = None
                        slot['tp3'] = None
                        slot['tp1Done'] = False
                        slot['tp2Done'] = False
                        slot['tp3Done'] = False
                        slot['feeBuy'] = None
                        slot['totalCost'] = None
                        slot['highestPrice'] = None
                        slot['trailingStop'] = None
                        slot['orderId'] = None
                        slot['status'] = 'READY'
                elif slot_info['tp'] == 'SL':
                    slot['entryPrice'] = None
                    slot['quantity'] = None
                    slot['usdtSpent'] = None
                    slot['stopLoss'] = None
                    slot['tp1'] = None
                    slot['tp2'] = None
                    slot['tp3'] = None
                    slot['tp1Done'] = False
                    slot['tp2Done'] = False
                    slot['tp3Done'] = False
                    slot['feeBuy'] = None
                    slot['totalCost'] = None
                    slot['highestPrice'] = None
                    slot['trailingStop'] = None
                    slot['orderId'] = None
                    slot['status'] = 'READY'
                break

        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2)

    # Historial SIEMPRE se guarda
    closed_record = {
        'coin': coin,
        'slotId': slot_id,
        'closeType': slot_info['tp'],
        'entryPrice': slot_info['entry'],
        'closePrice': current_price,
        'quantity': close_qty,
        'usdtSpent': slot_info['usdt_spent'],
        'closeTime': datetime.now(timezone.utc).isoformat(),
        'orderId': order_result.get('orderId') if isinstance(order_result, dict) else None,
        'quantityRatio': pct,
    }

    try:
        with open(trade_history_file, 'r') as f:
            history_data = json.load(f)
    except (ValueError, FileNotFoundError):
        history_data = {"version": "1.1", "closed": [], "cashouts": []}

    history_data['closed'].append(closed_record)
    history_data['cashouts'].append({
        'time': closed_record['closeTime'],
        'coin': coin,
        'slotId': slot_id,
        'type': closed_record['closeType'],
        'amountUSDT': round(current_price * close_qty, 8),
        'price': current_price,
        'quantityRatio': pct,
    })
    with open(trade_history_file, 'w') as f:
        json.dump(history_data, f, indent=2)

    print(f"   💾 Historial cerrado guardado en {trade_history_file}")
    print()

# Progreso cercano a TP sin cierres
if not slots_to_close:
    for slot in data.get('slots', []):
        if slot.get('status') != 'ACTIVE':
            continue
        entry = safe_float(slot.get('entryPrice'))
        if entry <= 0:
            continue
        progress = ((current_price - entry) / entry) * 100
        tp1 = safe_float(slot.get('tp1'))
        tp2 = safe_float(slot.get('tp2'))
        tp3 = safe_float(slot.get('tp3'))
        next_tp = None
        next_tp_pct = None
        if not slot.get('tp1Done', False) and tp1 > 0:
            next_tp = tp1
            next_tp_pct = ((tp1 - entry) / entry) * 100
        elif not slot.get('tp2Done', False) and tp2 > 0:
            next_tp = tp2
            next_tp_pct = ((tp2 - entry) / entry) * 100
        elif not slot.get('tp3Done', False) and tp3 > 0:
            next_tp = tp3
            next_tp_pct = ((tp3 - entry) / entry) * 100
        if next_tp and next_tp_pct:
            progress_to_next = (progress / next_tp_pct) * 100
            if progress_to_next >= 95:
                print(f"⚠️  CERCA DEL TP: {coin} Slot {slot['slotId']} → {progress_to_next:.1f}%")
                print(f"   Current: ${current_price:.2f} | TP: ${next_tp:.2f}")
                print()
