#!/usr/bin/env python3
"""
Migración de cashout-history.json v1.0 → v2.0
- Separa cashouts[] en manualCashouts[]
- Agrega autoCashouts[] vacío (listo para cierres automáticos)
- Actualiza metadata y summary
"""

import json
import sys
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
CASHOUT_FILE = WORKSPACE / "crypto-bots" / "cashout-history.json"
BACKUP_SUFFIX = ".v1-backup"

def migrate():
    # Leer archivo original
    if not CASHOUT_FILE.exists():
        print(f"❌ Error: {CASHOUT_FILE} no existe")
        return False
    
    with open(CASHOUT_FILE, 'r') as f:
        data = json.load(f)
    
    # Crear backup
    backup_path = str(CASHOUT_FILE) + BACKUP_SUFFIX
    with open(backup_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Backup creado: {backup_path}")
    
    # Migrar estructura
    migrated = {
        "version": "2.0",
        "created": data.get("created", ""),
        "totalCashouts": data.get("totalCashouts", 0),
        "totalUSDTWithdrawn": data.get("totalUSDTWithdrawn", 0),
        "totalMXNReceived": data.get("totalMXNReceived", 0),
        "avgExchangeRate": data.get("avgExchangeRate", 0),
        "autoCashouts": [],  # Nuevo array para cierres automáticos
        "manualCashouts": [],  # Cashouts manuales migrados
        "summary": {}
    }
    
    # Migrar cashouts[] → manualCashouts[]
    if "cashouts" in data:
        for i, cashout in enumerate(data["cashouts"]):
            # Agregar campos nuevos si no existen
            if "type" not in cashout:
                cashout["type"] = "MANUAL_P2P"
            if "dedupKey" not in cashout:
                # Generar dedupKey único
                date_str = cashout.get("date", "").replace("-", "").replace(":", "").replace("T", "")
                cashout["dedupKey"] = f"manual-{date_str}-{i+1}"
            
            migrated["manualCashouts"].append(cashout)
        
        print(f"✅ Migrados {len(migrated['manualCashouts'])} cashouts manuales")
    
    # Migrar summary
    if "summary" in data:
        migrated["summary"] = data["summary"]
    else:
        # Calcular summary básico
        total_manual = sum(c.get("totalUSDT", 0) for c in migrated["manualCashouts"])
        migrated["summary"] = {
            "totalTradingPnL": 0.00,
            "totalWithdrawn": total_manual,
            "remainingInBot": 0.00,
            "note": "Migrado de v1.0 a v2.0 - autoCashouts[] disponible para cierres automáticos"
        }
    
    # Agregar metadata de migración
    migrated["migrationInfo"] = {
        "fromVersion": "1.0",
        "toVersion": "2.0",
        "migratedAt": Path(backup_path).stat().st_mtime,
        "backupFile": backup_path
    }
    
    # Guardar archivo migrado
    with open(CASHOUT_FILE, 'w') as f:
        json.dump(migrated, f, indent=2, ensure_ascii=False)
    print(f"✅ Archivo migrado a v2.0: {CASHOUT_FILE}")
    
    # Validar estructura
    print("\n📊 Resumen de la migración:")
    print(f"  - autoCashouts: {len(migrated['autoCashouts'])} registros (listo para cierres automáticos)")
    print(f"  - manualCashouts: {len(migrated['manualCashouts'])} registros migrados")
    print(f"  - Backup: {backup_path}")
    
    return True

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
