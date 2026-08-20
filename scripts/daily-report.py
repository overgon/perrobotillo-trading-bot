#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - REPORTE DIARIO DE TRADING
# ════════════════════════════════════════════════════════
# Ejecutar: 9:00 AM diario
# Envía: Portfolio total, P&L 24h, trades del día, trades activos, status sistema
# ════════════════════════════════════════════════════════

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
LOGS_DIR = WORKSPACE / "logs"
CRYPTO_BOTS_DIR = WORKSPACE / "crypto-bots"
SECRETS_DIR = Path.home() / ".openclaw" / "secrets"

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

def load_env_file(filepath):
    """Carga variables de entorno desde archivo .env"""
    env_vars = {}
    if filepath.exists():
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

def get_telegram_config():
    """Obtiene configuración de Telegram"""
    try:
        config_file = Path.home() / ".openclaw" / "openclaw.json"
        chat_id = "7543955537"  # Default from USER.md
        token = ""
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
                telegram = config.get('channels', {}).get('telegram', {})
                token = telegram.get('botToken', '')
                chat_ids = telegram.get('chatIds', [])
                if chat_ids:
                    chat_id = chat_ids[0]
        
        return token, chat_id
    except Exception as e:
        print(f"Error getting Telegram config: {e}", file=sys.stderr)
        return "", "7543955537"

def send_telegram(message):
    """Envía mensaje a Telegram"""
    token, chat_id = get_telegram_config()
    
    if not token:
        print("❌ No Telegram token found", file=sys.stderr)
        return False
    
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=data, timeout=15)
        if response.status_code == 200:
            print("✅ Reporte enviado a Telegram")
            return True
        else:
            print(f"❌ Error Telegram: {response.text}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ Error enviando Telegram: {e}", file=sys.stderr)
        return False

def get_portfolio_total():
    """Obtiene portfolio total en USDT y MXN desde dashboard + cache local"""
    try:
        # 1) Fuente principal: dashboard local, ya incluye toda la cartera
        import requests as _requests
        try:
            r = _requests.get("http://127.0.0.1:8080/api/portfolio", timeout=10)
            if r.status_code == 200:
                data = r.json()
                total_usdt = float(data.get("value", 0) or 0)
                mxn_rate = float(data.get("mxn_rate", 17.44) or 17.44)
                total_mxn = float(data.get("value_mx", 0) or 0)
                if total_usdt > 0:
                    return round(total_usdt, 2), round(total_mxn, 2)
        except Exception as e:
            print(f"⚠️ Dashboard portfolio unavailable: {e}", file=sys.stderr)
        # 2) Fallback: cache local si existe
        for p in [CRYPTO_BOTS_DIR / "portfolio-snapshot.json", CRYPTO_BOTS_DIR.parent / "portfolio_cache.json"]:
            try:
                if p.exists():
                    snap = json.loads(p.read_text())
                    total_usdt = float(snap.get("totalUSDT", snap.get("value", 0)) or 0)
                    mxn_rate = float(snap.get("mxn_rate", 17.44) or 17.44)
                    if total_usdt > 0:
                        return round(total_usdt, 2), round(total_usdt * mxn_rate, 2)
            except Exception:
                pass
        # 3) Si todo falla, no devolver 0; dejar valor actual para forzar inspección
        return 0.0, 0.0
    except Exception as e:
        print(f"Error getting portfolio: {e}", file=sys.stderr)
        return 0.0, 0.0

def get_pnl_24h_by_coin():
    """Obtiene P&L 24h por moneda desde trade-history.json.
    
    NOTA: solo incluye trades CERRADOS en las últimas 24h.
    El P&L no realizado de slots activos NO se suma aquí para evitar
    confundir el reporte diario; los activos se muestran por separado.
    """
    pnl_data = {coin: {'pnl_24h': 0, 'trades': 0, 'win': 0, 'loss': 0} for coin in COINS}
    try:
        history_file = CRYPTO_BOTS_DIR / "trade-history.json"
        if history_file.exists():
            with open(history_file) as f:
                data = json.load(f)
            cutoff = datetime.now(timezone.utc) - timedelta(days=1)
            for t in data.get("trades", []):
                ts = t.get("timestamp", "")
                if not ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                if dt >= cutoff:
                    coin = t.get("symbol")
                    if coin in COINS:
                        pnl = t.get("pnlUSDT", 0) or 0
                        pnl_data[coin]["pnl_24h"] += pnl
                        pnl_data[coin]["trades"] += 1
                        if pnl > 0:
                            pnl_data[coin]["win"] += 1
                        else:
                            pnl_data[coin]["loss"] += 1

        for coin in COINS:
            pnl_data[coin]["pnl_24h"] = round(pnl_data[coin]["pnl_24h"], 4)
        return pnl_data
    except Exception as e:
        print(f"Error getting P&L: {e}", file=sys.stderr)
        return {coin: {'pnl_24h': 0, 'trades': 0, 'win': 0, 'loss': 0} for coin in COINS}

