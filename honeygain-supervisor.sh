#!/bin/bash
# Honeygain Supervisor - checks if running, restarts if not
# Called by crontab every 5 minutes

WS="/home/overgon/.openclaw/workspace"
LOG_FILE="/home/overgon/.openclaw/workspace/.honeygain_supervisor.log"
PID_FILE="/home/overgon/.openclaw/workspace/.honeygain.pid"
STARTUP_LOG="/home/overgon/.openclaw/workspace/.honeygain_startup.log"
ENV_FILE="/home/overgon/.honeygain.env"
COOLDOWN_FILE="/home/overgon/.openclaw/workspace/.honeygain_cooldown"

# Source credentials
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') CRITICAL no $ENV_FILE" >> "$LOG_FILE"
    exit 1
fi

# Check cooldown (IP flag clearing)
if [ -f "$COOLDOWN_FILE" ]; then
    cooldown_until=$(cat "$COOLDOWN_FILE")
    now=$(date +%s)
    if [ "$now" -lt "$cooldown_until" ]; then
        remaining=$(( (cooldown_until - now) / 60 ))
        echo "$(date '+%Y-%m-%d %H:%M:%S') SKIP cooldown: $remaining min remaining" >> "$LOG_FILE"
        exit 0
    fi
    rm -f "$COOLDOWN_FILE"
    echo "$(date '+%Y-%m-%d %H:%M:%S') Cooldown expired, starting honeygain" >> "$LOG_FILE"
fi

# Check if honeygain is running and has connections
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        CONNS=$(cat /proc/$PID/net/tcp 2>/dev/null | grep " 01 " | wc -l)
        if [ "$CONNS" -gt 0 ] 2>/dev/null; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') OK PID=$PID conns=$CONNS" >> "$LOG_FILE"
            exit 0
        fi
    fi
    rm -f "$PID_FILE"
fi

# Check for "Network Overused" in startup log - if found, set cooldown and retry later
if [ -f "$STARTUP_LOG" ]; then
    if grep -q "Network Overused" "$STARTUP_LOG" 2>/dev/null; then
        # Set 15-minute cooldown
        echo $(($(date +%s) + 900)) > "$COOLDOWN_FILE"
        echo "$(date '+%Y-%m-%d %H:%M:%S') Network Overused detected, setting 15-min cooldown" >> "$LOG_FILE"
        exit 1
    fi
fi

# Start honeygain
echo "$(date '+%Y-%m-%d %H:%M:%S') Starting..." >> "$LOG_FILE"
export LD_LIBRARY_PATH="$WS:$LD_LIBRARY_PATH"
cd "$WS"
nohup setsid ./honeygain -tou-accept -email "$HONEYGAIN_EMAIL" -pass "$HONEYGAIN_PASS" -device "myPi5-b" > "$STARTUP_LOG" 2>&1 &
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"
sleep 3
if kill -0 $NEW_PID 2>/dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') OK Started PID=$NEW_PID" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') CRITICAL Process died" >> "$LOG_FILE"
fi
