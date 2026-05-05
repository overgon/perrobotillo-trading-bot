#!/bin/bash
# ════════════════════════════════════════════════════════
# 🧪 Perrobotillo Backtesting Engine
# ════════════════════════════════════════════════════════
# Uso: ./run-backtest.sh [SYMBOL] [START_DATE] [END_DATE]
# Ejemplo: ./run-backtest.sh BTCUSDT 2025-11-01 2026-05-04
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
DATA_DIR="${SCRIPT_DIR}/data"
RESULTS_DIR="${SCRIPT_DIR}/results"

# Crear directorios
mkdir -p "$DATA_DIR" "$RESULTS_DIR"

# Parámetros por defecto
SYMBOL="${1:-BTCUSDT}"
START_DATE="${2:-2025-11-01}"
END_DATE="${3:-2026-05-04}"

echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🧪 PERROBOTILLO BACKTESTING ENGINE                   ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "📊 Símbolo: $SYMBOL"
echo "📅 Período: $START_DATE → $END_DATE"
echo "💰 Capital inicial: \$1000 USDT (simulado)"
echo ""

# ════════════════════════════════════════════════════════
# PASO 1: DESCARGAR DATOS HISTÓRICOS
# ════════════════════════════════════════════════════════

echo "⏳ Paso 1/5: Descargando datos históricos..."

python3 << PYEOF
import requests
import pandas as pd
from datetime import datetime
import time

symbol = "$SYMBOL"
start_date = "$START_DATE"
end_date = "$END_DATE"
data_dir = "$DATA_DIR"

print(f"   Descargando datos de {symbol}...")

# Convertir fechas a timestamp
start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)

# Descargar datos de Binance (1d timeframe)
url = "https://api.binance.com/api/v3/klines"
params = {
    'symbol': symbol,
    'interval': '1d',
    'startTime': start_ts,
    'endTime': end_ts,
    'limit': 500
}

try:
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    
    if isinstance(data, list):
        # Convertir a DataFrame
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # Convertir tipos
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Guardar
        df.to_csv(f"{data_dir}/{symbol}_historical.csv", index=False)
        print(f"   ✅ {len(df)} días descargados")
        print(f"   📁 Guardado en: {data_dir}/{symbol}_historical.csv")
        
        # Mostrar estadísticas
        print(f"\n   📊 Estadísticas del período:")
        print(f"      Precio inicial: \${df['open'].iloc[0]:.2f}")
        print(f"      Precio final: \${df['close'].iloc[-1]:.2f}")
        print(f"      Máximo: \${df['high'].max():.2f}")
        print(f"      Mínimo: \${df['low'].min():.2f}")
        print(f"      Cambio: {((df['close'].iloc[-1] / df['open'].iloc[0]) - 1) * 100:.2f}%")
    else:
        print(f"   ❌ Error: {data}")
except Exception as e:
    print(f"   ❌ Error: {e}")

PYEOF

# ════════════════════════════════════════════════════════
# PASO 2: CALCULAR INDICADORES TÉCNICOS
# ════════════════════════════════════════════════════════

echo ""
echo "⏳ Paso 2/5: Calculando indicadores técnicos..."

python3 << PYEOF
import pandas as pd
import numpy as np

symbol = "$SYMBOL"
data_dir = "$DATA_DIR"

try:
    df = pd.read_csv(f"{data_dir}/{symbol}_historical.csv")
    
    # Calcular indicadores
    print("   Calculando indicadores...")
    
    # EMAs
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
    df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
    df['bb_width'] = ((df['bb_upper'] - df['bb_lower']) / df['bb_middle']) * 100
    
    # Volatilidad
    df['volatility'] = df['close'].pct_change().rolling(window=20).std() * 100
    
    # Guardar
    df.to_csv(f"{data_dir}/{symbol}_indicators.csv", index=False)
    print(f"   ✅ Indicadores calculados")
    print(f"   📁 Guardado en: {data_dir}/{symbol}_indicators.csv")
    
    # Mostrar últimos valores
    print(f"\n   📊 Últimos indicadores:")
    last = df.iloc[-1]
    print(f"      EMA20: \${last['ema_20']:.2f}")
    print(f"      EMA50: \${last['ema_50']:.2f}")
    print(f"      RSI: {last['rsi']:.2f}")
    print(f"      MACD: {last['macd']:.4f}")
    print(f"      BB Width: {last['bb_width']:.2f}%")
    print(f"      Volatility: {last['volatility']:.2f}%")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

