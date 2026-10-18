#!/bin/bash
# ════════════════════════════════════════════════════════
# 🚦 Regime-Aware Config Switcher
# ════════════════════════════════════════════════════════
# Swaps per-coin-config.env between bear/lateral and bull
# configs based on market-mode.conf + CB state.
#
# Usage: ./switch-per-coin-config.sh [--dry-run]
#
# Logic:
#   1. Read MARKET_MODE from market-mode.conf
#   2. Check global-pause-flag.json (CB active?)
#   3. If BULL/VOLATILE_BULL AND CB inactive:
#      → backup per-coin-config.env, copy .bull.env to active
#   4. If BEAR/LATERAL/VOLATILE_BEAR:
#      → restore from latest backup if bull config is active
#   5. Log to market-regime.json, notify Telegram
#
# Called from auto-adjust-strategy.sh after final mode resolution.
# ════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/.."
STATE_DIR="${SCRIPT_DIR}/state"
BACKUP_DIR="${SCRIPT_DIR}/.backup"
REGIME_FILE="${STATE_DIR}/market-regime.json"
COOLDOWN_FILE="${STATE_DIR}/last-regime-switch.time"
COOLDOWN_MINUTES=360  # 6 hours

ACTIVE_CONFIG="${SCRIPT_DIR}/per-coin-config.env"
BULL_CONFIG="${SCRIPT_DIR}/per-coin-config-bull.env"
MARKET_MODE_CONF="${SCRIPT_DIR}/market-mode.conf"
CB_FLAG="${SCRIPT_DIR}/global-pause-flag.json"

mkdir -p "$STATE_DIR" "$BACKUP_DIR"

# Load notification helpers
if [ -f "${SCRIPT_DIR}/notify.sh" ]; then
    source "${SCRIPT_DIR}/notify.sh"
fi

DRY_RUN="false"
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN="true"
fi

# ── Helper: source market-mode.conf ──
load_market_mode() {
    if [ ! -f "$MARKET_MODE_CONF" ]; then
        echo "LATERAL"
        return
    fi
    local mode=""
    while IFS='=' read -r key val; do
        if [ "$key" = "MARKET_MODE" ]; then
            mode=$(echo "$val" | tr -d '"' | tr -d ' ')
        fi
    done < "$MARKET_MODE_CONF"
    echo "${mode:-LATERAL}"
}

