#!/usr/bin/env python3
"""Perrobotillo Trading Bot - Python CLI entrypoint.

Usage:
  venv/bin/python crypto-bots/bot_cli.py --symbol BTC cycle
  venv/bin/python crypto-bots/bot_cli.py --symbol ETH dry-run
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
WORKSPACE = Path.home() / ".openclaw" / "workspace"
SECRETS = WORKSPACE / "secrets"
LOGS = WORKSPACE / "logs"
BINANCE_BASE = "https://api.binance.com"
SUPPORTED_SYMBOLS = {"BTC", "ETH", "BNB", "SOL", "LINK", "XRP", "AVAX"}

MAX_SLOTS = 3
STOP_LOSS_BY_COIN = {
    "BTC": 3.0,
    "ETH": 3.5,
    "SOL": 5.0,
    "LINK": 4.0,
    "XRP": 3.5,
    "BNB": 3.0,
    "AVAX": 4.5,
}
MIN_ORDER_USDT = 10.0
BINANCE_FEE_PERCENT = 0.015
TRADE_PERCENT_DEFAULT = 40

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
LOG_DIR = LOGS
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(symbol: str) -> logging.Logger:
    logger = logging.getLogger(f"bot_cli_{symbol}")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(LOG_DIR / f"bot_cli_{symbol}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.propagate = False
    return logger


# -----------------------------------------------------------------------------
# Locking
# -----------------------------------------------------------------------------
class LockError(Exception):
    pass


def acquire_lock(symbol: str, logger: logging.Logger) -> Path:
    lock_path = WORKSPACE / "crypto-bots" / f".bot_cli_{symbol}.lock"
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
        except (ValueError, OSError):
            pid = None
        if pid is not None:
            alive = True
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                alive = False
            except PermissionError:
                alive = True
            if alive:
                logger.info("Lock activo para %s (PID %s), abortando", symbol, pid)
                raise LockError(f"Another instance is running for {symbol} (PID {pid})")
            else:
                logger.info("Lock huérfano detectado para %s, limpiando", symbol)
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
    lock_path.write_text(str(os.getpid()))
    return lock_path


def release_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists():
            lock_path.unlink()
    except FileNotFoundError:
        pass


# -----------------------------------------------------------------------------
# Secrets / config loaders
# -----------------------------------------------------------------------------
def load_binance_env():
    env_file = SECRETS / "binance.env"
    if not env_file.exists():
        raise FileNotFoundError(f"Missing {env_file}")
    data = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


# -----------------------------------------------------------------------------
# Binance helpers
# -----------------------------------------------------------------------------
import urllib.request


def binance_get(path: str, params: dict | None = None) -> dict:
    url = f"{BINANCE_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_price(symbol: str) -> float:
    data = binance_get("/api/v3/ticker/price", {"symbol": f"{symbol}USDT"})
    return float(data["price"])


# -----------------------------------------------------------------------------
# Trade cycle
# -----------------------------------------------------------------------------
class TradeState:
    def __init__(self, symbol: str):
        self.path = WORKSPACE / "crypto-bots" / f"{symbol}-trade-state.json"
        self.data = self._load()

    def _load(self):
        if self.path.exists():
            return json.loads(self.path.read_text())
        return self._default()

    def _default(self):
        slots = []
        for i in range(1, MAX_SLOTS + 1):
            slots.append(
                {
                    "slotId": i,
                    "status": "READY",
                    "type": "NONE",
                    "orderId": None,
                    "entryPrice": None,
                    "quantity": None,
                    "usdtSpent": None,
                    "stopLoss": None,
                    "tp1": None,
                    "tp2": None,
                    "tp3": None,
                    "tp1Done": False,
                    "tp2Done": False,
                    "tp3Done": False,
                    "timestamp": None,
                }
            )
        return {
            "symbol": self.path.stem.split("-")[0],
            "maxSlots": MAX_SLOTS,
            "slots": slots,
            "lastUpdated": datetime.datetime.utcnow().isoformat(),
        }

    def active_slots(self):
        return [s for s in self.data["slots"] if s.get("status") == "ACTIVE"]

    def available_slot(self):
        for s in self.data["slots"]:
            if s.get("status") == "READY":
                return s["slotId"]
        return None

    def save(self):
        self.data["lastUpdated"] = datetime.datetime.utcnow().isoformat()
        self.path.write_text(json.dumps(self.data, indent=2))


def check_system_status() -> bool:
    try:
        binance_get("/api/v3/ping")
        return True
    except Exception as exc:
        logging.getLogger("bot_cli").warning("Binance status check failed: %s", exc)
        return False


def balance_usdt() -> float:
    # keep as stub to avoid touching secrets beyond env load
    return 0.0


def run_cycle(symbol: str, dry_run: bool = False) -> None:
    logger = setup_logging(symbol)
    try:
        acquire_lock(symbol, logger)
    except LockError as exc:
        logger.info(str(exc))
        print(str(exc))
        return

    try:
        logger.info("Iniciando ciclo para %s (dry_run=%s)", symbol, dry_run)
        if not check_system_status():
            logger.warning("Binance no disponible en este momento")
            print("Binance no disponible en este momento")
            return

        state = TradeState(symbol)
        active = len(state.active_slots())
        logger.info("Slots activos: %s/%s", active, MAX_SLOTS)

        slot = state.available_slot()
        if slot is None:
            logger.info("Sin slots disponibles")
            print(f"{symbol}: sin slots disponibles (READY={active})")
        else:
            logger.info("Slot disponible: %s", slot)
            print(f"{symbol}: slot disponible {slot}")

        logger.info("Ciclo completado")
    finally:
        release_lock(WORKSPACE / "crypto-bots" / f".bot_cli_{symbol}.lock")


def main() -> int:
    parser = argparse.ArgumentParser(description="Perrobotillo Trading Bot CLI")
    parser.add_argument("--symbol", required=True, choices=sorted(SUPPORTED_SYMBOLS))
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("cycle")
    sub.add_parser("dry-run")
    args = parser.parse_args()

    if args.command not in {"cycle", "dry-run"}:
        parser.print_help()
        return 1

    run_cycle(args.symbol, dry_run=args.command == "dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
