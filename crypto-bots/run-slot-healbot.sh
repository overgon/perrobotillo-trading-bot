#!/bin/bash
# Slot Healbot - Ejecución Local (sin LLM)
# Se ejecuta cada 10 minutos via cron del sistema

cd /home/overgon/.openclaw/workspace/crypto-bots
python3 slot-healbot.py > /dev/null 2>&1
