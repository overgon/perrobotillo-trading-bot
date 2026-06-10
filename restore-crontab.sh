#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - RESTAURAR CRONTAB COMPLETO
# ════════════════════════════════════════════════════════
# Fecha: Junio 10, 2026
# Restaurar todos los cron jobs después de optimización
# ════════════════════════════════════════════════════════

cat << 'EOF' | crontab -
# ════════════════════════════════════════════════════════
# Perrobotillo Trading Bot - Crontab Completo
# Actualizado: Junio 10, 2026 - Optimización Cero LLM
# ════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════
# SLOT HEALBOT - Cada 10 min (LOCAL, SIN LLM)
# ════════════════════════════════════════════════════════
*/10 * * * * /home/overgon/.openclaw/workspace/crypto-bots/run-slot-healbot.sh >> /home/overgon/.openclaw/logs/auto-heal.log 2>&1

# ════════════════════════════════════════════════════════
# AUTO-ADJUST STRATEGY - Cada 6 horas (con ML validation)
# ════════════════════════════════════════════════════════
0 */6 * * * /home/overgon/.openclaw/workspace/crypto-bots/auto-adjust-strategy.sh >> /home/overgon/.openclaw/logs/auto-adjust.log 2>&1

# ════════════════════════════════════════════════════════
# FAN CONTROL - Cada 2 minutos
# ════════════════════════════════════════════════════════
*/2 * * * * /home/overgon/.openclaw/workspace/scripts/fan-control.sh >> /home/overgon/.openclaw/logs/fan-control.log 2>&1

# ════════════════════════════════════════════════════════
# DRAWDOWN ALERT - Cada 30 minutos
# ════════════════════════════════════════════════════════
*/30 * * * * /home/overgon/.openclaw/workspace/check-drawdown-alert.sh >> /home/overgon/.openclaw/logs/drawdown-cron.log 2>&1

# ════════════════════════════════════════════════════════
# PROACTIVE ALERTS - Cada 30 minutos
# ════════════════════════════════════════════════════════
*/30 * * * * /home/overgon/.openclaw/workspace/crypto-bots/proactive-alerts.sh >> /home/overgon/.openclaw/logs/proactive-alerts.log 2>&1

# ════════════════════════════════════════════════════════
# PUBLIC IP MONITOR - Cada hora
# ════════════════════════════════════════════════════════
0 * * * * /home/overgon/.openclaw/workspace/check-public-ip.sh >> /home/overgon/.openclaw/logs/ip-monitor-cron.log 2>&1

# ════════════════════════════════════════════════════════
# BINANCE MAINTENANCE MONITOR - Cada 4 horas
# ════════════════════════════════════════════════════════
0 */4 * * * /home/overgon/.openclaw/workspace/scripts/binance-maintenance-monitor.sh >> /home/overgon/.openclaw/logs/binance-maintenance.log 2>&1

# ════════════════════════════════════════════════════════
# DAILY REPORT - 9 AM
# ════════════════════════════════════════════════════════
0 9 * * * /home/overgon/.openclaw/workspace/daily-report-9am.sh >> /home/overgon/.openclaw/logs/daily-report.log 2>&1

# ════════════════════════════════════════════════════════
# AUTO CAPITAL MANAGER - Diario 9 AM
# ════════════════════════════════════════════════════════
0 9 * * * /home/overgon/.openclaw/workspace/scripts/auto-capital-manager.sh >> /home/overgon/.openclaw/logs/auto-capital-manager.log 2>&1

# ════════════════════════════════════════════════════════
# MONTHLY REPORT - Día 1, 9 AM
# ════════════════════════════════════════════════════════
0 9 1 * * /home/overgon/.openclaw/workspace/scripts/monthly-report.sh >> /home/overgon/.openclaw/logs/monthly-report-cron.log 2>&1

# ════════════════════════════════════════════════════════
# ML AUTO-RETRAIN V2 - Domingos 3 AM
# ════════════════════════════════════════════════════════
0 3 * * 0 cd /home/overgon/.openclaw/workspace/ml && source ../venv/bin/activate && python3 auto-retrain-v2.py >> /home/overgon/.openclaw/logs/ml-auto-retrain.log 2>&1

# ════════════════════════════════════════════════════════
# ML RETRAIN STATUS REPORT - Domingos 9 AM
# ════════════════════════════════════════════════════════
0 9 * * 0 /home/overgon/.openclaw/workspace/scripts/ml-retrain-report.sh >> /home/overgon/.openclaw/logs/ml-retrain-report-cron.log 2>&1

# ════════════════════════════════════════════════════════
# PORTFOLIO REBALANCING - Domingos 11 PM
# ════════════════════════════════════════════════════════
0 23 * * 0 cd /home/overgon/.openclaw/workspace && ./scripts/portfolio-rebalance.sh rebalance >> /home/overgon/.openclaw/logs/portfolio-rebalance-cron.log 2>&1

