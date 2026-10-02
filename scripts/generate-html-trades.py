#!/usr/bin/env python3
"""
Genera las cards de trades cerrados para el reporte HTML
"""
import json
import sys

def generate_trade_cards(trades_json):
    """Genera HTML para las cards de trades"""
    try:
        trades = json.loads(trades_json)
        html = ""
        
        for trade in trades:
            pnl = float(trade.get('pnlUSDT', 0))
            pnl_class = "positive" if pnl >= 0 else "negative"
            pnl_sign = "+" if pnl >= 0 else ""
            
            html += f"""
        <div class="trade-card">
            <div class="trade-header">
                <div><strong>{trade['symbol']}/USDT</strong> - Slot {trade['slotId']} - {trade['type']}</div>
                <div class="trade-pnl {pnl_class}">{pnl_sign}${pnl:.2f}</div>
            </div>
            <table style="margin: 0;">
                <tr><td>Entry:</td><td>${float(trade['entryPrice']):.2f}</td><td>Exit:</td><td>${float(trade['exitPrice']):.2f}</td></tr>
                <tr><td>Quantity:</td><td>{trade['quantity']}</td><td>Close Type:</td><td>{trade['closeType']}</td></tr>
                <tr><td>Time:</td><td colspan="3">{trade['closeTime']}</td></tr>
            </table>
        </div>
"""
        return html
    except Exception as e:
        return f"<!-- Error: {e} -->"

if __name__ == "__main__":
    import os
    # Leer de variable de entorno
    trades_json = os.environ.get('TRADES_JSON', '[]')
    print(generate_trade_cards(trades_json))
