#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - REPORTE DIARIO DE TRADING v2.1 (FIXED)
# ════════════════════════════════════════════════════════
# Ejecutar: 9:00 AM diario (cron)
# Envía: Portfolio total, PnL 24h, trades del día, trades activos, status sistema
# Formato: compacto, sin comillas extra, PnL (no P&L)
# FIX: timezone-aware comparisons, robust parsing
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
        chat_id = "7543955537"
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
    """Envía mensaje a Telegram usando curl con --data-urlencode (evita comillas extra)"""
    token, chat_id = get_telegram_config()

    if not token:
        print("❌ No Telegram token found", file=sys.stderr)
        return False

    try:
        import subprocess
        # Usar --data-urlencode para escapar correctamente el mensaje
        result = subprocess.run([
            'curl', '-s', '-w', '\n%{http_code}',
            '-X', 'POST',
            f'https://api.telegram.org/bot{token}/sendMessage',
            '-d', f'chat_id={chat_id}',
            '--data-urlencode', f'text={message}',
            '-d', 'parse_mode=Markdown',
            '--max-time', '15'
        ], capture_output=True, text=True, timeout=20)

        # Extraer código HTTP
        output = result.stdout
        lines = output.rsplit('\n', 1)
        if len(lines) == 2:
            body, http_code = lines
        else:
            body = output
            http_code = '000'

        if http_code == '200':
            if '"ok":true' in body or '"ok": True' in body:
                print("✅ Reporte enviado a Telegram")
                return True
            else:
                print(f"❌ Telegram API Error: {body}", file=sys.stderr)
                return False
        else:
            print(f"❌ HTTP Error: {http_code} | {body}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ Error enviando Telegram: {e}", file=sys.stderr)
        return False


def parse_datetime_safe(ts_str):
    """Parsea datetime de forma robusta, manejando timezone naive/aware"""
    if not ts_str:
        return None
    try:
        # Intentar parsear con fromisoformat
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        # Si no tiene timezone, asumir UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        try:
            # Fallback: strptime
            dt = datetime.strptime(ts_str[:19], '%Y-%m-%dT%H:%M:%S')
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None


def get_portfolio_total():
    """Obtiene portfolio total en USDT y MXN"""
    try:
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
        return 0.0, 0.0
    except Exception as e:
        print(f"Error getting portfolio: {e}", file=sys.stderr)
        return 0.0, 0.0


def get_pnl_24h_by_coin():
    """Obtiene PnL 24h por moneda desde trade-history.json
    FIX: timezone-aware comparison using UTC consistently
    """
    pnl_data = {coin: {'pnl_24h': 0.0, 'trades': 0, 'win': 0, 'loss': 0} for coin in COINS}
    try:
        history_file = CRYPTO_BOTS_DIR / "trade-history.json"
        if history_file.exists():
            with open(history_file) as f:
                data = json.load(f)
            # Cutoff: 24h ago, timezone-aware UTC
            cutoff = datetime.now(timezone.utc) - timedelta(days=1)

            for t in data.get("trades", []):
                ts = t.get("closeTime", "") or t.get("timestamp", "") or ""
                if not ts:
                    continue

                dt = parse_datetime_safe(ts)
                if dt is None:
                    continue

                # ✅ Comparación timezone-aware (both UTC)
                if dt >= cutoff:
                    coin = t.get("symbol", "")
                    if coin in COINS:
                        try:
                            pnl = float(t.get("pnlUSDT", 0) or 0)
                        except (ValueError, TypeError):
                            pnl = 0.0

                        pnl_data[coin]["pnl_24h"] += pnl
                        pnl_data[coin]["trades"] += 1
                        if pnl > 0:
                            pnl_data[coin]["win"] += 1
                        elif pnl < 0:
                            pnl_data[coin]["loss"] += 1

        for coin in COINS:
            pnl_data[coin]["pnl_24h"] = round(pnl_data[coin]["pnl_24h"], 4)
        return pnl_data
    except Exception as e:
        print(f"Error getting PnL: {e}", file=sys.stderr)
        return {coin: {'pnl_24h': 0.0, 'trades': 0, 'win': 0, 'loss': 0} for coin in COINS}


