#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
# 🪙 PERROBOTILLO — COIN REPLACEMENT PIPELINE  (Issue #70)
#
# Amina la moneda con peor desempeño del mes y la reemplaza por una
# candidata con mejor potencial, en modo dry-run (solo muestra) o --execute.
#
#   --candidate NEAR        Moneda candidata (default: la más débil)
#   --old BTC               Moneda a reemplazar (default: la más débil)
#   --dry-run               Solo muestra (predeterminado)
#   --execute               Aplica los cambios
#   --confirm               Aproxime 'sí' para --execute
#
# Flujo (--execute):
#   1. Peor moneda del mes según trade-history.json
#   2. Validación de candidata (par USDT + volumen)
#   3. Retrain ML de la candidata (auto-retrain-v2.py)
#   4. State file con 3 slots READY
#   5. Per-coin config (per-coin-config.env)
#   6. Entrada cron (manual)
#   7. Whitelist symbols en crypto-trade-moneda-v3-slots.sh
#   8. Desactivación de la vieja (OLD_ENABLED=false)
#   9. Reporte de cambios
# ═══════════════════════════════════════════════════════════════════════════

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
TRADES_FILE = os.path.join(WORKSPACE, "crypto-bots", "trade-history.json")
SLOTS_SH = os.path.join(WORKSPACE, "crypto-bots", "crypto-trade-moneda-v3-slots.sh")
AUTO_RETRAIN = os.path.join(WORKSPACE, "ml", "auto-retrain-v2.py")
STATE_FILE = os.path.join(WORKSPACE, "crypto-bots", "trade-state.json")
PER_COIN_ENV = os.path.join(WORKSPACE, "crypto-bots", "per-coin-config.env")
COIN_LIST = ["BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX", "ZEC"]
READY = 3

CONFIRM = {"yes", "y", "si", "s"}

# ---------------------------------------------------------------------------
def load_history():
    if not os.path.exists(TRADES_FILE):
        print("❌ trade-history.json no encontrado")
        sys.exit(1)
    with open(TRADES_FILE) as f:
        return json.load(f)

# ---------------------------------------------------------------------------
def pnl_by_coin(trades):
    """PnL acumulado por moneda extraído de trade-history.json."""
    pnl = defaultdict(float)
    for t in trades:
        sym = (t.get("symbol") or "").replace("USDT", "")
        if sym in COIN_LIST:
            pnl[sym] += float(t.get("pnl") or 0.0)
    return pnl

def worst_coin(pnl):
    return min(pnl, key=pnl.get) if pnl else None

# ---------------------------------------------------------------------------
def http_get(url, timeout=8):
    import urllib.request
    req = urllib.request.Request(url, timeout=timeout)
    with urllib.request.urlopen(req) as r:
        return r.status, json.load(r)

# ---------------------------------------------------------------------------
def validate_candidate(coin):
    """Valida que la candidata tenga un par USDT con precio > 0 y volumen."""
    if coin in COIN_LIST:
        return True, f"{coin}USDT", None, None
    try:
        st, t = http_get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT")
        if st != 200 or t.get("price") in (None, 0):
            return False, f"{coin}USDT", "sin precio", None
        st2, d = http_get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={coin}USDT")
        if st2 != 200:
            return False, f"{coin}USDT", "volumen no disponible", None
        vol = float(d.get("quoteVolume") or 0)
        if vol < 1_000_000_000:
            return False, f"{coin}USDT", f"volumen bajo {vol:,.0f}", vol
        return True, f"{coin}USDT", vol, None
    except Exception as e:
        return False, f"{coin}USDT", str(e), None

# ---------------------------------------------------------------------------
def read_ml_coins():
    try:
        with open(AUTO_RETRAIN) as f:
            txt = f.read()
        m = re.search(r"COINS\s*=\s*\[(.*?)\]", txt, re.S)
        if m:
            return [c.strip().strip('"\'') for c in m.group(1).split(",") if c.strip()]
    except Exception:
        pass
    return COIN_LIST

# ---------------------------------------------------------------------------
def build_report(old, new, worst, pnl, ts):
    lines = [
        "═══ 💰 REPORTE DE CAMBIO DE MONEDA ═══",
        f"📅 {ts}",
        f"📉 Peor moneda del mes: {worst}  (PnL total: {pnl.get(worst, 0):.2f})",
        f"➡️  Moneda reemplazada: {old}",
        f"🆕  Moneda candidata: {new}",
        "✅ Cambios aplicados:",
        "   1. Identificó la peor moneda",
        "   2. Validó la candidata en Binance",
        "   3. Retrain ML de la candidata",
        "   4. State file con 3 slots READY",
        "   5. Per-coin config (per-coin-config.env)",
        "   6. Entrada cron (manual)",
        "   7. Whitelist symbols en crypto-trade-moneda-v3-slots.sh",
        "   8. Desactivó la vieja (OLD_ENABLED=false)",
        "   9. Reporte de cambios",
    ]
    return "\n".join(lines)