# ── Helper: check if CB is active ──
cb_is_active() {
    if [ ! -f "$CB_FLAG" ]; then
        return 1  # CB inactive
    fi
    local pause_until
    pause_until=$(python3 -c "
import json, sys
from datetime import datetime
try:
    d = json.load(open('$CB_FLAG'))
    pa = d.get('pause_until', '')
    if not pa:
        sys.exit(0)
    now = datetime.now()
    # Handle both ISO and naive formats
    if 'T' in pa:
        exp = datetime.fromisoformat(pa.replace('Z', '+00:00'))
        exp = exp.replace(tzinfo=None) if exp.tzinfo else exp
    else:
        exp = datetime.strptime(pa, '%Y-%m-%d %H:%M:%S')
    sys.exit(0 if now > exp else 1)
except Exception:
    sys.exit(0)  # file exists but malformed → treat as active
" 2>/dev/null || echo "0")

    if [ "$pause_until" = "0" ]; then
        return 1  # expired or malformed → inactive
    fi
    return 0
}

# ── Helper: detect which config is currently active ──
detect_active_config() {
    # Compare active config against bull config
    # If they match, bull is active; if they differ, bear is active
    if [ ! -f "$BULL_CONFIG" ]; then
        echo "bear"
        return
    fi
    if diff -q "$ACTIVE_CONFIG" "$BULL_CONFIG" >/dev/null 2>&1; then
        echo "bull"
    else
        echo "bear"
    fi
}

# ── Helper: write regime state JSON ──
write_regime_state() {
    local mode="$1" active_config="$2" reason="$3" switched="$4"

    # Pre-calculate CB status as shell var (avoid nested python3 calls)
    if cb_is_active; then
        CB_ACTIVE_STR="True"
    else
        CB_ACTIVE_STR="False"
    fi
    BULL_EXISTS_STR="True"
    [ -f "$BULL_CONFIG" ] || BULL_EXISTS_STR="False"

    python3 -c "
import json, os
from datetime import datetime

regime = {
    'market_mode': '$mode',
    'active_config': '$active_config',
    'reason': '$reason',
    'last_switched': '$switched',
    'last_updated': datetime.now().isoformat(),
    'cb_active': $CB_ACTIVE_STR,
    'bull_config_exists': $BULL_EXISTS_STR,
}

existing = {}
if os.path.exists('$REGIME_FILE'):
    try:
        with open('$REGIME_FILE') as f:
            existing = json.load(f)
    except Exception:
        pass

regime['switch_count'] = existing.get('switch_count', 0) + (1 if '$switched' != existing.get('last_switched', '') else 0)

with open('$REGIME_FILE', 'w') as f:
    json.dump(regime, f, indent=2)
print(json.dumps(regime, indent=2))
" 2>/dev/null
}

# ── Main ──
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  🚦 Regime Config Switcher                            ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

MARKET_MODE=$(load_market_mode)
echo "📊 Market mode: $MARKET_MODE"

if cb_is_active; then
    echo "🛑 Circuit breaker ACTIVE — manteniendo config defensiva (bear/lateral)"
    CURRENT_CONFIG=$(detect_active_config)
    if [ "$CURRENT_CONFIG" = "bull" ]; then
        echo "⚠️  Bull config active during CB — restoring bear config"
        if [ "$DRY_RUN" = "false" ]; then
            # Find latest backup
            LATEST_BACKUP=$(ls -t "${BACKUP_DIR}/per-coin-config.env.2025"* 2>/dev/null | head -1)
            if [ -n "$LATEST_BACKUP" ]; then
                cp "$LATEST_BACKUP" "$ACTIVE_CONFIG"
                echo "✅ Restored from: $LATEST_BACKUP"
            else
                # Fallback: generate from bull by reverting TP/SL/size changes
                echo "⚠️ No backup found — keeping current config (manual review needed)"
            fi
        fi
    fi
    write_regime_state "$MARKET_MODE" "bear" "CB active, defensive mode" "$(date '+%Y-%m-%d %H:%M:%S')" >/dev/null
else
    echo "✅ Circuit breaker inactive"
    CURRENT_CONFIG=$(detect_active_config)
    echo "📁 Current config: $CURRENT_CONFIG"

    # Determine target config based on market mode
    case "$MARKET_MODE" in
        BULL|VOLATILE_BULL)
            TARGET_CONFIG="bull"
            ;;
        *)
            TARGET_CONFIG="bear"
            ;;
    esac

    echo "🎯 Target config: $TARGET_CONFIG"

    if [ "$CURRENT_CONFIG" = "$TARGET_CONFIG" ]; then
        echo "🔁 No cambio necesario (config already $TARGET_CONFIG)"
        write_regime_state "$MARKET_MODE" "$CURRENT_CONFIG" "No change needed" "$(date '+%Y-%m-%d %H:%M:%S')" >/dev/null
    else
        echo "🔄 Cambiando config: $CURRENT_CONFIG → $TARGET_CONFIG"

        if [ "$DRY_RUN" = "true" ]; then
            echo "🧪 [DRY-RUN] Would switch config now"
        else
            # Cooldown check
            if [ -f "$COOLDOWN_FILE" ]; then
                LAST_SWITCH=$(cat "$COOLDOWN_FILE")
                NOW=$(date +%s)
                LAST_TS=$(date -d "$LAST_SWITCH" +%s 2>/dev/null || echo 0)
                AGE_MIN=$(( (NOW - LAST_TS) / 60 ))
                if [ "$AGE_MIN" -lt "$COOLDOWN_MINUTES" ]; then
                    echo "⏳ Cooldown: ${AGE_MIN}min < ${COOLDOWN_MINUTES}min — skipping switch"
                    write_regime_state "$MARKET_MODE" "$CURRENT_CONFIG" "Cooldown active (${AGE_MIN}min)" "$(date '+%Y-%m-%d %H:%M:%S')" >/dev/null
                    exit 0
                fi
            fi

            # Backup current config
            TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
            BACKUP_PATH="${BACKUP_DIR}/per-coin-config.env.${TIMESTAMP}"
            cp "$ACTIVE_CONFIG" "$BACKUP_PATH"
            echo "💾 Backup: $BACKUP_PATH"

            if [ "$TARGET_CONFIG" = "bull" ]; then
                cp "$BULL_CONFIG" "$ACTIVE_CONFIG"
                echo "✅ Applied BULL config from per-coin-config-bull.env"
                REASON="Switched to bull config on $MARKET_MODE"
                NOTIFY_EVENT="REGIME_BULL"
                NOTIFY_EMOJI="🟢"
            else
                # Restore from latest backup
                LATEST_BACKUP=$(ls -t "${BACKUP_DIR}/per-coin-config.env.2025"* 2>/dev/null | head -1)
                if [ -n "$LATEST_BACKUP" ]; then
                    cp "$LATEST_BACKUP" "$ACTIVE_CONFIG"
                    echo "✅ Restored BEAR/LATERAL config from: $LATEST_BACKUP"
                    REASON="Restored bear config (market mode: $MARKET_MODE)"
                    NOTIFY_EVENT="REGIME_BEAR"
                    NOTIFY_EMOJI="🔴"
                else
                    echo "⚠️ No backup found — cannot restore"
                    REASON="No backup to restore"
                fi
            fi

            # Update cooldown
            date '+%Y-%m-%d %H:%M:%S' > "$COOLDOWN_FILE"

            # Write regime state
            write_regime_state "$MARKET_MODE" "$TARGET_CONFIG" "$REASON" "$(date '+%Y-%m-%d %H:%M:%S')"

            # Notify
            if command -v send_telegram >/dev/null 2>&1; then
                MSG=$(printf "%s REGIME SWITCH | Mode: %s -> %s\n📝 %s\n⚙️ per-coin-config.env updated\n✅ Aplicado" "$NOTIFY_EMOJI" "$CURRENT_CONFIG" "$TARGET_CONFIG" "$REASON")
                send_telegram "$NOTIFY_EVENT" "$MSG" 2>/dev/null || echo "⚠️ Notify failed"
            fi
        fi
    fi
fi

echo ""
echo "📄 Regime state: $REGIME_FILE"
