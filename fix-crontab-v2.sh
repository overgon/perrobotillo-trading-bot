#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - RESTAURAR CRONTAB CORREGIDO (2026-10-04)
# Combina paths absolutos del backup + componentes modernos
# ════════════════════════════════════════════════════════

cat << 'CRONEOF' | crontab -
# ════════════════════════════════════════════════════════
# Perrobotillo Trading Bot - Crontab CORREGIDO
# Paths ABSOLUTOS para evitar path corruption en cron
# Generado: 2026-10-04
# ════════════════════════════════════════════════════════

# Variables de entorno (definidas pero crontab usa paths absolutos)
HOME=/home/overgon
WORKSPACE=/home/overgon/.openclaw/workspace
PYTHON=/usr/bin/python3
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# ════════════════════════════════════════════════════════
# TRADING BOTS - 7 Monedas (cada 10 min, offsets escalonados)
# Distribuido para evitar picos de CPU en Pi5
# ════════════════════════════════════════════════════════
0,10,20,30,40,50 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh BTC >> /home/overgon/.openclaw/logs/cron-BTC.log 2>&1
1,11,21,31,41,51 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh ETH >> /home/overgon/.openclaw/logs/cron-ETH.log 2>&1
2,12,22,32,42,52 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh BNB >> /home/overgon/.openclaw/logs/cron-BNB.log 2>&1
3,13,23,33,43,53 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh SOL >> /home/overgon/.openclaw/logs/cron-SOL.log 2>&1
4,14,24,34,44,54 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh ZEC >> /home/overgon/.openclaw/logs/cron-ZEC.log 2>&1
5,15,25,35,45,55 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh XRP >> /home/overgon/.openclaw/logs/cron-XRP.log 2>&1
6,16,26,36,46,56 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh AVAX >> /home/overgon/.openclaw/logs/cron-AVAX.log 2>&1

# ════════════════════════════════════════════════════════
# GLOBAL CIRCUIT BREAKER - Cada 5 minutos (LOCAL, SIN LLM)
# Bloquea nuevas aperturas cuando hay drawdown global
# ════════════════════════════════════════════════════════
*/5 * * * * /home/overgon/.openclaw/workspace/crypto-bots/global-circuit-breaker.sh >> /home/overgon/.openclaw/logs/cb-monitor.log 2>&1

# ════════════════════════════════════════════════════════
# CB COUNTDOWN UPDATE - Cada 5 minutos (LOCAL, SIN LLM)
# Actualiza dashboard-circuit-breaker-status.json
# ════════════════════════════════════════════════════════
*/5 * * * * /home/overgon/.openclaw/workspace/crypto-bots/run-circuit-breaker-update.sh >> /home/overgon/.openclaw/logs/cb-monitor.log 2>&1

# ════════════════════════════════════════════════════════
# AUTO-ADJUST STRATEGY - Cada 6 horas (con ML validation)
# ════════════════════════════════════════════════════════
0 */6 * * * /home/overgon/.openclaw/workspace/crypto-bots/auto-adjust-strategy.sh >> /home/overgon/.openclaw/logs/auto-adjust.log 2>&1

# ════════════════════════════════════════════════════════
# AUTO-RESUME TRADING - Cada 5 minutos
# Reactiva BTC/ETH si cumplen criterios de performance
# ════════════════════════════════════════════════════════
*/5 * * * * /home/overgon/.openclaw/workspace/crypto-bots/auto-resume-trading.sh >> /home/overgon/.openclaw/logs/auto-resume.log 2>&1

# ════════════════════════════════════════════════════════
# PORTFOLIO UPDATER - Cada 10 minutos
# ════════════════════════════════════════════════════════
*/10 * * * * /home/overgon/.openclaw/workspace/crypto-bots/update-portfolio.sh >> /home/overgon/.openclaw/logs/portfolio-updater.log 2>&1

# ════════════════════════════════════════════════════════
# VERIFY BALANCES - Cada hora
# ════════════════════════════════════════════════════════
0 * * * * /home/overgon/.openclaw/workspace/crypto-bots/verify-balances.sh >> /home/overgon/.openclaw/logs/verify-balances-cron.log 2>&1

# ════════════════════════════════════════════════════════
# UPDATE ML PREDICTIONS - Cada 2 horas
# ════════════════════════════════════════════════════════
0 */2 * * * /home/overgon/.openclaw/workspace/crypto-bots/update-ml-predictions.sh >> /home/overgon/.openclaw/logs/ml-predictions-update.log 2>&1

# ════════════════════════════════════════════════════════
# DAILY REPORT - 9 AM (Python directo)
# ════════════════════════════════════════════════════════
0 9 * * * /usr/bin/python3 /home/overgon/.openclaw/workspace/scripts/daily-report.py >> /home/overgon/.openclaw/logs/daily-report.log 2>&1

# ════════════════════════════════════════════════════════
# DRAWNDOWN ALERT - Cada 30 minutos
# ════════════════════════════════════════════════════════
*/30 * * * * /home/overgon/.openclaw/workspace/check-drawdown-alert.sh >> /home/overgon/.openclaw/logs/drawdown-cron.log 2>&1

