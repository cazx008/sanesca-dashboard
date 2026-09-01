"""
Flujo de Despacho Matutino Autónomo con Timeout de Supervisión (15 Minutos)
Diseñado para ejecución desatendida en GitHub Actions o programador local
"""
import time
import sys
import requests
from datetime import datetime, timezone, timedelta
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_AUTHORIZED_CHAT_ID, WHATSAPP_TARGET_GROUP_NAME
from notion_client import get_today_report
from greenapi_client import green_client
from state_manager import state_mgr
from telegram_handlers import (
    send_telegram_message, edit_telegram_message,
    answer_callback_query, get_morning_alert_keyboard
)

sys.stdout.reconfigure(encoding='utf-8')
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TIMEOUT_SECONDS = 900  # 15 minutos

def run_morning_dispatch_cycle():
    now_vzla = state_mgr.get_local_now()
    today_str = now_vzla.strftime("%Y-%m-%d")
    now_fmt = now_vzla.strftime("%I:%M %p")

    print(f"🌅 Iniciando ciclo matutino de telemetría: {today_str} ({now_fmt})")

    # 1. Validación de Domingo
    if now_vzla.weekday() == 6:
        print("ℹ️ Hoy es Domingo (planta no operativa). Ciclo omitido.")
        return 0

    # 2. Control de Idempotencia
    if state_mgr.is_dispatched_today():
        print(f"ℹ️ El reporte de hoy ya fue despachado a las {state_mgr.state.get('last_production_time')}. Omitiendo.")
        return 0

    # 3. Obtener reporte de Notion
    rep = get_today_report()
    deadline_time = (now_vzla + timedelta(seconds=TIMEOUT_SECONDS)).strftime("%I:%M %p")

    alert_text = f"""🌅 <b>ALERTA MATUTINA DE PLANIFICACIÓN ({now_fmt})</b>

{rep['telegram_html']}

━━━━━━━━━━━━━━━━━━━━━
⏱️ <b>VENTANA DE SUPERVISIÓN: 15 MINUTOS</b>
Tienes hasta las <b>{deadline_time}</b> para omitir o probar.
<i>Si no respondes antes de las {deadline_time}, se auto-despachará al grupo oficial.</i>"""

    send_res = send_telegram_message(
        TELEGRAM_AUTHORIZED_CHAT_ID,
        alert_text,
        reply_markup=get_morning_alert_keyboard()
    )

    if not send_res or not send_res.get("ok"):
        print("❌ Error crítico enviando alerta matutina a Telegram.")
        return 1

    alert_message_id = send_res["result"]["message_id"]
    print(f"✅ Alerta matutina enviada a Telegram (Message ID: {alert_message_id}). Esperando supervisión hasta {deadline_time}...")

    # 4. Inicializar offset de Telegram
    last_offset = 0
    try:
        r = requests.get(f"{BASE_URL}/getUpdates?offset=-1", timeout=10)
        res = r.json()
        if res.get("ok") and res.get("result"):
            last_offset = res["result"][-1]["update_id"] + 1
    except Exception:
        pass

    start_time = time.time()
    dispatched = False

    while time.time() - start_time < TIMEOUT_SECONDS:
        elapsed = int(time.time() - start_time)
        remaining = TIMEOUT_SECONDS - elapsed

        try:
            url = f"{BASE_URL}/getUpdates?offset={last_offset}&timeout=5"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        last_offset = update["update_id"] + 1

                        # Solo procesar callbacks de este mensaje específico
                        if "callback_query" in update:
                            cb = update["callback_query"]
                            cb_msg_id = cb.get("message", {}).get("message_id")
                            cb_user_id = cb.get("from", {}).get("id")
                            cb_data = cb.get("data", "")
                            cb_id = cb.get("id")

                            if cb_user_id == TELEGRAM_AUTHORIZED_CHAT_ID:
                                if cb_data == "action_send_production":
                                    answer_callback_query(cb_id, "Despachando a WhatsApp...")
                                    print("🚀 Aprobación manual recibida. Despachando a WhatsApp...")
                                    res_wa = green_client.send_production_dispatch(rep["whatsapp_text"])
                                    if res_wa.get("ok"):
                                        state_mgr.record_production_dispatch(res_wa.get("idMessage"))
                                        confirm = f"""✅ <b>REPORTE DESPACHADO MANUALMENTE A WHATSAPP</b>
📅 <b>Fecha:</b> {rep['dia']}, {rep['fecha']} ({datetime.now().strftime('%I:%M %p')})
👥 <b>Grupo:</b> <i>{WHATSAPP_TARGET_GROUP_NAME}</i>
📊 <b>Probabilidad:</b> {rep['prob_label']}
⏱️ <b>Ventana:</b> {rep['hora_corte']} – {rep['hora_retorno']}
⚡ <i>Aprobado por el operador.</i>"""
                                        edit_telegram_message(TELEGRAM_AUTHORIZED_CHAT_ID, alert_message_id, confirm)
                                        print("✅ Despacho exitoso a producción.")
                                        return 0
                                    else:
                                        err_txt = f"❌ <b>Fallo al despachar a WhatsApp:</b>\n<code>{res_wa.get('error')}</code>"
                                        edit_telegram_message(TELEGRAM_AUTHORIZED_CHAT_ID, alert_message_id, err_txt)
                                        return 1

                                elif cb_data == "action_cancel_today":
                                    answer_callback_query(cb_id, "Despacho cancelado para hoy.")
                                    cancel_txt = f"⏸️ <b>DESPACHO OMITIDO PARA HOY</b>\nRegistrado a las {datetime.now().strftime('%I:%M %p')} por el operador.\n<i>El grupo oficial no recibirá notificación.</i>"
                                    edit_telegram_message(TELEGRAM_AUTHORIZED_CHAT_ID, alert_message_id, cancel_txt)
                                    print("⏸️ Despacho cancelado por el operador.")
                                    return 0

                                elif cb_data == "action_test_sandbox":
                                    answer_callback_query(cb_id, "Enviando a tu WhatsApp privado...")
                                    print("🧪 Enviando prueba a Sandbox...")
                                    res_sb = green_client.send_sandbox_test(rep["whatsapp_text"])
                                    if res_sb.get("ok"):
                                        sb_notice = f"🧪 <i>Copia de prueba enviada a tu WhatsApp privado. La ventana de auto-despacho sigue activa ({remaining // 60} min restantes).</i>"
                                        send_telegram_message(TELEGRAM_AUTHORIZED_CHAT_ID, sb_notice)

        except Exception as e:
            print(f"Advertencia en polling: {e}")

        time.sleep(2)

    # 5. Si expira el timeout (Auto-despacho)
    print(f"⏰ Tiempo de supervisión expirado ({TIMEOUT_SECONDS}s). Procediendo a AUTO-DESPACHO...")
    res_auto = green_client.send_production_dispatch(rep["whatsapp_text"])
    auto_time_str = datetime.now().strftime("%I:%M %p")

    if res_auto.get("ok"):
        state_mgr.record_production_dispatch(res_auto.get("idMessage"))
        auto_confirm = f"""✅ <b>REPORTE AUTO-DESPACHADO A WHATSAPP ({auto_time_str})</b>
📅 <b>Fecha:</b> {rep['dia']}, {rep['fecha']}
👥 <b>Grupo:</b> <i>{WHATSAPP_TARGET_GROUP_NAME}</i>
📊 <b>Probabilidad:</b> {rep['prob_label']}
⏱️ <b>Ventana:</b> {rep['hora_corte']} – {rep['hora_retorno']}
ℹ️ <i>Despachado automáticamente al expirar la ventana de supervisión de 15 min.</i>"""
        edit_telegram_message(TELEGRAM_AUTHORIZED_CHAT_ID, alert_message_id, auto_confirm)
        print("✅ Auto-despacho completado exitosamente.")
        return 0
    else:
        err_auto = f"❌ <b>Fallo en auto-despacho a WhatsApp:</b>\n<code>{res_auto.get('error')}</code>"
        edit_telegram_message(TELEGRAM_AUTHORIZED_CHAT_ID, alert_message_id, err_auto)
        return 1

if __name__ == "__main__":
    sys.exit(run_morning_dispatch_cycle())
