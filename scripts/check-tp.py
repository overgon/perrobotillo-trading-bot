#!/usr/bin/env python3
"""
TP Checker - Verifica si hay TPs que cerrar para una moneda
Uso: python3 check-tp.py COIN CURRENT_PRICE STATE_FILE LOG_FILE
"""

import json
import subprocess
import sys
from datetime import datetime
import os
import urllib.request
import urllib.parse

if len(sys.argv) < 5:
    print(f"Usage: {sys.argv[0]} COIN CURRENT_PRICE STATE_FILE LOG_FILE")
    sys.exit(1)

coin = sys.argv[1]
current_price = float(sys.argv[2])
state_file = sys.argv[3]
log_file = sys.argv[4]

print(f"DEBUG Python: Checking {coin} at ${current_price}")

with open(state_file, 'r') as f:
    data = json.load(f)

slots_to_close = []

for slot in data.get('slots', []):
    print(f"DEBUG: Slot {slot.get('slotId')} status={slot.get('status')}")
    if slot.get('status') != 'ACTIVE':
        continue
    
    # Verificar TP1, TP2, TP3 y STOP LOSS
    tp_targets = [
        ('TP1', slot.get('tp1', 0), slot.get('tp1Done', False)),
        ('TP2', slot.get('tp2', 0), slot.get('tp2Done', False)),
        ('TP3', slot.get('tp3', 0), slot.get('tp3Done', False)),
    ]
    
    # Verificar Stop Loss
    stop_loss = slot.get('stopLoss', 0)
    sl_triggered = False
    if stop_loss > 0 and current_price <= stop_loss:
        sl_triggered = True
    
    for tp_name, tp_price, tp_done in tp_targets:
        if tp_done or tp_price == 0:
            continue
        
        if current_price >= tp_price:
            slots_to_close.append({
                'slot_id': slot['slotId'],
                'tp': tp_name,
                'entry': slot['entryPrice'],
                'tp_price': tp_price,
                'current': current_price,
                'quantity': slot['quantity'],
                'usdt_spent': slot['usdtSpent']
            })
    
    # Verificar Stop Loss
    if sl_triggered and stop_loss > 0:
        slots_to_close.append({
            'slot_id': slot['slotId'],
            'tp': 'SL',
            'entry': slot['entryPrice'],
            'tp_price': stop_loss,
            'current': current_price,
            'quantity': slot['quantity'],
            'usdt_spent': slot['usdtSpent']
        })

# Ejecutar cierres
for slot_info in slots_to_close:
    if slot_info['tp'] == 'SL':
        print(f"🛑 STOP LOSS HIT: {coin} Slot {slot_info['slot_id']}")
    else:
        print(f"🎯 TP HIT DETECTADO: {coin} Slot {slot_info['slot_id']} {slot_info['tp']}")
    
    print(f"   Entry: ${slot_info['entry']:.2f}")
    print(f"   TP: ${slot_info['tp_price']:.2f}")
    print(f"   Current: ${slot_info['current']:.2f}")
    print(f"   Quantity: {slot_info['quantity']}")
    print(f"   🚀 Ejecutando cierre INMEDIATO...")
    
    # Ejecutar cierre
    cmd = f"$HOME/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh {coin}"
    subprocess.run(cmd, shell=True, capture_output=True)
    
    print(f"   ✅ Cierre ejecutado")
    
    # Actualizar estado
    slot_id = slot_info['slot_id']
    tp_name = slot_info['tp']
    
    for slot in data.get('slots', []):
        if slot.get('slotId') == slot_id:
            slot['status'] = 'READY'
            if tp_name == 'TP1':
                slot['tp1Done'] = True
            elif tp_name == 'TP2':
                slot['tp2Done'] = True
            elif tp_name == 'TP3':
                slot['tp3Done'] = True
            break
    
    with open(state_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"   📝 Estado actualizado: Slot {slot_id} → READY")
    
    # Enviar alerta por Telegram
    telegram_env = os.path.expanduser("~/.openclaw/secrets/telegram.env")
    if os.path.exists(telegram_env):
        with open(telegram_env, 'r') as tg_file:
            for line in tg_file:
                if line.startswith('TELEGRAM_BOT_TOKEN='):
                    tg_token = line.strip().split('=')[1]
                elif line.startswith('TELEGRAM_CHAT_ID='):
                    tg_chat_id = line.strip().split('=')[1]
        
        pnl = (slot_info['current'] - slot_info['entry']) * slot_info['quantity']
        pnl_pct = ((slot_info['current'] - slot_info['entry']) / slot_info['entry']) * 100
        
        if slot_info['tp'] == 'SL':
            emoji = "🛑"
            title = "STOP LOSS HIT"
            pnl_str = f"-${abs(pnl):.2f} ({pnl_pct:.2f}%)"
        elif pnl >= 0:
            emoji = "✅"
            title = f"TP HIT - {slot_info['tp']}"
            pnl_str = f"+${pnl:.2f} ({pnl_pct:.2f}%)"
        else:
            emoji = "⚠️"
            title = f"TP HIT - {slot_info['tp']}"
            pnl_str = f"-${abs(pnl):.2f} ({pnl_pct:.2f}%)"
        
        message = (
            f"{emoji} {title}\n\n"
            f"🪙 {coin}/USDT - Slot {slot_id}\n\n"
            f"💰 Entry: ${slot_info['entry']:.2f}\n"
            f"🎯 Target: ${slot_info['tp_price']:.2f}\n"
            f"📈 Current: ${slot_info['current']:.2f}\n\n"
            f"💵 P&L: {pnl_str}\n"
            f"📊 Cantidad: {slot_info['quantity']}\n\n"
            f"⚡ Cierre ejecutado por TP Monitor\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST\n\n"
            f"🐕 Perrobotillo Trading Bot"
        )
        
        try:
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            data_req = urllib.parse.urlencode({
                'chat_id': tg_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }).encode()
            urllib.request.urlopen(url, data_req, timeout=10)
            print(f"   📱 Alerta enviada por Telegram")
        except Exception as e:
            print(f"   ❌ Error enviando Telegram: {e}")
        
        # NOTIFICAR AL DASHBOARD PARA SONIDO EN NAVEGADOR
        try:
            dashboard_url = "http://localhost:8080/api/notify-tp"
            notify_data = urllib.parse.urlencode({
                'coin': coin,
                'slot_id': slot_info['slot_id'],
                'tp': slot_info['tp'],
                'pnl': pnl
            }).encode()
            
            req = urllib.request.Request(dashboard_url, data=notify_data)
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=5)
            print(f"   🌐 Dashboard notificado")
        except Exception as e:
            print(f"   ⚠️ Dashboard no notificado: {e}")
    
    print()

if not slots_to_close:
    for slot in data.get('slots', []):
        if slot.get('status') != 'ACTIVE':
            continue
        
        entry = slot.get('entryPrice', 0)
        if entry > 0:
            progress = ((current_price - entry) / entry) * 100
            
            tp1 = slot.get('tp1', 0)
            tp2 = slot.get('tp2', 0)
            tp3 = slot.get('tp3', 0)
            
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