def get_yesterday_trades():
    """Obtiene trades del día anterior desde trade-history.json y logs"""
    trades = []
    
    try:
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        
        # Fuente principal: trade-history.json
        history_file = CRYPTO_BOTS_DIR / "trade-history.json"
        if history_file.exists():
            with open(history_file) as f:
                data = json.load(f)
            for t in data.get("trades", []):
                ts = t.get("closeTime", "") or t.get("timestamp", "")
                if not ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
                if dt.strftime('%Y-%m-%d') == yesterday_str:
                    trades.append({
                        'coin': t.get('symbol'),
                        'line': f"{t.get('closeTime')} {t.get('symbol')} slot{t.get('slotId')} {t.get('closeType')} PnL={t.get('pnlUSDT')}"
                    })
        
        # Fallback: logs de cron en ~/.openclaw/logs/
        if not trades:
            for coin in COINS:
                log_file = Path.home() / ".openclaw" / "logs" / f"cron-{coin}.log"
                if log_file.exists():
                    with open(log_file, 'r') as f:
                        for line in f:
                            if yesterday_str in line:
                                if any(x in line for x in ['TP', 'SL', 'cerrado', 'Trade logged']):
                                    trades.append({
                                        'coin': coin,
                                        'line': line.strip()
                                    })
        
        return trades
    except Exception as e:
        print(f"Error getting trades: {e}", file=sys.stderr)
        return []

def get_active_trades():
    """Obtiene trades activos con status leyendo los archivos de estado por moneda"""
    active = []
    try:
        for coin in COINS:
            state_file = CRYPTO_BOTS_DIR / f"{coin}-trade-state.json"
            if not state_file.exists():
                continue
            state = json.loads(state_file.read_text())
            active_slots = []
            for slot in state.get("slots", []):
                if slot.get("status") == "ACTIVE":
                    entry = float(slot.get("entryPrice", 0) or 0)
                    quantity = float(slot.get("quantity", 0) or 0)
                    usdt_spent = float(slot.get("usdtSpent", 0) or 0)
                    avg_cost = usdt_spent / quantity if usdt_spent > 0 and quantity > 0 else entry
                    current = entry
                    try:
                        import requests as _requests
                        r = _requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=4)
                        if r.status_code == 200:
                            current = float(r.json().get("price", entry) or entry)
                    except Exception:
                        current = entry
                    pnl = quantity * (current - avg_cost)
                    active_slots.append({
                        "coin": coin,
                        "slotId": slot.get("slotId"),
                        "entry": entry,
                        "current": current,
                        "quantity": quantity,
                        "orderId": slot.get("orderId"),
                        "pnl": pnl,
                    })
            active.extend(active_slots)
    except Exception as e:
        print(f"Error getting active trades: {e}", file=sys.stderr)
        return []
    return active

def get_system_status():
    """Verifica estado del sistema"""
    status = {
        'api': '✅ OK',
        'ip': '✅ OK',
        'alerts': [],
        'orders_active': 0
    }
    
    try:
        # Conteo real de trades activos desde state files
        active_count = 0
        for coin in COINS:
            state_file = CRYPTO_BOTS_DIR / f"{coin}-trade-state.json"
            if not state_file.exists():
                continue
            state = json.loads(state_file.read_text())
            active_count += sum(1 for s in state.get("slots", []) if s.get("status") == "ACTIVE")
        status['orders_active'] = active_count
        
        # Verificar IP whitelist
        ip_log = LOGS_DIR / "ip-whitelist.log"
        if ip_log.exists():
            with open(ip_log, 'r') as f:
                lines = f.readlines()[-10:]
                if any('ERROR' in line or 'FAIL' in line for line in lines):
                    status['ip'] = '⚠️ Revisar'
                    status['alerts'].append('IP whitelist requiere atención')
        
        # Verificar API
        api_log = LOGS_DIR / "binance-api.log"
        if api_log.exists():
            with open(api_log, 'r') as f:
                lines = f.readlines()[-20:]
                error_count = sum(1 for line in lines if 'ERROR' in line or '429' in line)
                if error_count > 5:
                    status['api'] = '⚠️ Rate limit'
                    status['alerts'].append(f'{error_count} errores API recientes')
        
        return status
    except Exception as e:
        print(f"Error checking system: {e}", file=sys.stderr)
        status['alerts'].append(f'Error verificando sistema: {e}')
        return status

def get_win_rate(days=1):
    """Calcula win rate de los últimos N días desde trade-history.json"""
    history_file = CRYPTO_BOTS_DIR / 'trade-history.json'
    if not history_file.exists():
        return 0, 0, 0
    try:
        with open(history_file) as f:
            data = json.load(f)
        trades = data.get('trades', [])
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        for t in trades:
            ts = t.get('timestamp') or t.get('closeTime') or ''
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except Exception:
                continue
            if dt >= cutoff:
                recent.append(t)
        total = len(recent)
        wins = sum(1 for t in recent if t.get('pnlUSDT') is not None and t['pnlUSDT'] > 0)
        losses = total - wins
        return wins, losses, total
    except Exception:
        return 0, 0, 0

