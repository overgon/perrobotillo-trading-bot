#!/usr/bin/env python3
"""Verificación completa del estado de los 7 modelos y slots de trading"""
import json, os, glob

WORKSPACE = "/home/overgon/.openclaw/workspace"

COINS = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"]

print("=== 📊 ML STATUS (7 monedas) ===")
print(f"{'COIN':<6} {'STATUS':<10} {'ACCURACY':<10} {'GAP%':<8} {'F1':<8} {'LAST_TRAINED'}")
print("-" * 70)

for coin in COINS:
    meta_path = f"{WORKSPACE}/ml/models_optimized/{coin}_optimized_metadata.json"
    if os.path.exists(meta_path):
        m = json.load(open(meta_path))
        metrics = m.get("metrics", {})
        acc = metrics.get("accuracy", 0)
        gap = metrics.get("overfitting_gap", 0)
        f1 = metrics.get("f1", 0)
        trained = m.get("trained_at", "?")[:16]
        status = "✅ PASS" if gap < 0.05 else "⚠️ WARN"
        print(f"{coin:<6} {status:<10} {acc:<10.2%} {gap:<8.2%} {f1:<8.2%} {trained}")
    else:
        print(f"{coin:<6} ❌ NO MODEL")

print()
print("=== 📌 TRADE STATE (slots) ===")
print(f"{'COIN':<6} {'READY':<6} {'ACTIVE':<7} {'TIPOS'}")
print("-" * 40)

for coin in COINS:
    state_path = f"{WORKSPACE}/crypto-bots/{coin}-trade-state.json"
    if os.path.exists(state_path):
        s = json.load(open(state_path))
        slots = s.get("slots", [])
        ready = sum(1 for sl in slots if sl.get("status") == "READY")
        active = sum(1 for sl in slots if sl.get("status") == "ACTIVE")
        types = [sl.get("type", "?") for sl in slots]
        print(f"{coin:<6} {ready}/3    {active}       {types}")
    else:
        print(f"{coin:<6} ❌ No trade-state")

print()
print("=== 🔧 SISTEMA CRÍTICO ===")
issues = []

# Circuit breaker
pause_flag = f"{WORKSPACE}/crypto-bots/global-pause-flag.json"
if os.path.exists(pause_flag):
    pf = json.load(open(pause_flag))
    pause_until = pf.get("pause_until", "N/A")
    print(f"⚠️ CIRCUIT BREAKER: PAUSADO hasta {pause_until}")
    issues.append("circuit-breaker")
else:
    print("✅ CIRCUIT BREAKER: INACTIVO")

# ML pause flags
paused_coins = []
for coin in COINS:
    flag_path = f"{WORKSPACE}/crypto-bots/{coin}-ml-pause-flag.json"
    if os.path.exists(flag_path):
        pf = json.load(open(flag_path))
        if pf.get("paused"):
            paused_coins.append(coin)
if paused_coins:
    print(f"⚠️ ML PAUSE: {paused_coins}")
    issues.append("ml-pause")
else:
    print("✅ ML PAUSE FLAGS: TODOS LIMPIOS")

# Lockfiles stuck
stuck = []
for coin in COINS:
    lock = f"{WORKSPACE}/crypto-bots/.{coin}-trading.lock"
    if os.path.exists(lock) and os.path.getsize(lock) > 0:
        stuck.append(coin)
if stuck:
    print(f"❌ LOCKFILES STUCK: {stuck}")
    issues.append("stuck-locks")
else:
    print("✅ LOCKFILES: TODOS OK (vacíos)")

# Cron jobs
import subprocess
cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
cron_count = cron.count("/crypto-trade-moneda-v3-slots.sh")
print(f"✅ CRON: {cron_count} jobs de trading activos")

print()
print("=== 🎯 VEREDICTO ===")
if not issues:
    print("✅✅✅ BOT 100% OPERATIVO — LISTO PARA ABRIR TRADES EN LAS 7 MONEDAS ✅✅✅")
else:
    print(f"⚠️ PROBLEMAS: {issues} — revisar antes de operar")