def get_yesterday_trades():
    """Obtiene trades del día anterior desde trade-history.json
    FIX: timezone-aware comparison
    """
    trades = []

    try:
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        # ✅ Usar UTC para comparación consistente con datos almacenados
        yesterday_utc = datetime.now(timezone.utc) - timedelta(days=1)
        cutoff = yesterday_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_end = cutoff + timedelta(days=1)

        history_file = CRYPTO_BOTS_DIR / "trade-history.json"
        if history_file.exists():
            with open(history_file) as f:
                data = json.load(f)
            for t in data.get("trades", []):
                ts = t.get("closeTime", "") or t.get("timestamp", "") or ""
                if not ts:
                    continue

                dt = parse_datetime_safe(ts)
                if dt is None:
                    continue

                # ✅ Comparación timezone-aware
                if cutoff <= dt < cutoff_end:
                    coin = t.get("symbol", "?")
                    close_type = t.get("closeType", "CLOSE")
                    slot_id = t.get("slotId", "?")
                    pnl_usdt = t.get("pnlUSDT", 0)

                    # ✅ Build line robustamente
                    try:
                        pnl_str = f"{float(pnl_usdt):.4f}"
                    except (ValueError, TypeError):
                        pnl_str = "0"

                    trades.append({
                        'coin': coin,
                        'line': f"{ts} {coin} slot{slot_id} {close_type} PnL={pnl_str}"
                    })

        if not trades:
            # Fallback: leer logs de cron SOLO para trades realmente cerrados
            for coin in COINS:
                log_file = Path.home() / ".openclaw" / "logs" / f"cron-{coin}.log"
                if log_file.exists():
                    try:
                        with open(log_file, 'r') as f:
                            for line in f:
                                if yesterday_str in line:
                                    # ✅ Solo líneas que REALMENTE indican trade cerrado
                                    # Formatos: "Trade logged", "cerrado", "SL HIT", "TP1/2/3 HIT"
                                    if 'Trade logged' in line or 'cerrado' in line:
                                        if 'TP' in line or 'SL' in line:
                                            trades.append({
                                                'coin': coin,
                                                'line': line.strip()
                                            })
                    except Exception:
                        pass

        return trades
    except Exception as e:
        print(f"Error getting trades: {e}", file=sys.stderr)
        return []


def get_active_trades():
    """Obtiene trades activos con status leyendo state files"""
    active = []
    try:
        for coin in COINS:
            state_file = CRYPTO_BOTS_DIR / f"{coin}-trade-state.json"
            if not state_file.exists():
                continue
            try:
                state = json.loads(state_file.read_text())
            except Exception:
                continue
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
                    active.append({
                        "coin": coin,
                        "slotId": slot.get("slotId"),
                        "entry": entry,
                        "current": current,
                        "quantity": quantity,
                        "orderId": slot.get("orderId"),
                        "pnl": pnl,
                    })
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
        active_count = 0
        for coin in COINS:
            state_file = CRYPTO_BOTS_DIR / f"{coin}-trade-state.json"
            if not state_file.exists():
                continue
            try:
                state = json.loads(state_file.read_text())
                active_count += sum(1 for s in state.get("slots", []) if s.get("status") == "ACTIVE")
            except Exception:
                pass
        status['orders_active'] = active_count

        ip_log = LOGS_DIR / "ip-whitelist.log"
        if ip_log.exists():
            try:
                with open(ip_log, 'r') as f:
                    lines = f.readlines()[-10:]
                    if any('ERROR' in line or 'FAIL' in line for line in lines):
                        status['ip'] = '⚠️ Revisar'
                        status['alerts'].append('IP whitelist requiere atención')
            except Exception:
                pass

        api_log = LOGS_DIR / "binance-api.log"
        if api_log.exists():
            try:
                with open(api_log, 'r') as f:
                    lines = f.readlines()[-20:]
                    error_count = sum(1 for line in lines if 'ERROR' in line or '429' in line)
                    if error_count > 5:
                        status['api'] = '⚠️ Rate limit'
                        status['alerts'].append(f'{error_count} errores API recientes')
            except Exception:
                pass

        return status
    except Exception as e:
        print(f"Error checking system: {e}", file=sys.stderr)
        status['alerts'].append(f'Error verificando sistema: {e}')
        return status


