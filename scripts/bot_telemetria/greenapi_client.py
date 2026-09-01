"""
Cliente de Integración con Green-API (WhatsApp Gateway)
Resolución de Grupos y Despacho de Mensajes con Whitelist de Seguridad
"""
import requests
from config import (
    GREEN_API_HOST, GREEN_API_ID_INSTANCE, GREEN_API_TOKEN,
    WHATSAPP_TEST_CHAT_ID, WHATSAPP_PROD_GROUP_ID,
    WHATSAPP_TARGET_GROUP_NAME, is_allowed_whatsapp_chat
)

class GreenApiClient:
    def __init__(self):
        self.host = GREEN_API_HOST
        self.id_instance = GREEN_API_ID_INSTANCE
        self.token = GREEN_API_TOKEN
        self.test_chat_id = WHATSAPP_TEST_CHAT_ID
        self.prod_group_id = WHATSAPP_PROD_GROUP_ID

    def is_configured(self):
        """Verifica si las credenciales de Green-API están completas."""
        return bool(self.id_instance and self.token and not self.token.startswith("PENDIENTE"))

    def get_state(self):
        """Verifica el estado de autorización de la instancia de WhatsApp."""
        if not self.is_configured():
            return {"ok": False, "error": "Credenciales de Green-API no configuradas en .env"}
        
        url = f"{self.host}/waInstance{self.id_instance}/getStateInstance/{self.token}"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return {"ok": True, "data": r.json()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def send_message(self, chat_id, message_text):
        """Envía un mensaje validando estrictamente contra la whitelist."""
        if not self.is_configured():
            return {"ok": False, "error": "Green-API no configurado. Token pendiente."}

        # Validación de seguridad: Whitelist estricta
        if not is_allowed_whatsapp_chat(chat_id):
            return {"ok": False, "error": f"Seguridad: El chat '{chat_id}' no está en la whitelist autorizada."}

        url = f"{self.host}/waInstance{self.id_instance}/sendMessage/{self.token}"
        payload = {
            "chatId": chat_id,
            "message": message_text,
            "linkPreview": True
        }
        try:
            r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
            return {"ok": True, "idMessage": data.get("idMessage")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def send_sandbox_test(self, message_text):
        """Envía un mensaje de prueba exclusivamente al chat personal de Lex."""
        return self.send_message(self.test_chat_id, message_text)

    def send_production_dispatch(self, message_text):
        """Envía el reporte oficial al grupo de planta SANESCA EQUIPO."""
        return self.send_message(self.prod_group_id, message_text)

# Instancia global
green_client = GreenApiClient()