# ════════════════════════════════════════════════════════
# PROACTIVE ALERTS - Cada 30 minutos
# ════════════════════════════════════════════════════════
*/30 * * * * /home/overgon/.openclaw/workspace/crypto-bots/proactive-alerts.sh >> /home/overgon/.openclaw/logs/proactive-alerts.log 2>&1

# ════════════════════════════════════════════════════════
# EARLY WARNING ALERT - Cada 5 minutos (NUEVO)
# ════════════════════════════════════════════════════════
*/5 * * * * /home/overgon/.openclaw/workspace/crypto-bots/early-warning-alert.sh >> /home/overgon/.openclaw/logs/early-warning-alert.log 2>&1

# ════════════════════════════════════════════════════════
# PUBLIC IP MONITOR - Cada hora
# ════════════════════════════════════════════════════════
0 * * * * /home/overgon/.openclaw/workspace/check-public-ip.sh >> /home/overgon/.openclaw/logs/ip-monitor-cron.log 2>&1

# ════════════════════════════════════════════════════════
# BINANCE MAINTENANCE MONITOR - Cada 4 horas
# ════════════════════════════════════════════════════════
0 */4 * * * /home/overgon/.openclaw/workspace/scripts/binance-maintenance-monitor.sh >> /home/overgon/.openclaw/logs/binance-maintenance.log 2>&1

# ════════════════════════════════════════════════════════
# FAN CONTROL - Cada 2 minutos
# ════════════════════════════════════════════════════════
*/2 * * * * /home/overgon/.openclaw/workspace/scripts/fan-control.sh >> /home/overgon/.openclaw/logs/fan-control.log 2>&1

# ════════════════════════════════════════════════════════
# DUCKDNS - Cada 5 minutos
# Path corregido: NO usa $WORKSPACE/../ (ruta relativa rota)
# ════════════════════════════════════════════════════════
*/5 * * * * /home/overgon/duckdns.sh >> /home/overgon/.openclaw/logs/duckdns.log 2>&1

# ════════════════════════════════════════════════════════
# ML AUTO-RETRAIN - Domingos 3 AM
# ════════════════════════════════════════════════════════
0 3 * * 0 /home/overgon/.openclaw/workspace/ml/ml-retrain-cron.sh >> /home/overgon/.openclaw/logs/ml-auto-retrain.log 2>&1

# ════════════════════════════════════════════════════════
# ML RETRAIN STATUS REPORT - Domingos 9 AM
# ════════════════════════════════════════════════════════
0 9 * * 0 /home/overgon/.openclaw/workspace/scripts/ml-retrain-report.sh >> /home/overgon/.openclaw/logs/ml-retrain-report-cron.log 2>&1

# ════════════════════════════════════════════════════════
# PORTFOLIO REBALANCING - Domingos 11 PM
# ════════════════════════════════════════════════════════
0 23 * * 0 cd /home/overgon/.openclaw/workspace && /home/overgon/.openclaw/workspace/scripts/portfolio-rebalance.sh rebalance >> /home/overgon/.openclaw/logs/portfolio-rebalance-cron.log 2>&1

# ════════════════════════════════════════════════════════
# TRAILING STOPS ATR UPDATE - Cada 2 horas
# ════════════════════════════════════════════════════════
0 */2 * * * cd /home/overgon/.openclaw/workspace && /home/overgon/.openclaw/workspace/scripts/update-trailing-stops.sh >> /home/overgon/.openclaw/logs/trailing-stops-cron.log 2>&1

# ════════════════════════════════════════════════════════
# PARAM MULTIPLIERS - Cada 5 minutos (NUEVO)
# ════════════════════════════════════════════════════════
*/5 * * * * /home/overgon/.openclaw/workspace/dashboard/run-param-multipliers.sh >> /home/overgon/.openclaw/logs/param-multipliers.log 2>&1

# ════════════════════════════════════════════════════════
# HOUSEKEEPING - 1ro de cada mes, 1 AM
# ════════════════════════════════════════════════════════
0 1 1 * * /home/overgon/.openclaw/workspace/scripts/housekeeping.sh >> /home/overgon/.openclaw/logs/housekeeping.log 2>&1

# ════════════════════════════════════════════════════════
# LOG ROTATION - Domingos 2 AM
# ════════════════════════════════════════════════════════
0 2 * * 0 logrotate -f /home/overgon/.openclaw/logs/logrotate.conf

# ════════════════════════════════════════════════════════
# DASHBOARD WATCHDOG - Cada minuto
# ════════════════════════════════════════════════════════
* * * * * /home/overgon/.openclaw/workspace/dashboard/watchdog.sh >> /home/overgon/.openclaw/logs/dashboard-watchdog.log 2>&1

# ════════════════════════════════════════════════════════
# SYNC STATE WITH BINANCE - Cada 15 minutos
# ════════════════════════════════════════════════════════
*/15 * * * * /home/overgon/.openclaw/workspace/crypto-bots/sync-state-with-binance.sh >> /home/overgon/.openclaw/logs/sync-state.log 2>&1

CRONEOF

echo "✅ Crontab corregido con paths absolutos"
crontab -l | wc -l
echo "líneas instaladas"
