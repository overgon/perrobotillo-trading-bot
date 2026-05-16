# 📋 Issues Tracker - Perrobotillo Trading Bot

**Última actualización:** 2026-05-16

---

## 🔥 Issues Activos

### #1 - 🐛 Dashboard muestra LATERAL cuando el modo real es BEAR
**Estado:** ✅ FIXED  
**Reportado:** 2026-05-16 12:26 CST  
**Fixeado:** 2026-05-16 12:35 CST  
**Labels:** `bug` `dashboard` `fixed`  
**Commit:** 9c8e887

**Descripción:**
El dashboard mostraba incorrectamente `LATERAL` en el MARKET_MODE, aunque el auto-adjust strategy había actualizado el modo a `BEAR`.

**Causa Raíz:**
El parser de `dynamic-config.env` no manejaba el prefijo `export ` (formato bash script).

**Solución:**
Agregar `.replace('export ', '')` en el parser de `dashboard/app.py`.

**Prevención Futura:**
- [ ] Agregar test unitario para parser de config files
- [ ] Validar que dashboard y bot tengan mismo estado en watchdog
- [ ] Alerta si hay discrepancia > 5 minutos

---

## 📊 Estadísticas

| Estado | Count |
|--------|-------|
| **Abiertos** | 0 |
| **En Progreso** | 0 |
| **Cerrados** | 1 |
| **Total** | 1 |

### Por Categoría
| Categoría | Count |
|-----------|-------|
| **Bugs** | 1 |
| **Features** | 0 |
| **Mejoras** | 0 |
| **Documentación** | 0 |

---

## 📝 Cómo Reportar un Issue

1. **Revisa issues existentes** - Busca si ya existe un issue similar
2. **Usa el template** - `.github/ISSUE_TEMPLATE/bug-report.md`
3. **Proporciona detalles** - Logs, screenshots, pasos para reproducir
4. **Etiqueta correctamente** - Usa labels apropiados
5. **Sigue el issue** - Responde a preguntas del equipo

---

## 🏷️ Labels Disponibles

| Label | Descripción |
|-------|-------------|
| `bug` | Algo no funciona correctamente |
| `dashboard` | Relacionado al dashboard web |
| `fixed` | Issue resuelto |
| `enhancement` | Mejora o feature request |
| `documentation` | Mejoras a documentación |
| `help wanted` | Se necesita ayuda |
| `priority:high` | Alta prioridad |
| `priority:critical` | Crítico, necesita atención inmediata |

---

## 🔄 Workflow de Issues

```
Reportado → Triaged → In Progress → Review → Fixed → Closed
```

### Estados:
1. **Reportado** - Issue nuevo, necesita revisión
2. **Triaged** - Revisado y etiquetado por el equipo
3. **In Progress** - Alguien está trabajando en ello
4. **Review** - Fix completado, necesita validación
5. **Fixed** - Fix mergeado a `main`
6. **Closed** - Issue cerrado (puede reabrirse si hay regresión)

---

## 📅 Historial de Issues

### Mayo 2026
- **#1** - Dashboard MARKET_MODE incorrecto ✅ FIXED

---

<div align="center">

**🐕 Perrobotillo Trading Bot** - *"Nunca confiar, siempre verificar"*

[Crear Nuevo Issue](https://github.com/overgon/perrobotillo-trading-bot/issues/new/choose)

</div>
