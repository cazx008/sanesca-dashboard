"""
Módulo de Programación Horaria (Scheduler)
Maneja:
1. Alerta Matutina Diaria (06:30 AM UTC-4) con supervisión
2. Pre-Alerta Preventiva de Corte (25 minutos antes del horario estimado)
3. Auditoría de Automatizaciones
"""
from datetime import datetime, timezone, timedelta
from telegram_handlers import send_morning_alert, send_telegram_message
from notion_client import get_today_report
from state_manager import state_mgr
from config import TELEGRAM_AUTHORIZED_CHAT_ID

VENEZUELA_TZ = timezone(timedelta(hours=-4))

class TelemetryScheduler:
    def __init__(self, target_hour=6, target_minute=30):
        self.target_hour = target_hour
        self.target_minute = target_minute
        self.last_morning_run_date = None
        self.last_prealert_run_date = None

    def get_local_now(self):
        return datetime.now(VENEZUELA_TZ)

    def check_morning_alert(self):
        """Verifica y ejecuta la alerta matutina de las 06:30 AM."""
        if not state_mgr.is_automation_enabled("alerta_matutina"):
            return False

        now = self.get_local_now()
        today_date = now.strftime("%Y-%m-%d")

        if self.last_morning_run_date == today_date:
            return False

        # Domingo no laborable
        if now.weekday() == 6:
            return False

        if now.hour == self.target_hour and now.minute == self.target_minute:
            self.last_morning_run_date = today_date
            print(f"⏰ [{now.strftime('%I:%M:%S %p')}] Disparando alerta matutina a Telegram...")
            res = send_morning_alert()
            if res and res.get("ok"):
                print("✅ Alerta matutina entregada en Telegram.")
            else:
                print("❌ Error entregando alerta matutina.")
            return True

        return False

    def check_prealert(self):
        """Verifica y ejecuta la pre-alerta de corte (25 minutos antes de la hora pico)."""
        if not state_mgr.is_automation_enabled("prealerta_corte"):
            return False

        now = self.get_local_now()
        today_date = now.strftime("%Y-%m-%d")

        if self.last_prealert_run_date == today_date:
            return False

        # Domingo no laborable
        if now.weekday() == 6:
            return False

        # Obtener inicio estimado en minutos desde medianoche
        rep = get_today_report()
        inicio_min = rep.get("inicio_min", 777)
        prealerta_min = max(0, inicio_min - 25)

        now_minutes = now.hour * 60 + now.minute

        if now_minutes == prealerta_min:
            self.last_prealert_run_date = today_date
            now_fmt = now.strftime("%I:%M %p")
            print(f"🔔 [{now_fmt}] Disparando Pre-Alerta Sonora de Corte...")

            msg = f"""🚨 <b>PRE-ALERTA PREVENTIVA DE CORTE ({now_fmt})</b>
━━━━━━━━━━━━━━━━━━━━━
⏱️ <b>Faltan ~25 minutos</b> para la ventana crítica estimada de hoy ({rep['hora_corte']}).

📋 <b>ACCIONES INMEDIATAS EN PLANTA:</b>
• Guardar y respaldar archivos en Láser CNC y Plegadora.
• Respaldar computadoras de diseño y administración.
• Verificar que el Generador Iveco Aifo esté en Standby listo para transferencia."""

            send_telegram_message(TELEGRAM_AUTHORIZED_CHAT_ID, msg)
            return True

        return False

    def check_and_execute(self):
        self.check_morning_alert()
        self.check_prealert()

scheduler = TelemetryScheduler(target_hour=6, target_minute=30)
