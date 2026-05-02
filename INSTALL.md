# 🚀 Guía de Instalación - Perrobotillo Trading Bot

**Tiempo estimado:** 15-20 minutos  
**Nivel:** Intermedio

---

## 📋 PRE-REQUISITOS

Antes de empezar, necesitás:

- [ ] Raspberry Pi 5 o Linux (Ubuntu/Debian)
- [ ] Conexión a internet
- [ ] Cuenta en Binance verificada
- [ ] 10-15 minutos de tiempo
- [ ] $100+ USDT para trading (mínimo recomendado)

---

## PASO 1: Clonar el Repositorio (2 min)

```bash
# Crear directorio para el bot
mkdir -p ~/bots
cd ~/bots

# Clonar el repositorio
git clone git@github.com:overgon/perrobotillo-trading-bot.git

# Entrar al directorio
cd perrobotillo-trading-bot
```

---

## PASO 2: Instalar OpenClaw (5 min)

```bash
# Instalar OpenClaw globalmente
npm install -g openclaw

# Verificar instalación
openclaw --version

# Inicializar OpenClaw (primer uso)
openclaw onboard

# Seguir el asistente de configuración
# - Aceptar defaults
# - Configurar workspace
# - Listo!
```

---

## PASO 3: Configurar API Keys de Binance (5 min)

### 3.1 Crear API Key en Binance

