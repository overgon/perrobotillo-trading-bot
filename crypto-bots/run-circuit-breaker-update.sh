#!/bin/bash
# Circuit Breaker Countdown Update - Ejecución Local (sin LLM)
# Se ejecuta cada 5 minutos via cron del sistema

cd /home/overgon/.openclaw/workspace/crypto-bots
python3 update-circuit-breaker-countdown.py > /dev/null 2>&1