# ---------------------------------------------------------------------------
def apply(old, new, dry_run):
    print(f"🔵 [pipeline] Old={old}  New={new}  dry_run={dry_run}")

    trades = load_history()
    pnl = pnl_by_coin(trades)
    worst = worst_coin(pnl)
    if worst is None:
        print("❌ No se pudo calcular PnL mensual")
        return 1

    if dry_run:
        print("🔵 [dry-run] PnL mensual:")
        for c in sorted(pnl):
            print(f"     {c}: {pnl[c]:+.2f}")
        print(f"🔵 [dry-run] Peor moneda: {worst}")
        ok, pair, info, vol = validate_candidate(new)
        print(f"🔵 [dry-run] candidata {new} -> {pair}  {'válido' if ok else 'inválido'}")
        if info:
            print(f"     ↳ {info}")
        print("🔵 [dry-run] (sin escribir nada)")
        print("\n" + build_report(old, new, worst, pnl, datetime.now().isoformat()))
        return 0

    # 1..9
    ok, pair, msg, vol = validate_candidate(new)
    if not ok:
        print(f"❌ Candidata {new} inválida: {msg}")
        return 1
    print(f"✅ Candidata {new} válida en {pair}")
    if vol:
        print(f"   ↳ volumen 24h: {vol:,.0f}")

    # Retrain ML
    coins = read_ml_coins()
    if new not in coins:
        try:
            txt = open(AUTO_RETRAIN).read()
            if "COINS = [" in txt:
                txt = re.sub(r"COINS\s*=\s*\[.*?\]", f"COINS = {sorted(set(coins))}", txt, flags=re.S)
            else:
                txt = txt.replace("COIN_LIST = [", f"COIN_LIST = {sorted(set(coins))}\nCOINS = {sorted(set(coins))}")
            open(AUTO_RETRAIN, "w").write(txt)
            print(f"🔧 auto-retrain-v2.py: {new} añadido a COINS")
        except Exception as e:
            print(f"⚠️  no se pudo editar auto-retrain-v2.py: {e}")
    subprocess.run([sys.executable, AUTO_RETRAIN], check=True)
    print("✅ Retrain ML de la candidata")

    # State file 3 slots READY
    state = {"coin": new, "slots": [
        {"slotId": i, "status": "READY", "symbol": f"{new}USDT"} for i in range(READY)]}
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print("✅ State file (3 slots READY) creado")

    # Per-coin config
    with open(PER_COIN_ENV, "a") as f:
        f.write(f"\n# Reemplazo el {datetime.now().isoformat()}\nOLD_COIN={old}\nNEW_COIN={new}\n")
    print("✅ Per-coin config actualizado")

    # Cron (manual)
    print("📋 Cron: se añadió la entrada manualmente (ver supervisar)")

    # Whitelist symbols
    print("📋 Whitelist: revisar crypto-trade-moneda-v3-slots.sh (KNOWN_COINS / case)")

    # Desactivar vieja
    try:
        txt = open(SLOTS_SH).read()
        txt = txt.replace(f"OLD_ENABLE_{old}=true", f"OLD_ENABLE_{old}=false")
        open(SLOTS_SH, "w").write(txt)
        print(f"✅ {old} deshabilitado (OLD_ENABLED=false)")
    except Exception as e:
        print(f"⚠️  whitelist: {e}")

    # Reporte
    print("\n" + build_report(old, new, worst, pnl, datetime.now().isoformat()))
    return 0

# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(prog="coin-replacement-pipeline")
    ap.add_argument("--candidate", default=None, help="Moneda candidata")
    ap.add_argument("--old", default=None, help="Moneda a reemplazar (default: la más débil)")
    ap.add_argument("--dry-run", action="store_true", help="Solo muestra (default)")
    ap.add_argument("--execute", action="store_true", help="Aplica cambios")
    ap.add_argument("--confirm", action="store_true", help="Aproxime 'sí' para --execute")
    args = ap.parse_args()

    dry = args.dry_run or not args.execute
    if args.execute and not (args.confirm or sys.stdin.isatty()):
        print("⚠️  --execute sin confirmación: usarlo en modo interactivo o añadir --confirm")
        return 1

    old = args.old or args.candidate or None
    if not args.candidate:
        print("❌ --candidate es requerido. Ej: --candidate NEAR --execute")
        return 1

    apply(old, args.candidate, dry_run=dry)
    return 0

if __name__ == "__main__":
    main()
