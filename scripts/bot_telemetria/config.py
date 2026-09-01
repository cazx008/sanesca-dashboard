"""
Módulo de Configuración y Constantes de Entorno
Sistema de Telemetría y Despacho Operativo Sanesca
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_AUTHORIZED_CHAT_ID = int(os.getenv("TELEGRAM_AUTHORIZED_CHAT_ID", "0"))

# Green-API (WhatsApp Gateway) Settings
GREEN_API_HOST = os.getenv("GREEN_API_HOST", "https://7107.api.greenapi.com").rstrip("/")
GREEN_API_ID_INSTANCE = os.getenv("GREEN_API_ID_INSTANCE", "").strip()
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN", "").strip()

# Whitelist Estricta de WhatsApp (Protección de cuota de 3 chats)
WHATSAPP_TEST_CHAT_ID = os.getenv("WHATSAPP_TEST_CHAT_ID", "584121339426@c.us").strip()
WHATSAPP_PROD_GROUP_ID = os.getenv("WHATSAPP_PROD_GROUP_ID", "120363260007129331@g.us").strip()
WHATSAPP_TARGET_GROUP_NAME = os.getenv("WHATSAPP_TARGET_GROUP_NAME", "SANESCA EQUIPO 💛💙❤️").strip()

ALLOWED_WHATSAPP_CHATS = {WHATSAPP_TEST_CHAT_ID, WHATSAPP_PROD_GROUP_ID}

# Notion API Settings
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "").strip()
NOTION_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Bases de Datos de Notion
NOTION_HISTORIAL_DB = os.getenv("NOTION_HISTORIAL_DB", "839a0715f3e94b119b224e179001f5f1").replace("-", "")
NOTION_RESUMEN_DB = os.getenv("NOTION_RESUMEN_DB", "3aa868054e2781338d94de72d7fc0d23").replace("-", "")
NOTION_DASHBOARD_DB = os.getenv("NOTION_DASHBOARD_DB", "3c3868054e2781ffadd6c35fb3a40c03").replace("-", "")
NOTION_PLANES_DB = os.getenv("NOTION_PLANES_DB", "682f77509124472b94d4e192d11af84f").replace("-", "")

# Entidades Relacionales Fijas de Planta
NOTION_PLAN_Q3_PAGE_ID = "396868054e2780cca8d2f3db0d640631"
NOTION_GENERADOR_MAQUINARIA_PAGE_ID = "31b868054e278092b2c3ea374e76b4dd"

# Operational Parameters
SEMANAS_FALLBACK = int(os.getenv("SEMANAS_FALLBACK", "20"))
TZ_OFFSET_MIN = int(os.getenv("TZ_OFFSET_MIN", "240"))  # UTC-4 = 240 minutos

# Generador Iveco Aifo Specs
GENERADOR_SPECS = {
    "modelo": "Iveco Aifo GE 8031 I",
    "potencia": "28 kW PRP / 92A @ 1800 RPM / 60Hz",
    "consumo_l_h": 6.2,
    "ciclo_horas": 200,
    "preventiva_horas": 180
}

def is_allowed_whatsapp_chat(chat_id):
    """Garantiza que solo se envíen mensajes a los chats autorizados en whitelist."""
    return chat_id in ALLOWED_WHATSAPP_CHATS

def validate_config(require_whatsapp=False):
    """Valida que las credenciales mínimas estén presentes."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("Falta TELEGRAM_BOT_TOKEN en .env")
    if not TELEGRAM_AUTHORIZED_CHAT_ID:
        errors.append("Falta TELEGRAM_AUTHORIZED_CHAT_ID en .env")
    if not NOTION_TOKEN:
        errors.append("Falta NOTION_TOKEN en .env")
    if require_whatsapp:
        if not GREEN_API_ID_INSTANCE:
            errors.append("Falta GREEN_API_ID_INSTANCE en .env")
        if not GREEN_API_TOKEN or GREEN_API_TOKEN.startswith("PENDIENTE"):
            errors.append("Falta GREEN_API_TOKEN válido en .env")
    return errors
