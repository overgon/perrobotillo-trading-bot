# 📊 Reporte Mensual de Trading

## Descripción

Script automático que genera un informe mensual detallado con:
- **Top performance** por moneda (mejor y peor rendimientos)
- **Rendimientos mensuales** detallados por cada una de las 7 monedas
- **Estadísticas clave**: total trades, win rate, P&L total del mes

## Ubicación

```
/home/overgon/.openclaw/workspace/scripts/monthly-report.sh
```

## Schedule (Cron)

```bash
# Día 1 de cada mes a las 9:00 AM
0 9 1 * * /home/overgon/.openclaw/workspace/scripts/monthly-report.sh >> /home/overgon/.openclaw/logs/monthly-report-cron.log 2>&1
```

## Output

### Telegram
- Reporte enviado automáticamente al canal de Telegram del Jefe
- Formato HTML con emojis y tablas

### Archivo Local
- Guardado en: `/home/overgon/.openclaw/workspace/crypto-bots/monthly-report-YYYY-MM.md`
- Formato Markdown para referencia futura

## Métricas Incluidas

### Top Performance
- 🥇 Mejor moneda del mes (mayor P&L positivo)
- 🥉 Peor moneda del mes (menor P&L o mayor pérdida)

### Rendimientos por Moneda
| Métrica | Descripción |
|---------|-------------|
| P&L | Ganancia/pérdida neta en USDT |
| Trades | Cantidad total de trades cerrados |
| Win Rate | Porcentaje de trades ganadores |

### Resumen del Mes
- P&L Total acumulado
- Total de trades ejecutados
- Wins vs Losses
- Win Rate global

### Destacados por Moneda
- Mejor trade (% gain máximo)
- Peor trade (% loss mínimo)

## Logs

- **Ejecución:** `/home/overgon/.openclaw/logs/monthly-report-cron.log`
- **Detalle:** `/home/overgon/.openclaw/logs/monthly-report.log`

## Comandos Útiles

### Probar script manualmente
```bash
/home/overgon/.openclaw/workspace/scripts/monthly-report.sh
```

### Ver últimos reportes
```bash
ls -lh /home/overgon/.openclaw/workspace/crypto-bots/monthly-report-*.md
```

### Ver logs de ejecución
```bash
tail -50 /home/overgon/.openclaw/logs/monthly-report.log
```

## Requisitos

- Archivos `*-daily-pnl.json` en `/home/overgon/.openclaw/workspace/crypto-bots/`
- Logs de trades en `/home/overgon/.openclaw/logs/trade-*.log`
- Configuración de Telegram en `~/.openclaw/openclaw.json`

---

🐕 Perrobotillo Trading Bot  
*"¡Nunca confiar, siempre verificar!"*