1. **Ve a:** [Binance API Management](https://www.binance.com/en/my/settings/api-management)

2. **Click en "Create API"**

3. **Nombrá tu key:** `Perrobotillo-Bot`

4. **Configuración de permisos:**
   ```
   ✅ Enable Reading: SÍ
   ✅ Enable Spot & Margin Trading: SÍ
   ❌ Enable Withdrawals: NO (NUNCA!)
   ```

5. **Guardá tus credenciales:**
   - API Key: `abcd1234...` (copiá)
   - Secret Key: `xyz789...` (copiá)
   - ⚠️ El Secret Key solo se muestra UNA VEZ

### 3.2 Configurar IP Whitelist

1. **Obtené tu IP pública:**
   ```bash
   curl https://api.ipify.org
   # Ejemplo: 187.188.230.163
   ```

2. **En Binance API Management:**
   - Click "Edit" en tu API key
   - En "IP Whitelist", agregá tu IP
   - Marcá "Restrict access to trusted IPs only"
   - Guardar

### 3.3 Crear archivo de secrets

```bash
# Crear directorio secrets (ya existe, pero verificamos)
mkdir -p secrets

# Copiar el archivo de ejemplo
cp secrets/binance.env.example secrets/binance.env

# Editar con tus credenciales
nano secrets/binance.env
```

**Reemplazá:**
```bash
BINANCE_API_KEY="tu_api_key_aqui"
BINANCE_SECRET_KEY="tu_secret_key_aqui"
PUBLIC_IP="tu_ip_publica_aqui"
```

**Guardar y salir:** `Ctrl+X`, `Y`, `Enter`

### 3.4 Proteger el archivo

```bash
# Solo vos podés leer/escribir
chmod 600 secrets/binance.env

# Verificar permisos
ls -la secrets/binance.env
# Debería mostrar: -rw------- (600)
```

---

## PASO 4: Configurar Telegram (Opcional, 3 min)

### 4.1 Crear Bot de Telegram

1. **Abrí Telegram** y buscá [@BotFather](https://t.me/botfather)

2. **Enviá:** `/newbot`

3. **Seguí las instrucciones:**
   - Nombre: `Perrobotillo Trading Bot`
   - Username: `PerrobotilloBot` (debe terminar en `Bot`)

4. **Guardá el token:**
   ```
   Use this token to access the HTTP API:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

### 4.2 Obtener tu Chat ID

1. **Buscá [@userinfobot](https://t.me/userinfobot)**

2. **Enviá cualquier mensaje**

3. **Te responderá con tu Chat ID:**
   ```
   Id: 7543955537
   ```

### 4.3 Configurar en el bot

```bash
# Copiar archivo de ejemplo
cp secrets/telegram.env.example secrets/telegram.env

# Editar
nano secrets/telegram.env
```

**Reemplazá:**
```bash
TELEGRAM_BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_CHAT_ID="7543955537"
```

**Proteger:**
```bash
chmod 600 secrets/telegram.env
```

---

## PASO 5: Verificar Configuración (2 min)

```bash
# Ejecutar script de verificación
./check-public-ip.sh
```

**Deberías ver:**
```
✅ API Binance: Conectada
✅ IP Whitelist: Verificada
✅ Secrets: Configurados
✅ Permisos: Correctos
```

**Si algo falla:**
- ❌ API: Verificá tus keys en `secrets/binance.env`
- ❌ IP: Actualizá tu IP en Binance y en el archivo
- ❌ Permisos: `chmod 600 secrets/*`

---

## PASO 6: Configurar OpenClaw (3 min)

```bash
# Verificar estado de OpenClaw
openclaw status

# Deberías ver:
# - Gateway: running
# - Telegram: OK (si configuraste)
# - Model: qwen3.5:cloud (o local)
```

**Si Telegram no está configurado:**

```bash
# Editar configuración de OpenClaw
nano ~/.openclaw/openclaw.json

# Buscá la sección "channels" y agregá:
"channels": {
  "telegram": {
    "botToken": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "enabled": true
  }
}

# Reiniciar gateway
openclaw gateway restart
```

---

## PASO 7: Probar el Bot (2 min)

### 7.1 Verificar balances

```bash
# Ver tu portfolio en Binance
curl -s --request GET \
  --url "https://api.binance.com/api/v3/account" \
  --header "X-MBX-APIKEY: $(jq -r '.BINANCE_API_KEY' secrets/binance.env)" \
  --data-urlencode "timestamp=$(date +%s000)" \
  --data-urlencode "signature=$(echo -n "timestamp=$(date +%s000)" | openssl dgst -sha256 -hmac "$(jq -r '.BINANCE_SECRET_KEY' secrets/binance.env)" | awk '{print $2}')" \
  | jq '.balances[] | select(.free != "0.00000000")'
```

### 7.2 Iniciar el bot (modo prueba)

```bash
# Iniciar SOLO BTC primero (para probar)
./crypto-trade-moneda-v3-slots.sh BTC

# Ver logs
tail -f logs/trade-BTC.log
```

**Deberías ver:**
```
[2026-05-02 12:00:00] [BTC] 🤖 Perrobotillo Trading Bot iniciado
[2026-05-02 12:00:01] [BTC] ✅ API Binance: Conectada
[2026-05-02 12:00:02] [BTC] 📊 Precio actual: $78,420.00
[2026-05-02 12:00:03] [BTC] 💰 USDT disponible: $1,100.00
[2026-05-02 12:00:04] [BTC] 🎯 Buscando oportunidades...
```

### 7.3 Verificar en Telegram

Si configuraste Telegram, deberías recibir un mensaje:
```
🐕 Perrobotillo Bot Iniciado

✅ BTC: Monitoreo activo
💰 USDT: $1,100.00
📊 Precio: $78,420.00
```

---

## PASO 8: Iniciar Todas las Monedas

```bash
# Iniciar bot para todas las monedas
for coin in BTC ETH BNB SOL LINK XRP AVAX; do
    echo "Iniciando $coin..."
    ./crypto-trade-moneda-v3-slots.sh $coin &
done

echo "✅ Todas las monedas iniciadas"
```

---

## PASO 9: Configurar Automatización (Opcional)

### 9.1 Reporte Diario (9 AM)

```bash
# Editar crontab
crontab -e

# Agregar al final:
0 9 * * * /home/overgon/bots/perrobotillo-trading-bot/daily-report-9am.sh
```

### 9.2 Monitoreo de IP (cada hora)

```bash
# Agregar al crontab:
0 * * * * /home/overgon/bots/perrobotillo-trading-bot/check-public-ip.sh
```

### 9.3 Alertas de Drawdown (cada 30 min)

```bash
# Agregar al crontab:
*/30 * * * * /home/overgon/bots/perrobotillo-trading-bot/check-drawdown-alert.sh
```

---

## ✅ CHECKLIST FINAL

Antes de operar con dinero real:

- [ ] OpenClaw instalado y funcionando
- [ ] API keys configuradas en Binance
- [ ] IP whitelist actualizada en Binance
- [ ] `secrets/binance.env` creado y protegido (600)
- [ ] Telegram configurado (opcional)
- [ ] Script de verificación pasó sin errores
- [ ] Bot de prueba (BTC) funcionando
- [ ] Todas las monedas iniciadas
- [ ] Cron jobs configurados (opcional)
- [ ] Leíste SECURITY.md y entendés los riesgos

---

## 🆘 SOLUCIÓN DE PROBLEMAS

### "API key invalid"

```bash
# Verificar que las keys están correctas
cat secrets/binance.env | grep BINANCE

# Verificar que no hay espacios extra
# Debería ser: BINANCE_API_KEY="abcd1234..." (sin espacios)
```

### "IP not whitelisted"

```bash
# Verificar tu IP actual
curl https://api.ipify.org

# Comparar con la IP en Binance
# Si son diferentes, actualizá en Binance y en secrets/binance.env
```

### "Permission denied"

```bash
# Dar permisos de ejecución
chmod +x *.sh
chmod +x crypto-bots/*.sh

# Verificar permisos de secrets
ls -la secrets/
# Debería ser: -rw------- (600)
```

### Bot no opera

```bash
# Verificar logs
tail -100 logs/trade-BTC.log

# Verificar estado
openclaw status

# Reiniciar gateway
openclaw gateway restart
```

---

## 📞 SOPORTE

Si tenés problemas:

1. **Revisá los logs:**
   ```bash
   tail -100 logs/trade-BTC.log
   ```

2. **Verificá el estado:**
   ```bash
   openclaw status
   ```

3. **Creá un issue en GitHub:**
   - [github.com/overgon/perrobotillo-trading-bot/issues](https://github.com/overgon/perrobotillo-trading-bot/issues)
   - Incluí logs (SIN secrets)

4. **Discord OpenClaw:**
   - [discord.com/invite/clawd](https://discord.com/invite/clawd)

---

<div align="center">

**¡LISTO! 🎉**

*Ahora Perrobotillo está operando por vos*

🐕 *"Nunca confiar, siempre verificar"*

</div>