# ════════════════════════════════════════════════════════
# TRAILING STOPS ATR UPDATE - Cada 2 horas
# ════════════════════════════════════════════════════════
0 */2 * * * cd /home/overgon/.openclaw/workspace && ./scripts/update-trailing-stops.sh >> /home/overgon/.openclaw/logs/trailing-stops-cron.log 2>&1

# ════════════════════════════════════════════════════════
# ETH ACCUMULATION TRACKER - Cada 4 horas
# ════════════════════════════════════════════════════════
0 */4 * * * /home/overgon/.openclaw/workspace/crypto-bots/eth-accumulation-tracker.sh >> /home/overgon/.openclaw/logs/eth-accumulation.log 2>&1

# ════════════════════════════════════════════════════════
# VERIFY BALANCES - Cada hora
# ════════════════════════════════════════════════════════
0 * * * * cd /home/overgon/.openclaw/workspace/crypto-bots && ./verify-balances.sh >> /home/overgon/.openclaw/logs/verify-balances-cron.log 2>&1

# ════════════════════════════════════════════════════════
# UPDATE PORTFOLIO - Cada 10 minutos
# ════════════════════════════════════════════════════════
*/10 * * * * /home/overgon/.openclaw/workspace/crypto-bots/update-portfolio.sh >> /home/overgon/.openclaw/logs/portfolio-updater.log 2>&1

# ════════════════════════════════════════════════════════
# UPDATE ML PREDICTIONS - Cada 2 horas
# ════════════════════════════════════════════════════════
0 */2 * * * /home/overgon/.openclaw/workspace/crypto-bots/update-ml-predictions.sh >> /home/overgon/.openclaw/logs/ml-predictions-update.log 2>&1

# ════════════════════════════════════════════════════════
# DASHBOARD WATCHDOG - Cada minuto
# ════════════════════════════════════════════════════════
* * * * * /home/overgon/.openclaw/workspace/dashboard/watchdog.sh >> /home/overgon/.openclaw/logs/dashboard-watchdog.log 2>&1

# ════════════════════════════════════════════════════════
# AUTO-RESET CLOSED SLOTS - Cada 5 minutos
# ════════════════════════════════════════════════════════
*/5 * * * * /home/overgon/.openclaw/workspace/auto-reset-closed-slots.sh >> /home/overgon/.openclaw/logs/auto-reset-slots.log 2>&1

# ════════════════════════════════════════════════════════
# DYNAMIC POSITION SIZING - Diario 8 AM
# ════════════════════════════════════════════════════════
0 8 * * * /usr/bin/python3 /home/overgon/.openclaw/workspace/crypto-bots/dynamic-position-sizing.py >> /home/overgon/.openclaw/logs/position-sizing.log 2>&1

# ════════════════════════════════════════════════════════
# HOUSEKEEPING - Mensual (1ro de cada mes, 1 AM)
# ════════════════════════════════════════════════════════
0 1 1 * * /home/overgon/.openclaw/scripts/housekeeping.sh >> /home/overgon/.openclaw/logs/housekeeping.log 2>&1

# ════════════════════════════════════════════════════════
# LOG ROTATION - Semanal (domingos, 2 AM)
# ════════════════════════════════════════════════════════
0 2 * * 0 logrotate -f /home/overgon/.openclaw/logs/logrotate.conf

# ════════════════════════════════════════════════════════
# DUCKDNS - Cada 5 minutos
# ════════════════════════════════════════════════════════
*/5 * * * * /home/overgon/duckdns.sh >> /home/overgon/.openclaw/logs/duckdns.log 2>&1

# ════════════════════════════════════════════════════════
# TRADING BOTS - 7 Monedas (cada 10 min, distribuidas)
# ════════════════════════════════════════════════════════
0,10,20,30,40,50 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh BTC >> /home/overgon/.openclaw/logs/auto-trade-all.log 2>&1
1,11,21,31,41,51 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh ETH >> /home/overgon/.openclaw/logs/auto-trade-all.log 2>&1
2,12,22,32,42,52 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh BNB >> /home/overgon/.openclaw/logs/auto-trade-all.log 2>&1
3,13,23,33,43,53 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh SOL >> /home/overgon/.openclaw/logs/auto-trade-all.log 2>&1
4,14,24,34,44,54 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh LINK >> /home/overgon/.openclaw/logs/auto-trade-all.log 2>&1
5,15,25,35,45,55 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh XRP >> /home/overgon/.openclaw/logs/auto-trade-all.log 2>&1
6,16,26,36,46,56 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh AVAX >> /home/overgon/.openclaw/logs/auto-trade-all.log 2>&1

EOF

echo "✅ Crontab restaurado exitosamente"
crontab -l | wc -l
echo "líneas instaladas"
