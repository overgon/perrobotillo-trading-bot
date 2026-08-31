#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 PERROBOTILLO - RESTAURAR CRONTAB ADAPTADO
# ════════════════════════════════════════════════════════
# Fecha: 25/08/2026
# Versión adaptada: omite scripts inexistentes en filesystem
# Scripts excluidos: run-slot-healbot.sh, eth-accumulation-tracker.sh,
#                    auto-reset-closed-slots.sh, daily-report-9am.sh (NO EXISTEN)
# Reemplazidos por equivalentes reales (daily-report.py)
# Logs separados por moneda para mejor debugging
# ════════════════════════════════════════════════════════

cat << 'EOF' | crontab -
# ════════════════════════════════════════════════════════
# Perrobotillo Trading Bot - Crontab Adaptado (25/08/2026)
# ════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════
# TRADING BOTS - 7 Monedas (cada 10 min, offsets escalonados)
# Distribuido para evitar picos de CPU en Pi5
# Logs: cron-BTC.log, cron-ETH.log, cron-BNB.log, cron-SOL.log,
#       cron-LINK.log, cron-XRP.log, cron-AVAX.log
# ════════════════════════════════════════════════════════
0,10,20,30,40,50 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh BTC >> /home/overgon/.openclaw/logs/cron-BTC.log 2>&1
1,11,21,31,41,51 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh ETH >> /home/overgon/.openclaw/logs/cron-ETH.log 2>&1
2,12,22,32,42,52 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh BNB >> /home/overgon/.openclaw/logs/cron-BNB.log 2>&1
3,13,23,33,43,53 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh SOL >> /home/overgon/.openclaw/logs/cron-SOL.log 2>&1
4,14,24,34,44,54 * * * * /home/overgon/.openclaw/workspace/crypto-trade-moneda-v3-slots.sh LINK >> /home/overgon/.openclaw/logs/cron-LINK.log 2>&1
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
# Actualiza cache de portfolio para dashboard
# ════════════════════════════════════════════════════════
*/10 * * * * /home/overgon/.openclaw/workspace/crypto-bots/update-portfolio.sh >> /home/overgon/.openclaw/logs/portfolio-updater.log 2>&1

# ════════════════════════════════════════════════════════
# VERIFY BALANCES - Cada hora
# Reconciliación de balances Binance ↔ local
# ════════════════════════════════════════════════════════
0 * * * * /home/overgon/.openclaw/workspace/crypto-bots/verify-balances.sh >> /home/overgon/.openclaw/logs/verify-balances-cron.log 2>&1

# ════════════════════════════════════════════════════════
# UPDATE ML PREDICTIONS - Cada 2 horas
# Actualiza ONLY las predicciones del mercado (rápido)
# ════════════════════════════════════════════════════════
0 */2 * * * /home/overgon/.openclaw/workspace/crypto-bots/update-ml-predictions.sh >> /home/overgon/.openclaw/logs/ml-predictions-update.log 2>&1

# ════════════════════════════════════════════════════════
# DAILY REPORT - 9 AM (Python directo, no shell wrapper)
# Equivalente real a daily-report-9am.sh que no existe
# ════════════════════════════════════════════════════════
0 9 * * * /usr/bin/python3 /home/overgon/.openclaw/workspace/scripts/daily-report.py >> /home/overgon/.openclaw/logs/daily-report.log 2>&1

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
# DRAWNDOWN ALERT - Cada 30 minutos
# ════════════════════════════════════════════════════════
*/30 * * * * /home/overgon/.openclaw/workspace/check-drawdown-alert.sh >> /home/overgon/.openclaw/logs/drawdown-cron.log 2>&1

# ════════════════════════════════════════════════════════
# PROACTIVE ALERTS - Cada 30 minutos
# ════════════════════════════════════════════════════════
*/30 * * * * /home/overgon/.openclaw/workspace/crypto-bots/proactive-alerts.sh >> /home/overgon/.openclaw/logs/proactive-alerts.log 2>&1

# ════════════════════════════════════════════════════════
# PUBLIC IP MONITOR - Cada hora
# Verifica IP whitelist Binance
# ════════════════════════════════════════════════════════
0 * * * * /home/overgon/.openclaw/workspace/check-public-ip.sh >> /home/overgon/.openclaw/logs/ip-monitor-cron.log 2>&1

# ════════════════════════════════════════════════════════
# BINANCE MAINTENANCE MONITOR - Cada 4 horas
# ════════════════════════════════════════════════════════
0 */4 * * * /home/overgon/.openclaw/workspace/scripts/binance-maintenance-monitor.sh >> /home/overgon/.openclaw/logs/binance-maintenance.log 2>&1

# ════════════════════════════════════════════════════════
# FAN CONTROL - Cada 2 minutos
# Control de refrigeración Pi5
# ════════════════════════════════════════════════════════
*/2 * * * * /home/overgon/.openclaw/workspace/scripts/fan-control.sh >> /home/overgon/.openclaw/logs/fan-control.log 2>&1

# ════════════════════════════════════════════════════════
# DUCKDNS - Cada 5 minutos
# Actualización de DNS dinámico para dashboard
# ════════════════════════════════════════════════════════
*/5 * * * * /home/overgon/duckdns.sh >> /home/overgon/.openclaw/logs/duckdns.log 2>&1

# ════════════════════════════════════════════════════════
# SYNC STATE WITH BINANCE - Cada 15 minutos
# Reconciliación órdenes Binance ↔ local
# ════════════════════════════════════════════════════════
*/15 * * * * /home/overgon/.openclaw/workspace/crypto-bots/sync-state-with-binance.sh >> /home/overgon/.openclaw/logs/sync-state.log 2>&1

# ════════════════════════════════════════════════════════
# DASHBOARD WATCHDOG - Cada minuto
# ════════════════════════════════════════════════════════
* * * * * /home/overgon/.openclaw/workspace/dashboard/watchdog.sh >> /home/overgon/.openclaw/logs/dashboard-watchdog.log 2>&1

# ════════════════════════════════════════════════════════
# HOUSEKEEPING - 1ro de cada mes, 1 AM
# ════════════════════════════════════════════════════════
0 1 1 * * /home/overgon/.openclaw/scripts/housekeeping.sh >> /home/overgon/.openclaw/logs/housekeeping.log 2>&1

# ════════════════════════════════════════════════════════
# LOG ROTATION - Semanal (domingos, 2 AM)
# ════════════════════════════════════════════════════════
0 2 * * 0 logrotate -f /home/overgon/.openclaw/logs/logrotate.conf

# ════════════════════════════════════════════════════════
# DYNAMIC POSITION SIZING - Diario 8 AM
# ════════════════════════════════════════════════════════
0 8 * * * /usr/bin/python3 /home/overgon/.openclaw/workspace/crypto-bots/dynamic-position-sizing.py >> /home/overgon/.openclaw/logs/position-sizing.log 2>&1

EOF

echo "✅ Crontab adaptado restaurado"
crontab -l | wc -l
echo "líneas instaladas"