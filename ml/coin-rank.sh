#!/bin/bash
# ════════════════════════════════════════════════════════
# 🪙 Coin Ranker - Wrapper Bash
# ════════════════════════════════════════════════════════
# Muestra ranking de coins o verifica status de una coin
# Uso: ./coin-rank.sh [SYMBOL]
# ════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
RANKING_FILE="${SCRIPT_DIR}/coin-ranking.json"

# Si pasa SYMBOL, verifica esa coin
if [ -n "$1" ]; then
    SYMBOL="$1"
    
    if [ -f "$RANKING_FILE" ]; then
        python3 << PYEOF
import json
with open('$RANKING_FILE', 'r') as f:
    data = json.load(f)

stats = data['stats'].get('$SYMBOL', {})
suggestions = data['suggestions']

if not stats:
    print(f"❌ No hay datos para $SYMBOL")
else:
    print(f"\n🪙 $SYMBOL - ESTADÍSTICAS:")
    print(f"   Trades: {stats['total_trades']}")
    print(f"   Win Rate: {stats['win_rate']:.1%} ({stats['wins']}/{stats['total_trades']})")
    print(f"   P&L Total: \${stats['total_pnl']:.2f}")
    print(f"   Win Rate 24h: {stats['win_rate_24h']:.0%} ({stats['trades_24h']} trades)")
    print(f"   P&L 24h: \${stats['pnl_24h']:.2f}")
    
    # Verificar sugerencia
    action = "NORMAL"
    for category, items in suggestions.items():
        for item in items:
            if item['coin'] == '$SYMBOL':
                action = category.upper().replace('_', ' ')
                reason = item['reason']
    
    print(f"\n   💡 Acción: {action}")
    if 'reason' in locals():
        print(f"      {reason}")
PYEOF
    else
        echo "❌ No hay ranking generado. Ejecutá: python3 coin-ranker.py"
    fi
else
    # Sin argumento → mostrar ranking completo
    python3 "${SCRIPT_DIR}/coin-ranker.py"
fi