PYEOF

# ════════════════════════════════════════════════════════
# PASO 3: DESCARGAR FEAR & GREED
# ════════════════════════════════════════════════════════

echo ""
echo "⏳ Paso 3/5: Obteniendo Fear & Greed Index..."

python3 << PYEOF
import requests
import pandas as pd
from datetime import datetime, timedelta

data_dir = "$DATA_DIR"

print("   Descargando Fear & Greed Index...")

try:
    # Alternative.me API
    url = "https://api.alternative.me/fng/"
    params = {'limit': 365, 'format': 'json'}
    
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    
    if data['status'] == 'success':
        # Convertir a DataFrame
        df = pd.DataFrame(data['data'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.rename(columns={'value': 'fng_value', 'value_classification': 'fng_class'})
        
        # Guardar
        df.to_csv(f"{data_dir}/fear_greed.csv", index=False)
        print(f"   ✅ {len(df)} días descargados")
        print(f"   📁 Guardado en: {data_dir}/fear_greed.csv")
        
        # Mostrar últimos valores
        print(f"\n   📊 Fear & Greed actual:")
        last = df.iloc[-1]
        print(f"      Valor: {last['fng_value']} ({last['fng_class']})")
    else:
        print(f"   ⚠️  No se pudo descargar Fear & Greed")
        
except Exception as e:
    print(f"   ⚠️  Error: {e}")

PYEOF

# ════════════════════════════════════════════════════════
# PASO 4: EJECUTAR BACKTEST
# ════════════════════════════════════════════════════════

echo ""
echo "⏳ Paso 4/5: Ejecutando backtesting..."

python3 << PYEOF
import pandas as pd
import numpy as np
from datetime import datetime

symbol = "$SYMBOL"
data_dir = "$DATA_DIR"
results_dir = "$RESULTS_DIR"

print("   Cargando datos...")

# Cargar datos
try:
    df = pd.read_csv(f"{data_dir}/{symbol}_indicators.csv")
    fng = pd.read_csv(f"{data_dir}/fear_greed.csv")
    
    # Merge con Fear & Greed
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    fng['date'] = pd.to_datetime(fng['timestamp']).dt.date
    df = df.merge(fng[['date', 'fng_value']], on='date', how='left')
    df['fng_value'] = df['fng_value'].fillna(50)  # Default neutral
    
    print(f"   ✅ {len(df)} días de datos")
    
    # ════════════════════════════════════════════════════
    # ESTRATEGIAS A TESTEAR
    # ════════════════════════════════════════════════════
    
    strategies = {
        'Actual (FASE 1 v2.1)': {
            'tp1': 2.5, 'tp2': 5.0, 'tp3': 8.0, 'sl': 5.5,
            'position_size': 0.20, 'trailing': False
        },
        'Optimizada Bull': {
            'tp1': 3.0, 'tp2': 6.0, 'tp3': 10.0, 'sl': 8.0,
            'position_size': 0.25, 'trailing': True
        },
        'Optimizada Bear': {
            'tp1': 2.0, 'tp2': 4.0, 'tp3': 6.0, 'sl': 4.0,
            'position_size': 0.15, 'trailing': False
        },
        'Optimizada Lateral': {
            'tp1': 2.5, 'tp2': 5.0, 'tp3': 7.0, 'sl': 5.0,
            'position_size': 0.20, 'trailing': False
        },
        'Dinámica (Auto-Ajuste)': {
            'adaptive': True  # Se ajusta según mercado
        }
    }
    
    # ════════════════════════════════════════════════════
    # MOTOR DE BACKTEST
    # ════════════════════════════════════════════════════
    
    def run_backtest(df, strategy_name, config):
        initial_capital = 1000.0
        capital = initial_capital
        trades = []
        equity = [initial_capital]
        
        in_position = False
        entry_price = 0
        position_size = 0
        tp1_hit = False
        tp2_hit = False
        
        for i in range(100, len(df)):  # Empezar después de tener indicadores
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            
            # Determinar modo de mercado
            fng = row['fng_value']
            price = row['close']
            ema20 = row['ema_20']
            rsi = row['rsi']
            bb_width = row['bb_width']
            
            # Estrategia dinámica
            if config.get('adaptive'):
                if fng > 60 and price > ema20:
                    # Bull market
                    tp1, tp2, tp3, sl, pos_size = 3.0, 6.0, 10.0, 8.0, 0.25
                elif fng < 40 and price < ema20:
                    # Bear market
                    tp1, tp2, tp3, sl, pos_size = 2.0, 4.0, 6.0, 4.0, 0.15
                else:
                    # Lateral
                    tp1, tp2, tp3, sl, pos_size = 2.5, 5.0, 7.0, 5.0, 0.20
            else:
                tp1 = config['tp1']
                tp2 = config['tp2']
                tp3 = config['tp3']
                sl = config['sl']
                pos_size = config['position_size']
            
            # Señales de entrada
            if not in_position:
                # Entrada: RSI < 35 (oversold) o precio cruza EMA20 hacia arriba
                if (rsi < 35 or (prev_row['close'] < prev_row['ema_20'] and price > ema20)):
                    # Verificar que hay capital
                    if capital >= 10:  # Mínimo $10
                        in_position = True
                        entry_price = price
                        position_size = capital * pos_size
                        tp1_hit = False
                        tp2_hit = False
                        trades.append({
                            'date': row['timestamp'],
                            'type': 'BUY',
                            'price': entry_price,
                            'size': position_size
                        })
            
            # Señales de salida
            elif in_position:
                pnl_pct = ((price - entry_price) / entry_price) * 100
                
                # Stop Loss
                if pnl_pct <= -sl:
                    capital += position_size * (1 + pnl_pct / 100)
                    trades.append({
                        'date': row['timestamp'],
                        'type': 'SL',
                        'price': price,
                        'pnl': pnl_pct,
                        'capital': capital
                    })
                    in_position = False
                
                # TP1 (35% de la posición)
                elif not tp1_hit and pnl_pct >= tp1:
                    capital += position_size * 0.35 * (1 + tp1 / 100)
                    tp1_hit = True
                    trades.append({
                        'date': row['timestamp'],
                        'type': 'TP1',
                        'price': price,
                        'pnl': tp1,
                        'capital': capital
                    })
                
                # TP2 (30% de la posición)
                elif tp1_hit and not tp2_hit and pnl_pct >= tp2:
                    capital += position_size * 0.30 * (1 + tp2 / 100)
                    tp2_hit = True
                    trades.append({
                        'date': row['timestamp'],
                        'type': 'TP2',
                        'price': price,
                        'pnl': tp2,
                        'capital': capital
                    })
                
                # TP3 (35% restante)
                elif tp2_hit and pnl_pct >= tp3:
                    capital += position_size * 0.35 * (1 + tp3 / 100)
                    trades.append({
                        'date': row['timestamp'],
                        'type': 'TP3',
                        'price': price,
                        'pnl': tp3,
                        'capital': capital
                    })
                    in_position = False
            
            equity.append(capital)
        
        # Calcular métricas
        trades_df = pd.DataFrame(trades)
        
        if len(trades_df) == 0:
            return None
        
        # Separar trades completos (con salida)
        exit_trades = trades_df[trades_df['type'].isin(['SL', 'TP1', 'TP2', 'TP3'])]
        
        if len(exit_trades) == 0:
            return None
        
        # Métricas
        total_trades = len(exit_trades)
        winning_trades = len(exit_trades[exit_trades['pnl'] > 0])
        losing_trades = len(exit_trades[exit_trades['pnl'] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        gross_profit = exit_trades[exit_trades['pnl'] > 0]['pnl'].sum() if len(exit_trades[exit_trades['pnl'] > 0]) > 0 else 0
        gross_loss = abs(exit_trades[exit_trades['pnl'] < 0]['pnl'].sum()) if len(exit_trades[exit_trades['pnl'] < 0]) > 0 else 0
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        total_return = ((capital - initial_capital) / initial_capital) * 100
        
        # Drawdown
        equity_df = pd.DataFrame(equity)
        rolling_max = equity_df.expanding().max()
        drawdowns = (equity_df - rolling_max) / rolling_max * 100
        max_drawdown = abs(drawdowns.min())
        
        # Avg Win/Loss
        avg_win = exit_trades[exit_trades['pnl'] > 0]['pnl'].mean() if len(exit_trades[exit_trades['pnl'] > 0]) > 0 else 0
        avg_loss = abs(exit_trades[exit_trades['pnl'] < 0]['pnl'].mean()) if len(exit_trades[exit_trades['pnl'] < 0]) > 0 else 0
        
        return {
            'strategy': strategy_name,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'total_return': total_return,
            'final_capital': capital,
            'max_drawdown': max_drawdown,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'equity_curve': equity
        }
    
    # Ejecutar backtest para cada estrategia
    print("\n   Ejecutando backtests...")
    results = []
    
    for name, config in strategies.items():
        print(f"      Testing: {name}...")
        result = run_backtest(df, name, config)
        if result:
            results.append(result)
    
    # Guardar resultados
    if results:
        results_df = pd.DataFrame(results)
        results_df.to_csv(f"{results_dir}/{symbol}_backtest_results.csv", index=False)
        print(f"\n   ✅ Backtest completado")
        print(f"   📁 Resultados: {results_dir}/{symbol}_backtest_results.csv")
        
        # Mostrar resumen
        print(f"\n" + "="*60)
        print("📊 RESULTADOS DEL BACKTEST")
        print("="*60)
        
        for r in results:
            print(f"\n📈 {r['strategy']}:")
            print(f"   Trades: {r['total_trades']}")
            print(f"   Win Rate: {r['win_rate']:.2f}%")
            print(f"   Profit Factor: {r['profit_factor']:.2f}")
            print(f"   Total Return: {r['total_return']:.2f}%")
            print(f"   Max Drawdown: {r['max_drawdown']:.2f}%")
            print(f"   Final Capital: \${r['final_capital']:.2f}")
        
        # Encontrar la mejor estrategia
        best = max(results, key=lambda x: x['total_return'])
        print(f"\n🏆 MEJOR ESTRATEGIA: {best['strategy']}")
        print(f"   Retorno: {best['total_return']:.2f}%")
        print(f"   Win Rate: {best['win_rate']:.2f}%")
        
    else:
        print(f"   ❌ No se generaron resultados")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

PYEOF

# ════════════════════════════════════════════════════════
# PASO 5: GENERAR REPORTE
# ════════════════════════════════════════════════════════

echo ""
echo "⏳ Paso 5/5: Generando reporte..."

python3 << PYEOF
import pandas as pd
from datetime import datetime

symbol = "$SYMBOL"
results_dir = "$RESULTS_DIR"

try:
    results_df = pd.read_csv(f"{results_dir}/{symbol}_backtest_results.csv")
    
    # Crear reporte
    report = f"""
# 🧪 BACKTEST REPORT - {symbol}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Period:** $START_DATE to $END_DATE

## 📊 SUMMARY

| Strategy | Trades | Win Rate | Profit Factor | Return | Max DD |
|----------|--------|----------|---------------|--------|--------|
"""
    
    for _, row in results_df.iterrows():
        report += f"| {row['strategy']} | {row['total_trades']} | {row['win_rate']:.2f}% | {row['profit_factor']:.2f} | {row['total_return']:.2f}% | {row['max_drawdown']:.2f}% |\n"
    
    # Mejor estrategia
    best = results_df.loc[results_df['total_return'].idxmax()]
    report += f"""

## 🏆 BEST STRATEGY: {best['strategy']}

- **Total Return:** {best['total_return']:.2f}%
- **Win Rate:** {best['win_rate']:.2f}%
- **Profit Factor:** {best['profit_factor']:.2f}
- **Max Drawdown:** {best['max_drawdown']:.2f}%
- **Total Trades:** {best['total_trades']}

## 📈 RECOMMENDATION

Based on this backtest, the **{best['strategy']}** strategy shows the best performance
with a {best['total_return']:.2f}% return and {best['win_rate']:.2f}% win rate.

---
*Report generated by Perrobotillo Backtesting Engine*
"""
    
    # Guardar reporte
    with open(f"{results_dir}/{symbol}_report.md", 'w') as f:
        f.write(report)
    
    print(f"   ✅ Reporte generado: {results_dir}/{symbol}_report.md")
    print("\n" + report)
    
except Exception as e:
    print(f"   ❌ Error: {e}")

PYEOF

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  ✅ BACKTESTING COMPLETADO                            ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "📁 Resultados en: ${RESULTS_DIR}/"
echo ""
