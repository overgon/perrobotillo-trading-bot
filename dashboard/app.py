#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO TRADING DASHBOARD - CYBERPUNK EDITION
# ════════════════════════════════════════════════════════
# Dashboard avanzado con tiempo real
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

from flask import Flask, render_template, jsonify, request, send_from_directory
import threading

_DASH_CACHE = {}
_DASH_CACHE_LOCK = threading.Lock()
from functools import wraps
import json
import os
import subprocess
from datetime import datetime
import glob
import base64

_DASH_TTL = 5

def _set_mem_cache(key, value, ttl=_DASH_TTL):
    with _DASH_CACHE_LOCK:
        _DASH_CACHE[key] = {'value': value, 'ts': __import__('time').time(), 'ttl': ttl}

def _get_mem_cache(key):
    with _DASH_CACHE_LOCK:
        entry = _DASH_CACHE.get(key)
        if not entry:
            return None
        if __import__('time').time() - entry.get('ts', 0) > entry.get('ttl', _DASH_TTL):
            _DASH_CACHE.pop(key, None)
            return None
        return entry.get('value')

def get_mxn_rate():
    """Obtener tasa de cambio USDT/MXN en tiempo real de Binance con cache"""
    import os, time, json
    
    # Primero intentar leer del portfolio cache (si existe)
    portfolio_cache = "/tmp/portfolio_cache.json"
    if os.path.exists(portfolio_cache):
        try:
            with open(portfolio_cache) as f:
                cache = json.load(f)
                if 'mxn_rate' in cache:
                    rate = cache['mxn_rate']
                    print(f"💱 MXN rate from portfolio cache: ${rate:.4f}")
                    return rate
        except:
            pass
    
    cache_file = "/tmp/mxn_rate_cache.json"
    
    # Try cache first (5 minutes)
    if os.path.exists(cache_file):
        cache_age = time.time() - os.path.getmtime(cache_file)
        if cache_age < 300:  # 5 minutos
            with open(cache_file) as f:
                cached = json.load(f)
                rate = cached.get('rate', 17.5)
                print(f"💱 MXN rate from cache: ${rate:.4f} (age: {cache_age:.1f}s)")
                return rate
    
    # Fetch from Binance
    try:
        import requests
        response = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=USDTMXN', timeout=2)
        rate = float(response.json().get('price', 17.5))
        
        # Save cache
        with open(cache_file, 'w') as f:
            json.dump({'rate': rate, 'timestamp': time.time()}, f)
        
        print(f"💱 MXN rate from Binance: ${rate:.4f}")
        return rate
    except Exception as e:
        print(f"⚠️ Error getting MXN rate: {e}, using fallback")
        # Fallback: usar ultimo cache aunque este viejo
        try:
            if os.path.exists(cache_file):
                with open(cache_file) as f:
                    cached = json.load(f)
                    return cached.get('rate', 17.5)
        except:
            pass
        return 17.5  # Fallback final


app = Flask(__name__)

# ════════════════════════════════════════════════════════
# 🔒 SECURITY - HIDE SERVER HEADERS
# ════════════════════════════════════════════════════════

@app.after_request
def hide_server_headers(response):
    """Ocultar headers del servidor por seguridad"""
    response.headers.pop('Server', None)
    response.headers.pop('X-Powered-By', None)
    return response

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
CRYPTO_BOTS = f"{WORKSPACE}/crypto-bots"
CONFIG_FILE = f"{WORKSPACE}/config/capital-config.sh"

# ════════════════════════════════════════════════════════
# 🔒 SECURITY - HIDE SERVER HEADERS
# ════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════
# 📱 MOBILE VS DESKTOP ROUTING
# ════════════════════════════════════════════════════════

def is_mobile_device():
    """Detectar si el usuario está en dispositivo móvil"""
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # Dispositivos móviles comunes
    mobile_keywords = [
        'mobile', 'android', 'iphone', 'ipad', 'ipod',
        'blackberry', 'windows phone', 'opera mini', 'iemobile'
    ]
    
    is_mobile = any(keyword in user_agent for keyword in mobile_keywords)
    
    print(f'📱 Device Detection: {"MOBILE" if is_mobile else "DESKTOP"} - {user_agent[:50]}')
    
    return is_mobile

