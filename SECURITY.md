# Security Policy

## Reporting a Vulnerability
Si encontrás una vulnerabilidad, por favor no abras un issue público.
Envianos un mensaje privado por el medio acordado o usa el canal seguro definido por el proyecto.

## Credenciales y secretos
Este proyecto **no contiene** API keys, secrets ni tokens.
Si lo usás, creá tus propios archivos en `secrets/` y asegurate de que nunca se suban a git.

## Configuración recomendada
- Usá `secrets/binance.env.example` y `secrets/telegram.env.example` como base.
- Nunca compartas tus variables reales.
- Configurá `secrets/.gitignore` y validá con `git-secrets` o `gitleaks` antes de abrir el repo.

## IP Whitelist y exposure mínima
- Si exponés el dashboard, filtrá por IP o poné un reverse proxy autenticado.
- El acceso a Binance debe salir solo por la IP autorizada en tu API key.

## Estado del proyecto
- FASE 1 pública con controles activos.
- Canal principal: Telegram.
- Reportes y alertas deben mantener sin exposición datos sensibles.
