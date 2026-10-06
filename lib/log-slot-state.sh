#!/bin/bash
# ════════════════════════════════════════════════════════
# 📊 TRADE SLOT STATE TRACKER - Perrobotillo v2.1
# Integra con crypto-trade-moneda-v3-slots.sh
# Log: trade-slots.log (JSONL estructurado)
# ════════════════════════════════════════════════════════

# Uso: source este script, luego llamar log_slot_state

log_slot_state() {
    local coin="$1"
    local slot_id="$3"
    local status="$4"
    local entry_price="$5"
    local sl="$6"
    local tp="$7"
    local pnl="${8:-0}"
    
    local log_file="/home/overgon/.openclaw/logs/trade-slots.log"
    local ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    echo "{\"timestamp\":\"$ts\",\"event\":\"slot.state\",\"coin\":\"$coin\",\"slot_id\":$slot_id,\"status\":\"$status\",\"entry_price\":$entry_price,\"sl\":$sl,\"tp\":$tp,\"pnl\":$pnl}" >> "$log_file"
}

# Función para llamar al final de cada ciclo de trading
record_slot_cycle() {
    local coin="$1"
    local script_path="$0"
    local log_file="/home/overgon/.openclaw/logs/circuit-breaker-decisions.log"
    local ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Leer estado actual de slots
    local state_file="/home/overgon/.openclaw/workspace/crypto-bots/${coin}-trade-state.json"
    if [ -f "$state_file" ]; then
        local active_slots=$(jq -r '[.slots[] | select(.status == "ACTIVE")] | length' "$state_file" 2>/dev/null || echo "0")
        local total_slots=$(jq -r '.slots | length' "$state_file" 2>/dev/null || echo "0")
        
        echo "{\"timestamp\":\"$ts\",\"event\":\"cycle.complete\",\"coin\":\"$coin\",\"script\":\"$script_path\",\"active_slots\":$active_slots,\"total_slots\":$total_slots}" >> "$log_file"
    fi
}
