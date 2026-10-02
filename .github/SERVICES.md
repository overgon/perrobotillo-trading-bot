# 🔧 Systemd Services - Perrobotillo Trading Bot

**Última actualización:** 2026-05-16

---

## ✅ Servicios Configurados (Auto-Start)

Todos los servicios están configurados para **iniciar automáticamente** después de un reinicio o corte de luz.

### Servicios Principales

| Servicio | Estado | Auto-Start | Descripción |
|----------|--------|------------|-------------|
| **openclaw.service** | ✅ Active | ✅ Enabled | OpenClaw Gateway (core) |
| **perrobotillo-dashboard.service** | ✅ Active | ✅ Enabled | Dashboard web |
| **perrobotillo-tp-monitor.service** | ✅ Active | ✅ Enabled | TP Monitor (30s scan) |
| **perrobotillo-ngrok.service** | ✅ Active | ✅ Enabled | HTTPS tunnel |
| **perrobotillo-watchdog.service** | ✅ Active | ✅ Enabled | Health monitor |
| **perrobotillo-auto-adjust.service** | ✅ Active | ✅ Enabled | Auto-Adjust (6h) |
| **perrobotillo-daily-report.service** | ✅ Active | ✅ Enabled | Daily Report (9 AM) |

**Total:** 7/7 servicios operativos 🎉

---

## 📝 Detalles de Servicios

### openclaw.service
```ini
Description: OpenClaw Gateway Service
Type: simple
User: overgon
Restart: always
Auto-Start: ✅ Enabled
```

### perrobotillo-dashboard.service
```ini
Description: Perrobotillo Dashboard - Cyberpunk Edition
Type: simple
User: overgon
WorkingDirectory: /home/overgon/.openclaw/workspace/dashboard
ExecStart: python3 app.py
Restart: always
Auto-Start: ✅ Enabled
```

### perrobotillo-tp-monitor.service
```ini
Description: Perrobotillo TP Monitor - Real-time TP 100% Detection
Type: simple
User: overgon
WorkingDirectory: /home/overgon/.openclaw/workspace
ExecStart: /bin/bash -c 'while true; do ./tp-monitor.sh; sleep 30; done'
Restart: always
Auto-Start: ✅ Enabled
```

### perrobotillo-watchdog.service (NUEVO - 2026-05-16)
```ini
Description: Perrobotillo Watchdog - System Health Monitor
Type: simple
User: overgon
WorkingDirectory: /home/overgon/.openclaw/workspace
ExecStart: /bin/bash -c 'while true; do ./watchdog.sh; sleep 60; done'
Restart: always
Auto-Start: ✅ Enabled
```

### perrobotillo-auto-adjust.service (NUEVO - 2026-05-16)
```ini
Description: Perrobotillo Auto-Adjust Strategy - Market Mode Detection
Type: simple
User: overgon
WorkingDirectory: /home/overgon/.openclaw/workspace/crypto-bots
ExecStart: /bin/bash -c 'while true; do ./auto-adjust-strategy.sh; sleep 21600; done'
Restart: always
Auto-Start: ✅ Enabled
Interval: 6 hours (21600s)
```

### perrobotillo-daily-report.service (NUEVO - 2026-05-16)
```ini
Description: Perrobotillo Daily Report - 9 AM Telegram Report
Type: simple
User: overgon
WorkingDirectory: /home/overgon/.openclaw/workspace
ExecStart: /bin/bash -c 'while true; do ./daily-report-9am.sh; sleep 86400; done'
Restart: always
Auto-Start: ✅ Enabled
Interval: 24 hours (86400s)
```

---

## 🔧 Comandos Útiles

### Ver estado de todos los servicios
```bash
systemctl list-units --type=service | grep perrobotillo
```

### Ver estado detallado
```bash
systemctl status perrobotillo-dashboard.service
```

### Reiniciar un servicio
```bash
sudo systemctl restart perrobotillo-dashboard.service
```

### Ver logs
```bash
journalctl -u perrobotillo-dashboard.service -f
```

### Habilitar servicio (auto-start)
```bash
sudo systemctl enable perrobotillo-watchdog.service
```

### Deshabilitar servicio
```bash
sudo systemctl disable perrobotillo-watchdog.service
```

---

## 🚨 Recovery After Power Loss

Después de un corte de luz, todos los servicios:
1. **Inician automáticamente** al boot
2. **Reintentan** si fallan (Restart=always)
3. **Esperan 10s** entre retries (RestartSec=10)

**Verificación post-reinicio:**
```bash
# Verificar que todos estén activos
systemctl list-units --type=service | grep perrobotillo

# Debería mostrar todos como "active (running)"
```

---

## 📊 Health Check

Script para verificar todos los servicios:

```bash
#!/bin/bash
echo "=== Perrobotillo Services Status ==="
for service in openclaw perrobotillo-dashboard perrobotillo-tp-monitor perrobotillo-ngrok perrobotillo-watchdog perrobotillo-auto-adjust perrobotillo-daily-report; do
    status=$(systemctl is-active $service.service 2>/dev/null)
    if [ "$status" = "active" ]; then
        echo "✅ $service: $status"
    else
        echo "❌ $service: $status"
    fi
done
```

---

<div align="center">

**🐕 Perrobotillo Trading Bot** - *"Nunca confiar, siempre verificar"*

Todos los servicios configurados para auto-start después de corte de luz ✅

</div>