# ════════════════════════════════════════════════════════
# 🔐 HTTP BASIC AUTH CONFIGURATION
# ════════════════════════════════════════════════════════

AUTH_FILE = f"{WORKSPACE}/dashboard/.htpasswd"

def check_auth(username, password):
    """Verificar credenciales usando subprocess con htpasswd"""
    try:
        result = subprocess.run(
            ['htpasswd', '-vb', AUTH_FILE, username, password],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Auth error: {e}")
        return False

def authenticate():
    """Retornar respuesta 401 con header WWW-Authenticate"""
    return (
        jsonify({'error': 'Authentication required'}),
        401,
        {'WWW-Authenticate': 'Basic realm="Perrobotillo Dashboard"'}
    )

def requires_auth(f):
    """Decorator para proteger rutas"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization')
        if not auth:
            return authenticate()
        
        try:
            auth_type, auth_string = auth.split(None, 1)
            if auth_type.lower() != 'basic':
                return authenticate()
            
            decoded = base64.b64decode(auth_string).decode('utf-8')
            username, password = decoded.split(':', 1)
            
            if not check_auth(username, password):
                return authenticate()
                
        except Exception as e:
            print(f"Auth decode error: {e}")
            return authenticate()
        
        return f(*args, **kwargs)
    return decorated

# ════════════════════════════════════════════════════════
# FUNCIONES DE DATOS
# ════════════════════════════════════════════════════════

def get_portfolio_value():
    """Obtener valor total del portfolio DESDE BINANCE (tiempo real) + CACHE"""
    import os, time, json, requests, hmac, hashlib
    
    cache_file = "/tmp/portfolio_cache.json"
    
    # 1. Try cache first (10 minutes)
    if os.path.exists(cache_file):
        cache_age = time.time() - os.path.getmtime(cache_file)
        if cache_age < 600:  # 10 minutos
            with open(cache_file) as f:
                cached = json.load(f)
                print(f"💰 Portfolio from cache (${cached.get('value', 0):.2f}) - age: {cache_age:.1f}s")
                return float(cached.get('value', 0))
    
    # 2. Try to fetch from Binance
    try:
        secrets_file = os.path.expanduser("~/.openclaw/secrets/binance.env")
        if not os.path.exists(secrets_file):
            print("⚠️  No binance.env, using snapshot")
            snapshot_file = f"{WORKSPACE}/portfolio-snapshot.json"
            if os.path.exists(snapshot_file):
                with open(snapshot_file, 'r') as f:
                    data = json.load(f)
                    return float(data.get('value', 0))
            return 0.0
        
        with open(secrets_file, 'r') as f:
            lines = f.readlines()
            API_KEY = lines[0].split('=')[1].strip()
            API_SECRET = lines[1].split('=')[1].strip()
        
        # 3. Get balance from Binance
        # Sincronizar timestamp con Binance para evitar -1021 / -2015 por desfase
        try:
            t = requests.get('https://api.binance.com/api/v3/time', timeout=2)
            server_ts = int(t.json().get('serverTime', 0) or 0)
        except Exception:
            server_ts = int(time.time() * 1000)
        params = f'recvWindow=60000&timestamp={server_ts}'
        signature = hmac.new(API_SECRET.encode(), params.encode(), hashlib.sha256).hexdigest()
        
        headers = {'X-MBX-APIKEY': API_KEY}
        url = f'https://api.binance.com/api/v3/account?{params}&signature={signature}'
        
        response = requests.get(url, headers=headers, timeout=3)
        data = response.json()
        
        if 'balances' not in data:
            raise Exception(f"Binance API error: {data}")
        
        # 4. Get current prices
        prices_url = 'https://api.binance.com/api/v3/ticker/price'
        prices_response = requests.get(prices_url, timeout=3)
        prices = {p['symbol']: float(p['price']) for p in prices_response.json()}
        
        # 5. Calculate total value in USDT
        total_usdt = 0.0
        
        for b in data['balances']:
            free = float(b['free'])
            locked = float(b['locked'])
            total = free + locked
            
            if total < 0.001:
                continue
            
            asset = b['asset']
            
            if asset in ['USDT', 'BUSD', 'USDC']:
                total_usdt += total
                continue
            
            symbol = f'{asset}USDT'
            if symbol in prices:
                total_usdt += total * prices[symbol]
        
        # 6. Save cache
        with open(cache_file, 'w') as f:
            json.dump({'value': total_usdt, 'timestamp': time.time()}, f)
        
        print(f"💰 Portfolio from Binance (${total_usdt:.2f})")
        return total_usdt
        
    except Exception as e:
        print(f"❌ Error getting portfolio from Binance: {e}")
        cache_value = None
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    cache_value = float(json.load(f).get('value', 0))
            except Exception:
                cache_value = None
        if cache_value:
            print(f"⚠️  Usando cache local de portfolio: ${cache_value:.2f}")
            return cache_value
        # Fallback to snapshot
        try:
            snapshot_file = f"{WORKSPACE}/portfolio-snapshot.json"
            if os.path.exists(snapshot_file):
                with open(snapshot_file, 'r') as f:
                    data = json.load(f)
                    return float(data.get('value', 0))
        except Exception:
            pass
        return 0.0

def get_trade_states():
    """Obtener estado de trades para todas las coins"""
    cached = _get_mem_cache('trade_states')
    if cached is not None:
        return cached
    coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
    states = {}
    
    for coin in coins:
        state_file = f"{CRYPTO_BOTS}/{coin}-trade-state.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                
                # Normalizar entryPrice inválido en slots ACTIVOS
                slots = state.get('slots', [])
                for slot in slots:
                    status = slot.get('status', 'READY')
                    entry_price = slot.get('entryPrice')
                    
                    # Si entryPrice es null, 0, 0E-8, string vacío o NO válido, usar precio actual
                    if status == 'ACTIVE':
                        try:
                            ep = float(entry_price) if entry_price is not None else 0
                        except (TypeError, ValueError):
                            ep = 0
                        
                        if ep <= 0:
                            # Precio centralizado desde cache para evitar N requests
                            try:
                                prices = _get_mem_cache('binance_prices') or {}
                                current_price = float(prices.get(f'{coin}USDT', 0) or 0)
                            except Exception:
                                current_price = 0
                            if current_price > 0:
                                slot['entryPrice'] = current_price
                                slot['entryPriceNormalized'] = True
                
                states[coin] = state
            except Exception as e:
                print(f"Error reading {coin} state: {e}")
                states[coin] = {"status": "error"}
        else:
            states[coin] = {"status": "no_data"}
    
    _set_mem_cache('trade_states', states, ttl=2)
    return states

def get_trade_history():
    """Obtener historial de trades"""
    cached = _get_mem_cache('trade_history')
    if cached is not None:
        return cached
    history_file = f"{CRYPTO_BOTS}/trade-history.json"
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                data = json.load(f)
            trades = data.get('trades', [])
            trades = sorted(
                trades,
                key=lambda t: t.get('timestamp') or '',
                reverse=True
            )
            data['trades'] = trades
            _set_mem_cache('trade_history', data, ttl=5)
            return data
        except Exception as e:
            print(f"Error reading trade history: {e}")
    fallback = {
        "version": "1.0",
        "totalTrades": 0,
        "totalWins": 0,
        "totalLosses": 0,
        "netPnLUSDT": 0,
        "winRate": 0,
        "trades": []
    }
    _set_mem_cache('trade_history', fallback, ttl=5)
    return fallback

def get_grid_status():
    """🆕 Obtener status del Grid Trading Bot"""
    cached = _get_mem_cache('grid_status')
    if cached is not None:
        return cached
    grid_status_file = f"{WORKSPACE}/dashboard/grid-status.json"
    if os.path.exists(grid_status_file):
        try:
            with open(grid_status_file, 'r') as f:
                data = json.load(f)
                _set_mem_cache('grid_status', data, ttl=5)
                return data
        except Exception as e:
            print(f"Error reading grid status: {e}")
    fallback = {"status": "inactive", "totalBots": 0, "totalOrders": 0, "bots": {}}
    _set_mem_cache('grid_status', fallback, ttl=5)
    return fallback

def get_daily_pnl():
    """Calcular P&L de las últimas 24 horas + P&L no realizado de trades activos"""
    cached = _get_mem_cache('daily_pnl')
    if cached is not None:
        return cached
    try:
        from datetime import datetime, timedelta
        
        # Calcular fecha de hace 24 horas
        now = datetime.now()
        yesterday = now - timedelta(hours=24)
        
        total_pnl = 0.0
        pnl_by_coin = {}
        coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX']
        
        # Inicializar todas las monedas en 0
        for coin in coins:
            pnl_by_coin[coin] = 0.0
        
        # 1) PnL realizado desde trade-history.json
        history_file = f"{CRYPTO_BOTS}/trade-history.json"
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                data = json.load(f)
                trades = data.get('trades', [])
                
                for trade in trades:
                    close_time_str = trade.get('closeTime') or trade.get('timestamp')
                    if not close_time_str:
                        continue
                    
                    try:
                        close_time = datetime.fromisoformat(str(close_time_str).replace('Z', '+00:00'))
                        if close_time >= yesterday:
                            symbol = trade.get('symbol', 'UNKNOWN')
                            pnl = float(trade.get('pnlUSDT', trade.get('pnl', 0)) or 0)
                            total_pnl += pnl
                            pnl_by_coin[symbol] = pnl_by_coin.get(symbol, 0.0) + pnl
                    except Exception as e:
                        print(f"Error parsing date {close_time_str}: {e}")
                        continue
        
        # 2) PnL no realizado desde slots activos, usando precios cacheados centralizados
        prices = _get_mem_cache('binance_prices') or {}
        if not prices:
            try:
                import requests
                prices = {p['symbol']: float(p['price']) for p in requests.get('https://api.binance.com/api/v3/ticker/price', timeout=2).json()}
                _set_mem_cache('binance_prices', prices, ttl=2)
            except Exception:
                prices = {}
        for coin in coins:
            price_now = float(prices.get(f'{coin}USDT', 0) or 0)
            if not price_now:
                continue
            state_file = f"{CRYPTO_BOTS}/{coin}-trade-state.json"
            if not os.path.exists(state_file):
                continue
            try:
                state = json.loads(open(state_file).read())
            except Exception:
                continue
            active_slots = [s for s in state.get('slots', []) if s.get('status') == 'ACTIVE']
            for slot in active_slots:
                entry = float(slot.get('entryPrice', 0) or 0)
                qty = float(slot.get('quantity', 0) or 0)
                if entry <= 0 or qty <= 0:
                    continue
                pnl = (price_now - entry) * qty
                pnl_by_coin[coin] = pnl_by_coin.get(coin, 0.0) + pnl
                total_pnl += pnl
        
        # 3) Fluctuación real del Spot desde spot-registry.json
        registry_file = f"{CRYPTO_BOTS}/spot-registry.json"
        if os.path.exists(registry_file):
            try:
                registry = json.loads(open(registry_file).read())
                base_usdt = float(registry.get('total_usdt', 0) or 0)
                base_mxn = float(registry.get('total_mxn', 0) or 0)
                prices_base = registry.get('prices_base') or registry.get('prices_now', {})
                base_assets = registry.get('assets_mxn_base') or [
                    {'symbol': a.get('symbol'), 'mxn': a.get('mxn', 0)}
                    for a in registry.get('assets', [])
                ]
                spot_prices = registry.get('prices_now', {})
                mxn_rate = base_mxn / base_usdt if base_usdt > 0 else 17.0
                base_mxn_map = {a.get('symbol'): float(a.get('mxn', 0) or 0) for a in base_assets}
                for asset in registry.get('assets', []):
                    symbol = asset.get('symbol')
                    if symbol not in coins or symbol == 'USDT':
                        continue
                    balance = float(asset.get('balance', 0) or 0)
                    if balance <= 0:
                        continue
                    price_base = float(prices_base.get(symbol, 0) or 0)
                    price_now = float(spot_prices.get(symbol, asset.get('price_now', 0)) or 0)
                    mxn_now = balance * price_now * mxn_rate
                    mxn_base = base_mxn_map.get(symbol, mxn_now)
                    diff = mxn_now - mxn_base
                    pnl_by_coin[symbol] = pnl_by_coin.get(symbol, 0.0) + diff / mxn_rate
                    total_pnl += diff / mxn_rate
            except Exception as e:
                print(f"[PNL] Error applying spot-registry fluctuation: {e}")
        
        print(f"📊 24H P&L calculado: ${total_pnl:.2f} USDT")
        print(f"📊 P&L por moneda: {pnl_by_coin}")
        
        result = (round(total_pnl, 2), {k: round(v, 2) for k, v in pnl_by_coin.items()})
        _set_mem_cache('daily_pnl', result, ttl=5)
        return result
    except Exception as e:
        print(f"Error calculating daily PnL: {e}")
        return 0.0, {}

def get_cashout_history():
    """Obtener historial de cashouts"""
    cashout_file = f"{CRYPTO_BOTS}/cashout-history.json"
    if os.path.exists(cashout_file):
        try:
            with open(cashout_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cashout history: {e}")
    
    return {"cashouts": [], "totalUSDT": 0, "totalMXN": 0}

def get_market_mode():
    """Obtener modo de mercado actual"""
    # Primero intentar dynamic-config.env (tiene ML overrides)
    config_file = f"{CRYPTO_BOTS}/dynamic-config.env"
    fallback_file = f"{CRYPTO_BOTS}/market-mode.conf"
    
    # Usar dynamic-config.env si existe (tiene config real que usa el bot)
    if not os.path.exists(config_file):
        config_file = fallback_file
    
    if os.path.exists(config_file):
        try:
            mode_data = {}
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        # Remover 'export ' si existe (bash script format)
                        line = line.replace('export ', '').strip()
                        key, value = line.split('=', 1)
                        mode_data[key.strip()] = value.strip().strip('"')
            return mode_data
        except Exception as e:
            print(f"Error reading market mode: {e}")
    
    return {"MARKET_MODE": "LATERAL", "TP1": "2.5", "TP2": "5.0", "TP3": "7.0", "SL": "5.0"}

def _load_circuit_breaker_status():
    """Leer estado del Circuit Breaker desde el archivo de estado"""
    try:
        status_file = os.path.join(CRYPTO_BOTS, 'dashboard-circuit-breaker-status.json')
        if not os.path.exists(status_file):
            return {
                'circuitBreakerActive': False,
                'status': 'NORMAL',
                'pauseUntil': None,
                'triggeredBy': None,
                'message': 'CB OFF'
            }
        with open(status_file, 'r') as f:
            data = json.load(f)
        return {
            'circuitBreakerActive': bool(data.get('circuitBreakerActive', False)),
            'status': data.get('status', 'NORMAL'),
            'pauseUntil': data.get('pauseUntil'),
            'triggeredBy': data.get('triggeredBy'),
            'message': data.get('message', 'CB OFF')
        }
    except Exception as e:
        print(f"Error reading circuit breaker status: {e}")
        return {
            'circuitBreakerActive': False,
            'status': 'NORMAL',
            'pauseUntil': None,
            'triggeredBy': None,
            'message': 'CB OFF'
        }

# ════════════════════════════════════════════════════════
# RUTAS
# ════════════════════════════════════════════════════════

@app.route('/')
@requires_auth
def index():
    if is_mobile_device():
        return render_template('mobile.html')
    else:
        return render_template('index.html')

@app.route('/api/portfolio')
def api_portfolio():
    """API endpoint para valor del portfolio"""
    import os, json
    
    value = get_portfolio_value()
    
    # Leer tasa MXN del cache si existe
    mxn_rate = 17.5  # fallback
    cache_file = "/tmp/portfolio_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache = json.load(f)
                mxn_rate = cache.get('mxn_rate', get_mxn_rate())
        except:
            mxn_rate = get_mxn_rate()
    else:
        mxn_rate = get_mxn_rate()
    
    return jsonify({
        'value': value,
        'value_mx': round(mxn_rate * value, 2),
        'mxn_rate': mxn_rate,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/status')
def api_status():
    """API endpoint para estado completo"""
    portfolio_value = get_portfolio_value()
    trade_states = get_trade_states()
    trade_history = get_trade_history()
    daily_pnl, pnl_by_coin = get_daily_pnl()
    cashout_history = get_cashout_history()
    market_mode = get_market_mode()
    grid_status = get_grid_status()  # 🆕 Grid Trading Status
    
    # Calcular slots activos
    active_slots = 0
    ready_slots = 0
    
    for coin, state in trade_states.items():
        slots = state.get('slots', [])
        for slot in slots:
            status = slot.get('status', 'READY')
            if status == 'ACTIVE':
                active_slots += 1
            else:
                ready_slots += 1
    
    total_slots = active_slots + ready_slots
    
    # Verificar API Binance
    try:
        import requests
        test_url = 'https://api.binance.com/api/v3/ping'
        requests.get(test_url, timeout=2)
        api_binance = 'ok'
    except:
        api_binance = 'error'
    
    # Obtener IP pública
    try:
        import requests
        ip_response = requests.get('https://ifconfig.me', timeout=2)
        public_ip = ip_response.text.strip()
    except:
        public_ip = 'error'
    
    # Verificar Gateway (Ollama)
    try:
        import requests
        gateway_url = 'http://localhost:11434/api/tags'
        requests.get(gateway_url, timeout=2)
        gateway = 'ok'
    except:
        gateway = 'error'
    
    # Calcular próximo auto-ajuste (cada 6 horas)
    from datetime import datetime, timedelta
    now = datetime.now()
    # Próxima hora múltiplo de 6 (0, 6, 12, 18)
    next_adjustment = ((now.hour // 6) + 1) * 6
    if next_adjustment >= 24:
        next_adjustment = 0
        next_date = now.date() + timedelta(days=1)
    else:
        next_date = now.date()
    
    next_adjustment_dt = datetime.combine(next_date, datetime.min.time().replace(hour=next_adjustment))
    time_until = next_adjustment_dt - now
    seconds_until = int(time_until.total_seconds())
    hours_until = seconds_until // 3600
    minutes_until = (seconds_until % 3600) // 60
    
    return jsonify({
        'portfolio': {
            'value': portfolio_value,
            'value_mx': portfolio_value * get_mxn_rate(),
            'pnl_24h': round(daily_pnl, 2),
            'pnl_24h_percent': round((daily_pnl / portfolio_value * 100) if portfolio_value > 0 else 0, 2),
            'pnl_by_coin': pnl_by_coin
        },
        'slots': {
            'total': total_slots,
            'active': active_slots,
            'ready': ready_slots,
            'percentage': round((active_slots / total_slots * 100) if total_slots > 0 else 0, 1)
        },
        'grid': {  # 🆕 Grid Trading Status
            'status': grid_status.get('status', 'inactive'),
            'totalBots': grid_status.get('totalBots', 0),
            'totalOrders': grid_status.get('totalOrders', 0),
            'bots': grid_status.get('bots', {}),
            'tradesExecuted': grid_status.get('tradesExecuted', 0),
            'totalPnL': grid_status.get('totalPnL', 0.00)
        },
        'pnl': {
            '24h': daily_pnl,
            '24h_percent': round((daily_pnl / portfolio_value * 100) if portfolio_value > 0 else 0, 2),
            'by_coin': pnl_by_coin
        },
        'history': {
            'total_trades': trade_history.get('totalTrades', 0),
            'win_rate': round(
                sum(1 for t in trade_history.get('trades', []) if t.get('pnlUSDT') is not None and t['pnlUSDT'] > 0)
                / max(sum(1 for t in trade_history.get('trades', []) if t.get('pnlUSDT') is not None), 1)
                * 100,
                2
            ),
            'net_pnl': trade_history.get('netPnLUSDT', 0),
            'trades': (trade_history.get('trades', []) or [])[:10]
        },
        'cashout': {
            'total_usdt': cashout_history.get('totalUSDT', 0),
            'total_mxn': cashout_history.get('totalMXN', 0)
        },
        'market_mode': market_mode,
        'tradeStates': trade_states,
        'system': {
            'api_binance': api_binance,
            'ip_whitelist': public_ip,
            'gateway': gateway
        },
        'auto_adjust': {
            'next_adjustment': next_adjustment_dt.isoformat(),
            'hours_until': hours_until,
            'minutes_until': minutes_until,
            'interval_hours': 6
        },
        'circuitBreakerStatus': _load_circuit_breaker_status(),
        'timestamp': now.isoformat()
    })

@app.route('/api/prices')
def api_prices():
    """API endpoint para precios en tiempo real (OPTIMIZADO)"""
    try:
        import requests
        
        # UNA SOLA llamada a Binance para nuestras monedas
        symbols = ['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','LINKUSDT','XRPUSDT','AVAXUSDT']
        url = 'https://api.binance.com/api/v3/ticker/24hr?symbol=' + '&symbol='.join(symbols)
        response = requests.get(url, timeout=3)
        all_tickers = response.json()
        
        prices = {}
        for ticker in all_tickers:
            symbol = ticker.get('symbol', '')
            coin = symbol.replace('USDT', '')
            prices[coin] = {
                'price': float(ticker.get('lastPrice', 0)),
                'change_24h': float(ticker.get('priceChangePercent', 0)),
                'volume': float(ticker.get('volume', 0)),
                'high': float(ticker.get('highPrice', 0)),
                'low': float(ticker.get('lowPrice', 0))
            }
        
        return jsonify(prices)
        
    except Exception as e:
        print(f"Error getting prices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades')
def api_trades():
    """API endpoint para historial de trades"""
    history = get_trade_history()
    return jsonify(history)

# ════════════════════════════════════════════════════════
# 🔊 TEST SOUND PAGE
# ════════════════════════════════════════════════════════

@app.route("/test-sound")
def test_sound():
    """Test page for cash register sound"""
    return render_template("test-sound.html")

@app.route('/atom')
def atom_page():
    return render_template('atom.html')

@app.route('/api/atom/price')
def api_atom_price():
    try:
        with open('/tmp/atom_price_check.json') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception:
        return jsonify({'error':'no_price'}), 404

@app.route('/api/atom/events')
def api_atom_events():
    try:
        with open('/tmp/atom_events_watch.json') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception:
        return jsonify({'error':'no_events'}), 404

@app.route('/api/atom/news')
def api_atom_news():
    try:
        with open('/tmp/atom_weekly_news.json') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception:
        return jsonify({'error':'no_news'}), 404

@app.route('/crypto-bots/<path:filename>')
def serve_crypto_bot_file(filename):
    """Servir archivos desde crypto-bots/ (reportes, notificaciones, etc.)"""
    return send_from_directory(
        os.path.join(WORKSPACE, 'crypto-bots'),
        filename
    )

@app.route('/api/notify-tp', methods=['POST'])
def notify_tp():
    """Endpoint para que TP Monitor notifique TP hits y active sonido en dashboard"""
    import os
    data = request.json
    coin = data.get('coin', 'UNKNOWN')
    slot_id = data.get('slot_id', 0)
    tp_type = data.get('tp', 'TP')
    pnl = data.get('pnl', 0)
    
    # Log para que el frontend pueda detectar y reproducir sonido
    log_file = os.path.join(WORKSPACE, 'crypto-bots', 'tp-notifications.json')
    
    notifications = []
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                notifications = json.load(f)
        except:
            pass
    
    # Agregar nueva notificación
    notifications.append({
        'coin': coin,
        'slot_id': slot_id,
        'tp': tp_type,
        'pnl': pnl,
        'timestamp': datetime.now().isoformat(),
        'played': False  # Flag para que el frontend sepa que debe reproducir
    })
    
    # Mantener solo las últimas 10 notificaciones
    notifications = notifications[-10:]
    
    with open(log_file, 'w') as f:
        json.dump(notifications, f, indent=2)
    
    return jsonify({'status': 'ok', 'message': f'TP {tp_type} detected for {coin} Slot {slot_id}'})

@app.route('/crypto-bots/tp-notifications.json', methods=['POST'])
def update_tp_notifications():
    """Endpoint para limpiar/actualizar notificaciones TP"""
    import os
    data = request.json or []
    
    log_file = os.path.join(WORKSPACE, 'crypto-bots', 'tp-notifications.json')
    
    # Guardar solo notificaciones no jugadas (limpieza)
    with open(log_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    return jsonify({'status': 'ok', 'count': len(data)})



if __name__ == '__main__':
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🐕 PERROBOTILLO DASHBOARD - STARTING                 ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    print(f"📁 Workspace: {WORKSPACE}")
    print(f"🔐 Auth file: {AUTH_FILE}")
    print()
    print("🚀 Starting Flask server on port 8080...")
    print()
    app.run(host='0.0.0.0', port=8080, debug=False)