def get_win_rate(days=1):
    """Calcula win rate de los últimos N días
    FIX: timezone-aware comparison
    """
    history_file = CRYPTO_BOTS_DIR / 'trade-history.json'
    if not history_file.exists():
        return 0, 0, 0
    try:
        with open(history_file) as f:
            data = json.load(f)
        trades = data.get('trades', [])
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent = []
        for t in trades:
            ts = t.get('timestamp') or t.get('closeTime') or ''
            dt = parse_datetime_safe(ts)
            if dt is None:
                continue
            if dt >= cutoff:
                recent.append(t)

        total = len(recent)
        wins = sum(1 for t in recent if t.get('pnlUSDT') is not None and float(t.get('pnlUSDT') or 0) > 0)
        losses = total - wins
        return wins, losses, total
    except Exception:
        return 0, 0, 0


def generate_report():
    """Genera el reporte diario compacto v2"""
    now = datetime.now()
    date_str = now.strftime('%A %Y-%m-%d')

    total_usdt, total_mxn = get_portfolio_total()

    # PnL 24h por moneda
    pnl_data = {coin: {'pnl_24h': 0.0, 'trades': 0, 'win': 0, 'loss': 0} for coin in COINS}
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(get_pnl_24h_by_coin)
            pnl_data = fut.result(timeout=10)
    except Exception:
        pass

    yesterday_trades = get_yesterday_trades()
    active_trades = get_active_trades()
    system = get_system_status()

    total_pnl = sum(d['pnl_24h'] for d in pnl_data.values())

    if yesterday_trades:
        wins = sum(1 for t in yesterday_trades if 'TP' in t.get('line', ''))
        losses = sum(1 for t in yesterday_trades if 'SL' in t.get('line', ''))
        total_yest = len(yesterday_trades)
        win_rate = (wins / max(total_yest, 1)) * 100
        pnl_sum = 0.0
        for t in yesterday_trades:
            try:
                pnl_str = t.get('line', '').split('PnL=')[1].strip()
                pnl_val = float(pnl_str)
            except (IndexError, ValueError):
                pnl_val = 0.0
            pnl_sum += pnl_val
    else:
        wins, losses, total_yest = 0, 0, 0
        win_rate = 0.0
        pnl_sum = 0.0

    lines = []
    lines.append(f"🐕 **REPORTE DIARIO** - 📅 {date_str}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("💰 **PORTAFOLIO**")
    lines.append(f"USDT: ${total_usdt:,.2f} | MXN: ${total_mxn:,.0f}")
    lines.append(f"PnL 24h: ${total_pnl:+,.2f} ({win_rate:.0f}% WR)")
    lines.append("")
    lines.append("📊 **PnL 24H POR MONEDA**")
    for coin in COINS:
        data = pnl_data.get(coin, {})
        pnl = data.get('pnl_24h', 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        lines.append(f"{emoji} {coin}: ${pnl:+,.2f}")
    lines.append("")
    lines.append("📈 **AYER**")
    lines.append(f"Trades: {total_yest} | W:{wins} L:{losses} | PnL: ${pnl_sum:+,.2f}")
    lines.append("")

    if active_trades:
        lines.append("🎯 **ACTIVOS**")
        for trade in active_trades:
            coin = trade.get('coin', '?')
            entry = trade.get('entry', 0)
            current = trade.get('current', 0)
            pnl = trade.get('pnl', 0)
            emoji = "🟢" if pnl >= 0 else "🔴"
            lines.append(f"{emoji} {coin}: ${entry:.2f} → ${current:.2f} ({pnl:+.2f})")
        lines.append("")

    lines.append("🛡️ **SISTEMA**")
    lines.append(f"API: {system['api']} | IP: {system['ip']} | Órdenes: {system['orders_active']}")
    if system['alerts']:
        for alert in system['alerts']:
            lines.append(f"⚠️ {alert}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 Perrobotillo v2.1")

    return "\n".join(lines)


def main():
    print(f"🐕 Generando reporte diario - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report = generate_report()
    print("\n" + report + "\n")
    send_telegram(report)

    today = datetime.now().strftime('%Y-%m-%d')
    report_file = CRYPTO_BOTS_DIR / f"daily-report-{today}.md"

    try:
        with open(report_file, 'w') as f:
            md_report = report.replace('<b>', '**').replace('</b>', '**')
            md_report = md_report.replace('<i>', '_').replace('</i>', '_')
            f.write(md_report)
        print(f"✅ Reporte guardado: {report_file}")
    except Exception as e:
        print(f"⚠️ No se pudo guardar el reporte: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
