# 🔐 Seguridad - Perrobotillo Trading Bot

## 🚨 ADVERTENCIAS CRÍTICAS

### NUNCA HAGAS ESTO:

❌ **NUNCA subas tus API keys a GitHub**
```bash
# MAL - NUNCA hagas esto:
git add secrets/binance.env  # ❌ NO!
git commit -m "Adding API keys"  # ❌ PELIGROSO!
```

❌ **NUNCA compartas tu `.env` o `secrets/`**
- No los envíes por email
- No los subas a Google Drive/Dropbox público
- No los compartas en Discord/Telegram

❌ **NUNCA des permisos de retiro a tus API keys**
- Solo: Reading + Spot Trading
- NUNCA: Withdrawals

---

## ✅ MEJORES PRÁCTICAS

### 1. API Keys de Binance

**Configuración correcta:**

```
✅ Enable Reading: SÍ
✅ Enable Spot & Margin Trading: SÍ
❌ Enable Withdrawals: NO (NUNCA)
✅ IP Whitelist: SÍ (solo tu IP pública)
```

**Pasos:**

1. Ve a [Binance API Management](https://www.binance.com/en/my/settings/api-management)

2. Crea nueva API key

3. **Marca SOLO:**
   - [x] Enable Reading
   - [x] Enable Spot & Margin Trading
   - [ ] Enable Futures
   - [ ] Enable Margin
   - [ ] Enable Withdrawals ← **NUNCA MARCAR**

4. **IP Whitelist:**
   ```
   Tu IP pública: 123.456.789.012 (ejemplo)
   [x] Restrict access to trusted IPs only
   ```

5. Guarda tu IP en `secrets/binance.env`:
   ```bash
   PUBLIC_IP="123.456.789.012"
   ```

---

### 2. Almacenamiento de Secrets

**Estructura correcta:**

```
perrobotillo-trading-bot/
├── secrets/
│   ├── .gitkeep          # ✅ Archivo vacío para mantener el directorio
│   └── binance.env       # ⚠️ EN .gitignore (NO SUBIR)
└── config/
    └── capital-config.sh # ✅ Seguro para subir
```

**Permisos correctos:**

```bash
# Secrets solo legibles por el dueño
chmod 600 secrets/binance.env
chmod 600 secrets/telegram.env

# Directorio de secrets
chmod 700 secrets/
```

---

### 3. IP Dinámica - Monitoreo

**Si tu IP es dinámica (cambia frecuentemente):**

```bash
# 1. Instalar script de monitoreo
./check-public-ip.sh

# 2. Agregar al crontab (cada hora)
crontab -e

# 3. Agregar esta línea:
0 * * * * /ruta/al/check-public-ip.sh

# 4. Configurar alertas por Telegram
# El script te avisará si tu IP cambia
```

**¿Qué pasa si mi IP cambia?**

1. El bot detectará el cambio
2. Te enviará alerta por Telegram
3. Debes actualizar la IP whitelist en Binance:
   - Ve a Binance API Management
   - Edita tu API key
   - Actualiza la IP whitelist
   - Guarda

---

### 4. Verificación de Seguridad

**Antes de operar, verifica:**

```bash
# 1. Verificar que secrets NO están en git
git ls-files secrets/
# Debería estar vacío

# 2. Verificar .gitignore existe
cat .gitignore | grep secrets
# Debería mostrar: secrets/

# 3. Verificar permisos de secrets
ls -la secrets/
# Debería ser: -rw------- (600)

# 4. Ejecutar check de seguridad
./check-public-ip.sh
```

---

### 5. Checklist de Seguridad

Antes de cada sesión de trading:

- [ ] API keys sin permisos de retiro
- [ ] IP whitelist actualizada
- [ ] Secrets con permisos 600
- [ ] .gitignore configurado
- [ ] No hay secrets en git
- [ ] Monitoreo de IP activo
- [ ] Alertas de Telegram configuradas
- [ ] Stop loss configurado
- [ ] Daily loss limit configurado

---

## 🛡️ CAPAS DE SEGURIDAD

### Nivel 1: Prevención

```bash
# .gitignore adecuado
secrets/
*.env
openclaw.json

# Permisos restrictivos
chmod 600 secrets/*
chmod 700 secrets/
```

### Nivel 2: Detección

```bash
# Monitoreo de IP
./check-public-ip.sh  # Cada hora

# Monitoreo de drawdown
./check-drawdown-alert.sh  # Cada 30 min
```

### Nivel 3: Respuesta

```bash
# Cierre de emergencia
./emergency-close-all.sh

# Verificar estado
openclaw status
```

---

## 🚨 QUÉ HACER EN EMERGENCIAS

### Si crees que tus API keys fueron comprometidas:

1. **INMEDIATAMENTE:**
   ```bash
   # Cerrar todos los trades
   ./emergency-close-all.sh
   ```

2. **Ve a Binance:**
   - API Management
   - **ELIMINA** la API key comprometida
   - Crea una nueva

3. **Actualiza secrets:**
   ```bash
   # Editar con nuevas keys
   nano secrets/binance.env
   
   # Actualizar IP whitelist en Binance
   # Agregar tu IP actual
   ```

4. **Verifica:**
   ```bash
   ./check-public-ip.sh
   ```

### Si tu IP cambió y el bot no opera:

1. **Verifica tu IP:**
   ```bash
   curl https://api.ipify.org
   ```

2. **Actualiza en Binance:**
   - API Management
   - Edit API key
   - Actualizar IP whitelist
   - Guardar

3. **Actualiza en secrets:**
   ```bash
   nano secrets/binance.env
   # Cambiar PUBLIC_IP="nueva.ip.aqui"
   ```

4. **Reinicia el bot:**
   ```bash
   # Matar procesos actuales
   pkill -f crypto-trade-moneda
   
   # Reiniciar
   for coin in BTC ETH BNB SOL LINK XRP AVAX; do
       ./crypto-trade-moneda-v3-slots.sh $coin &
   done
   ```

---

## 📋 AUDITORÍA DE SEGURIDAD

### Verificación mensual:

```bash
# 1. Revisar logs de acceso
grep -r "API" logs/ | grep -i "error"

# 2. Verificar que no hay secrets expuestos
git log --all --full-history -- secrets/
# Debería estar vacío

# 3. Verificar permisos
find secrets/ -type f -exec ls -la {} \;
# Todos deberían ser -rw-------

# 4. Rotar API keys (recomendado cada 90 días)
# - Crear nuevas keys en Binance
# - Actualizar secrets/binance.env
# - Eliminar keys antiguas
```

---

## 🔒 CHECKLIST PARA NUEVOS USUARIOS

Antes de operar con dinero real:

- [ ] Leíste este documento completo
- [ ] Entendés los riesgos del trading
- [ ] API keys creadas SIN permisos de retiro
- [ ] IP whitelist configurada en Binance
- [ ] Secrets almacenados correctamente
- [ ] .gitignore configurado
- [ ] Permisos de archivos verificados (600/700)
- [ ] Monitoreo de IP configurado
- [ ] Alertas de Telegram funcionando
- [ ] Probaste el bot en testnet o con amounts pequeños
- [ ] Entendés la estrategia de trading
- [ ] Configuraste stop loss y daily loss limit
- [ ] Tenés un plan de emergencia

---

## 📞 CONTACTO Y REPORTE DE VULNERABILIDADES

Si encontrás una vulnerabilidad de seguridad:

1. **NO la publiques públicamente**
2. Creá un issue privado en GitHub
3. O contactá directamente al mantenedor

---

<div align="center">

**⚠️ LA SEGURIDAD ES TU RESPONSABILIDAD**

*Verificá dos veces, operá una vez*

🐕 Perrobotillo Trading Bot

</div>