def generate_report():
    """Genera el reporte diario completo"""
    now = datetime.now()
    date_str = now.strftime('%A %Y-%m-%d')
    
    # Obtener datos
    total_usdt, total_mxn = get_portfolio_total()
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(get_pnl_24h_by_coin)
            pnl_data = fut.result(timeout=8)
    except Exception:
        pnl_data = {coin: {'pnl_24h': 0, 'trades': 0, 'win': 0, 'loss': 0} for coin in COINS}
    yesterday_trades = get_yesterday_trades()
    active_trades = get_active_trades()
    system = get_system_status()
    
    # Calcular totales
    total_pnl = sum(d['pnl_24h'] for d in pnl_data.values())
    total_trades = sum(d['trades'] for d in pnl_data.values())
    if yesterday_trades:
        wins = sum(1 for t in yesterday_trades if 'TP' in t['line'])
        losses = sum(1 for t in yesterday_trades if 'SL' in t['line'])
        win_rate = (wins / max(len(yesterday_trades), 1)) * 100
    else:
        wins = 0
        losses = 0
        win_rate = 0.0
    
    # Construir mensaje
    report = []
    report.append("🐕 <b>REPORTE DIARIO DE TRADING</b> 🐕")
    report.append(f"📅 {date_str} - 9:00 AM")
    report.append("")
    report.append("━━━━━━━━━━━━━━━━━━━━━━")
    report.append("")
    
    # Portfolio
    report.append("💰 <b>PORTFOLIO TOTAL</b>")
    report.append(f"   USDT: <b>${total_usdt:,.2f}</b>")
    report.append(f"   MXN: <b>${total_mxn:,.0f}</b>")
    report.append("")
    
    # P&L 24h por moneda
    report.append("📊 <b>P&L 24H POR MONEDA</b>")
    for coin in COINS:
        data = pnl_data.get(coin, {})
        pnl = data.get('pnl_24h', 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        report.append(f"   {emoji} {coin}: ${pnl:+,.2f}")
    report.append(f"   ─────────────")
    report.append(f"   Total: <b>${total_pnl:+,.2f}</b>")
    report.append("")
    
    # Trades ayer
    report.append("📈 <b>TRADES DE AYER</b>")
    global_wins, global_losses, global_total = get_win_rate(days=1)
    global_win_rate = (global_wins / global_total * 100) if global_total > 0 else 0.0
    report.append(f"   Total: {global_total} trades")
    report.append(f"   Wins: {global_wins} | Losses: {global_losses}")
    report.append(f"   Win Rate: <b>{global_win_rate:.1f}%</b>")
    report.append(f"   P&L: <b>${total_pnl:+,.2f}</b>")
    report.append("")
    
    # Trades activos
    report.append("🎯 <b>TRADES ACTIVOS</b>")
    if active_trades:
        for trade in active_trades:
            coin = trade.get('coin', '?')
            entry = trade.get('entry', 0)
            current = trade.get('current', 0)
            pnl = trade.get('pnl', 0)
            emoji = "🟢" if pnl >= 0 else "🔴"
            report.append(f"   {emoji} {coin}: Entry ${entry:.2f} → ${current:.2f} ({pnl:+.2f})")
    else:
        report.append("   Sin trades activos")
    report.append("")
    
    # Sistema
    report.append("🛡️ <b>ESTADO DEL SISTEMA</b>")
    report.append(f"   API Binance: {system['api']}")
    report.append(f"   IP Whitelist: {system['ip']}")
    report.append(f"   Órdenes Activas: {system['orders_active']}")
    
    if system['alerts']:
        report.append("")
        report.append("⚠️ <b>ALERTAS:</b>")
        for alert in system['alerts']:
            report.append(f"   • {alert}")
    
    report.append("")
    report.append("━━━━━━━━━━━━━━━━━━━━━━")
    report.append("🤖 <i>Perrobotillo Trading Bot v2.1</i>")
    
    return "\n".join(report)

def main():
    print(f"🐕 Generando reporte diario - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    report = generate_report()
    
    # Imprimir en consola
    print("\n" + report + "\n")
    
    # Enviar a Telegram
    send_telegram(report)
    
    # Guardar copia local
    today = datetime.now().strftime('%Y-%m-%d')
    report_file = CRYPTO_BOTS_DIR / f"daily-report-{today}.md"
    
    try:
        with open(report_file, 'w') as f:
            # Convertir HTML a markdown simple para archivo
            md_report = report.replace('<b>', '**').replace('</b>', '**')
            md_report = md_report.replace('<i>', '_').replace('</i>', '_')
            f.write(md_report)
        print(f"✅ Reporte guardado: {report_file}")
    except Exception as e:
        print(f"⚠️ No se pudo guardar el reporte: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
