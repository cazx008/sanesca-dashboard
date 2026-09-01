# ⚡ Sistema de Telemetría y Despacho Operativo — Sanesca

Sistema automatizado de monitoreo de cortes eléctricos y despacho inteligente de reportes a WhatsApp, supervisado en tiempo real mediante Telegram.

---

## 🏛️ Arquitectura de la Solución

```
Notion API (DB2 & DB5)
       │
       ▼
[ notion_client.py ] ──► Extracción 20 semanas / 65 eventos + Huso UTC-4 + Franja Dorada
       │
       ├────────────────────────────────────────┐
       ▼                                        ▼
[ telegram_handlers.py ]               [ greenapi_client.py ]
• Comandos (/hoy, /enviar, /semana)     • Pasarela Green-API
• Botones táctiles inline                • Despacho a WhatsApp
• Alerta matutina (06:30 AM)            • Grupo: SANESCA EQUIPO ❤️💙
       │                                        │
       ▼                                        ▼
Telegram (@SanescaAIBot)               WhatsApp de Planta
(Supervisión Ejecutiva / Lex)          (Operadores / Planta)
```

---

## 📂 Archivos del Módulo

| Archivo | Responsabilidad |
|---|---|
| `config.py` | Carga de variables de `.env`, validación de tokens y especificaciones del generador Iveco Aifo. |
| `notion_client.py` | Conexión a bases de datos de Notion, cálculo matemático de horarios y maquetación de textos en formatos WhatsApp y Telegram. |
| `greenapi_client.py` | Cliente HTTP REST para la pasarela Green-API (detección automática de grupo y envío). |
| `telegram_handlers.py` | Enrutador de mensajes de texto, seguridad por `chat_id` y gestión de botones táctiles interactivos. |
| `scheduler.py` | Programador de reloj local (UTC-4) para la alerta de planificación matutina a las 06:30 AM. |
| `main.py` | Bucle de ejecución principal con polling en tiempo real y tolerancia a fallos de red. |
| `Iniciar_Bot_Sanesca.bat` | Lanzador directo de Windows para arrancar el servicio en un clic. |

---

## 🤖 Comandos Disponibles en Telegram (`@SanescaAIBot`)

* `/hoy` — Muestra el pronóstico en tiempo real, probabilidad clasificada y ventana de corte de hoy. Incluye botones táctiles `[ 🚀 Enviar a WhatsApp ]` y `[ 🔄 Actualizar ]`.
* `/enviar` — Despacha el reporte inmediatamente al grupo de WhatsApp de Sanesca.
* `/semana` — Muestra el semáforo semanal consolidado de los 7 días con los cortes históricos auditados.
* `/estado` — Diagnóstico de conexión en vivo con Notion y Green-API.
* `/menu` o `/start` — Despliega la tarjeta de bienvenida con accesos rápidos.

---

## ⚙️ Configuración (`.env`)

```env
TELEGRAM_BOT_TOKEN=TU_TELEGRAM_BOT_TOKEN_AQUI
TELEGRAM_AUTHORIZED_CHAT_ID=1143226405

GREEN_API_HOST=https://7107.api.greenapi.com
GREEN_API_ID_INSTANCE=710722725803
GREEN_API_TOKEN=<TU_API_TOKEN_INSTANCE>
WHATSAPP_TARGET_GROUP_NAME=SANESCA EQUIPO 💛💙❤️

NOTION_TOKEN=TU_NOTION_TOKEN_AQUI
NOTION_RESUMEN_DB=3aa868054e2781338d94de72d7fc0d23
NOTION_DASHBOARD_DB=3c3868054e2781ffadd6c35fb3a40c03
SEMANAS_FALLBACK=20
TZ_OFFSET_MIN=240
```
