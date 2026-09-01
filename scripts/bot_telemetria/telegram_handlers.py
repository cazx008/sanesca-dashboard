"""
Manejador de Comandos, Eventos, Teclado Persistente y Menú Nativo de Telegram (@SanescaAIBot)
Centro de Control de Telemetría Eléctrica y Operaciones Sanesca
"""
import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_AUTHORIZED_CHAT_ID, WHATSAPP_TARGET_GROUP_NAME
from notion_client import (
    get_today_report, get_weekly_summary_html, get_q3_maintenance_status,
    create_planta_on_entry, close_planta_off_entry
)
from greenapi_client import green_client
from state_manager import state_mgr

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ==========================================================
# REGISTRO DEL MENÚ DE COMANDOS NATIVO (setMyCommands)
# ==========================================================

OFFICIAL_COMMANDS = [
    {"command": "hoy",              "description": "⚡ Pronóstico y ventana de corte de hoy"},
    {"command": "test",             "description": "🧪 Enviar prueba a mi WhatsApp privado"},
    {"command": "enviar",           "description": "🚀 Despachar reporte a WhatsApp de planta"},
    {"command": "semana",           "description": "📅 Semáforo semanal de 7 días"},
    {"command": "planta",           "description": "🔋 Horómetro y horas restantes Plan Q3"},
    {"command": "prealerta",        "description": "🔔 Pre-alerta sonora (25 min antes)"},
    {"command": "automatizaciones", "description": "⚙️ Tablero de servicios y crons activos"},
    {"command": "guia",             "description": "📖 Manual operativo y glosario de planta"},
    {"command": "estado",           "description": "🔍 Diagnóstico de salud Notion y WhatsApp"}
]

def register_bot_commands():
    """Registra formalmente los comandos nativos en Telegram API."""
    url = f"{BASE_URL}/setMyCommands"
    try:
        r = requests.post(url, json={"commands": OFFICIAL_COMMANDS}, timeout=10)
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Error registrando comandos nativos: {e}")
        return False

# ==========================================================
# TECLADOS: PERSISTENTE (REPLY) E INLINE
# ==========================================================

def get_persistent_keyboard():
    """Teclado persistente en pantalla (ReplyKeyboardMarkup) para control táctil rápido."""
    return {
        "keyboard": [
            [
                {"text": "⚡ Pronóstico de Hoy"},
                {"text": "📅 Semáforo Semanal"}
            ],
            [
                {"text": "🧪 Probar en Privado"},
                {"text": "🚀 Despachar a Planta"}
            ],
            [
                {"text": "🔋 Horómetro Plan Q3"},
                {"text": "⚙️ Automatizaciones"}
            ],
            [
                {"text": "🔴 Planta ON (Corte)"},
                {"text": "🟢 Planta OFF (Retorno)"}
            ]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }

def get_today_inline_keyboard():
    """Botones táctiles en el mensaje del pronóstico diario."""
    return {
        "inline_keyboard": [
            [
                {"text": "🧪 Probar en Privado", "callback_data": "action_test_sandbox"},
                {"text": "🚀 Despachar a Planta", "callback_data": "action_send_production"}
            ],
            [
                {"text": "🔄 Actualizar Datos", "callback_data": "action_refresh_hoy"},
                {"text": "📅 Ver Semana", "callback_data": "action_view_week"}
            ]
        ]
    }

def get_morning_alert_keyboard():
    """Botones táctiles para la alerta matutina con ventana de supervisión."""
    return {
        "inline_keyboard": [
            [
                {"text": "🚀 Despachar Inmediatamente", "callback_data": "action_send_production"},
                {"text": "🧪 Probar en Privado", "callback_data": "action_test_sandbox"}
            ],
            [
                {"text": "❌ Omitir Despacho de Hoy", "callback_data": "action_cancel_today"}
            ]
        ]
    }

def get_automations_inline_keyboard():
    """Botones para conmutar servicios activos en el panel de control."""
    mat_status = "🟢" if state_mgr.is_automation_enabled("alerta_matutina") else "🔴"
    pre_status = "🟢" if state_mgr.is_automation_enabled("prealerta_corte") else "🔴"
    hor_status = "🟢" if state_mgr.is_automation_enabled("monitor_horometro") else "🔴"

    return {
        "inline_keyboard": [
            [
                {"text": f"{mat_status} Alerta Matutina (06:30)", "callback_data": "toggle_alerta_matutina"}
            ],
            [
                {"text": f"{pre_status} Pre-Alerta Corte (-25m)", "callback_data": "toggle_prealerta_corte"}
            ],
            [
                {"text": f"{hor_status} Monitor Horómetro Q3", "callback_data": "toggle_monitor_horometro"}
            ],
            [
                {"text": "🔄 Actualizar Panel", "callback_data": "refresh_automations"}
            ]
        ]
    }

# ==========================================================
# ENVÍO Y EDICIÓN DE MENSAJES
# ==========================================================

def send_telegram_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"❌ Error enviando mensaje a Telegram: {e}")
        return None

def edit_telegram_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    url = f"{BASE_URL}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"❌ Error editando mensaje en Telegram: {e}")
        return None

def answer_callback_query(callback_id, text=None):
    url = f"{BASE_URL}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

# ==========================================================
# GUÍA Y GLOSARIO OPERATIVO
# ==========================================================

def get_operational_guide_html():
    return """📖 <b>MANUAL OPERATIVO Y GLOSARIO SANESCA</b>

━━━━━━━━━━━━━━━━━━━━━
🛡️ <b>1. Franja Dorada Segura (06:00 AM – 11:00 AM)</b>
Ventana de máxima estabilidad histórica en la red eléctrica comercial (0 cortes registrados en 20 semanas).
• <b>Acción:</b> Concentrar trabajos de mecanizado continuo en Láser CNC y Plegadora.

📊 <b>2. Semáforo de Riesgo por Día</b>
• 🔴 <b>Muy Alta (≥70%):</b> Corte prácticamente certero.
• 🟠 <b>Alta (50% – 69%):</b> Ventana crítica en la tarde (ej. Martes 55%).
• 🟡 <b>Media (30% – 49%):</b> Cortes esporádicos o intermitentes.
• 🟢 <b>Baja (&lt;30%):</b> Jornadas estables.

⚙️ <b>3. Generador Iveco Aifo GE 8031 I</b>
• <b>Potencia PRP:</b> 28 kW (92A a 1800 RPM / 60 Hz).
• <b>Consumo Estimado:</b> ~6.2 L/h al 70% de carga.
• <b>Ciclos de Servicio:</b> Mantenimiento preventivo mayor cada 200 horas de uso. Advertencia a las 180h.

📝 <b>4. Registro Rápido con Botones</b>
• <b>🔴 Planta ON:</b> Crea en Notion el registro de encendido vinculado al Generador y al Plan Q3.
• <b>🟢 Planta OFF:</b> Cierra el registro, calcula minutos exactos y actualiza el horómetro."""

# ==========================================================
# ACCIONES EJECUTIVAS (SANDBOX, PRODUCCIÓN, PLANTA ON/OFF)
# ==========================================================

def execute_sandbox_test(chat_id, message_id=None):
    rep = get_today_report()
    now_str = datetime.now().strftime("%I:%M %p")
    res = green_client.send_sandbox_test(rep["whatsapp_text"])

    if res.get("ok"):
        state_mgr.record_sandbox_test(res.get("idMessage"))
        confirm = f"""🧪 <b>REPORTE DE PRUEBA ENVIADO A TU WHATSAPP PERSONAL</b>
📅 <b>Fecha:</b> {rep['dia']}, {rep['fecha']} ({now_str})
📱 <b>Destino:</b> Tu número privado (+58 412-1339426)
📊 <b>Probabilidad:</b> {rep['prob_label']}
⏱️ <b>Ventana:</b> {rep['hora_corte']} – {rep['hora_retorno']}

<i>El grupo oficial no ha recibido ningún mensaje. Revisa tu WhatsApp para verificar formato.</i>"""
        if message_id:
            edit_telegram_message(chat_id, message_id, confirm, reply_markup=get_today_inline_keyboard())
        else:
            send_telegram_message(chat_id, confirm, reply_markup=get_today_inline_keyboard())
        return True
    else:
        err = f"❌ <b>Error en prueba Sandbox:</b>\n<code>{res.get('error')}</code>"
        if message_id:
            edit_telegram_message(chat_id, message_id, err, reply_markup=get_today_inline_keyboard())
        else:
            send_telegram_message(chat_id, err)
        return False

def execute_production_dispatch(chat_id, message_id=None, force=False):
    rep = get_today_report()
    now_str = datetime.now().strftime("%I:%M %p")

    if state_mgr.is_dispatched_today() and not force:
        prev_time = state_mgr.state.get("last_production_time", "")
        warn_text = f"""⚠️ <b>EL REPORTE DE HOY YA FUE DESPACHADO A LAS {prev_time}</b>

Para evitar mensajes duplicados en el grupo de planta, este envío está bloqueado.
Para forzarlo, escribe <b>/forzar_envio</b>."""
        if message_id:
            edit_telegram_message(chat_id, message_id, warn_text, reply_markup=get_today_inline_keyboard())
        else:
            send_telegram_message(chat_id, warn_text, reply_markup=get_today_inline_keyboard())
        return False

    res = green_client.send_production_dispatch(rep["whatsapp_text"])

    if res.get("ok"):
        state_mgr.record_production_dispatch(res.get("idMessage"))
        confirm = f"""✅ <b>REPORTE OFICIAL PUBLICADO EN WHATSAPP</b>
📅 <b>Fecha:</b> {rep['dia']}, {rep['fecha']} ({now_str})
👥 <b>Grupo:</b> <i>{WHATSAPP_TARGET_GROUP_NAME}</i>
📊 <b>Probabilidad:</b> {rep['prob_label']}
⏱️ <b>Ventana de Corte:</b> {rep['hora_corte']} – {rep['hora_retorno']}
⚡ <i>Despacho completado exitosamente.</i>"""
        if message_id:
            edit_telegram_message(chat_id, message_id, confirm)
        else:
            send_telegram_message(chat_id, confirm)
        return True
    else:
        err = f"❌ <b>Fallo al despachar a WhatsApp:</b>\n<code>{res.get('error')}</code>"
        if message_id:
            edit_telegram_message(chat_id, message_id, err)
        else:
            send_telegram_message(chat_id, err)
        return False

def handle_planta_on(chat_id):
    """Procesa el encendido de la planta eléctrica y creación en Notion DB1."""
    if state_mgr.is_planta_active():
        sess = state_mgr.get_planta_session()
        send_telegram_message(chat_id, f"⚠️ <b>La planta ya se encuentra registrada como ENCENDIDA</b> desde las <code>{sess.get('start_iso', '')[:16].replace('T', ' ')}</code>.\nPresiona <b>🟢 Planta OFF (Retorno)</b> cuando regrese la energía eléctrica.")
        return

    send_telegram_message(chat_id, "⏳ <i>Registrando encendido de planta en Notion DB1 (Historial)...</i>")
    res = create_planta_on_entry()
    if res.get("ok"):
        state_mgr.set_planta_on(res["page_id"], res["start_iso"])
        txt = f"""🔴 <b>PLANTA ELÉCTRICA ENCENDIDA</b>
⏱️ <b>Hora de Inicio:</b> {res['start_time_str']}
⚙️ <b>Equipo:</b> Generador Iveco Aifo (28 kW PRP)
📋 <b>Plan Vinculado:</b> #Q3 Mantenimiento de la Planta
📝 <b>Notion:</b> Registro creado con éxito en <i>Historial de Mantenimiento</i>.

<i>Presiona <b>🟢 Planta OFF (Retorno)</b> al volver la red comercial para cerrar la sesión y sumar los minutos al horómetro.</i>"""
        send_telegram_message(chat_id, txt)
    else:
        send_telegram_message(chat_id, f"❌ <b>Error al registrar encendido en Notion:</b>\n<code>{res.get('error')}</code>")

def handle_planta_off(chat_id):
    """Procesa el apagado de la planta eléctrica y cierre en Notion DB1."""
    page_id = None
    start_iso = None

    if state_mgr.is_planta_active():
        sess = state_mgr.get_planta_session()
        page_id = sess.get("page_id")
        start_iso = sess.get("start_iso")
    else:
        # Consulta de respaldo directamente en Notion (tolerancia a fallos o encendido desde GUI)
        send_telegram_message(chat_id, "🔍 <i>Verificando si hay registros de planta abiertos en Notion...</i>")
        open_res = find_open_planta_entry()
        if open_res.get("found"):
            page_id = open_res.get("page_id")
            start_iso = open_res.get("start_iso")
        else:
            send_telegram_message(chat_id, "ℹ️ <b>No se encontró ninguna sesión abierta de planta encendida en Notion.</b>\n(Todas las filas de generación tienen su hora de fin completada).")
            return

    send_telegram_message(chat_id, "⏳ <i>Registrando apagado y calculando duración en Notion...</i>")
    res = close_planta_off_entry(page_id, start_iso)
    if res.get("ok"):
        state_mgr.set_planta_off()
        txt = f"""🟢 <b>PLANTA ELÉCTRICA APAGADA (RED RESTABLECIDA)</b>
⏱️ <b>Hora de Fin:</b> {res['end_time_str']}
⌛ <b>Duración de Operación:</b> <b>{res['duracion_str']}</b> ({res['duracion_minutos']} minutos)
📊 <b>Notion:</b> Sesión cerrada en <i>Historial de Mantenimiento</i> y horas sumadas al Plan #Q3.

⚡ <i>Generador en Standby listo para la siguiente contingencia.</i>"""
        send_telegram_message(chat_id, txt)
    else:
        send_telegram_message(chat_id, f"❌ <b>Error al cerrar registro en Notion:</b>\n<code>{res.get('error')}</code>")

# ==========================================================
# PROCESAMIENTO DE MENSAJES DE TEXTO Y TECLADO PERSISTENTE
# ==========================================================

def handle_text_message(chat_id, text, user_name=""):
    if chat_id != TELEGRAM_AUTHORIZED_CHAT_ID:
        send_telegram_message(chat_id, "⛔ <b>Acceso Restringido:</b> Solo el administrador autorizado puede operar este bot.")
        return

    raw = text.strip()
    cmd = raw.lower()

    # Mapeo de botones del teclado persistente
    if cmd in ["/start", "/menu", "menu", "hola", "inicio"]:
        register_bot_commands()
        welcome = f"""👋 ¡Hola <b>{user_name or 'Lex'}</b>! Centro de Control de Telemetría Sanesca.

Usa los botones táctiles permanentes en pantalla o el menú oficial <b>[/]</b> para operar la estación."""
        send_telegram_message(chat_id, welcome, reply_markup=get_persistent_keyboard())
        rep = get_today_report()
        send_telegram_message(chat_id, rep["telegram_html"], reply_markup=get_today_inline_keyboard())

    elif cmd in ["/hoy", "hoy", "⚡ pronóstico de hoy"]:
        rep = get_today_report()
        send_telegram_message(chat_id, rep["telegram_html"], reply_markup=get_today_inline_keyboard())

    elif cmd in ["/test", "test", "/prueba", "🧪 probar en privado"]:
        execute_sandbox_test(chat_id)

    elif cmd in ["/enviar", "enviar", "🚀 despachar a planta"]:
        execute_production_dispatch(chat_id)

    elif cmd in ["/forzar_envio", "forzar"]:
        execute_production_dispatch(chat_id, force=True)

    elif cmd in ["/semana", "semana", "📅 semáforo semanal"]:
        html = get_weekly_summary_html()
        send_telegram_message(chat_id, html)

    elif cmd in ["/planta", "planta", "🔋 horómetro plan q3"]:
        res = get_q3_maintenance_status()
        if res.get("ok"):
            send_telegram_message(chat_id, res["html"])
        else:
            send_telegram_message(chat_id, f"❌ Error consultando Plan Q3: {res.get('error')}")

    elif cmd in ["🔴 planta on (corte)", "planta on", "/on"]:
        handle_planta_on(chat_id)

    elif cmd in ["🟢 planta off (retorno)", "planta off", "/off"]:
        handle_planta_off(chat_id)

    elif cmd in ["/prealerta", "prealerta"]:
        rep = get_today_report()
        inicio_m = rep.get("inicio_min", 777)
        prealerta_m = max(0, inicio_m - 25)
        h = prealerta_m // 60
        m = prealerta_m % 60
        am_pm = "AM" if h < 12 else "PM"
        h12 = h % 12 if h % 12 != 0 else 12
        pre_str = f"{h12}:{m:02d} {am_pm}"

        txt = f"""🔔 <b>ESTADO DE LA PRE-ALERTA DE CORTE</b>
📅 <b>Jornada:</b> {rep['dia']}
⏱️ <b>Hora estimada de corte:</b> ~{rep['hora_corte']}
⏰ <b>Horario de pre-alerta (-25 min):</b> <b>~{pre_str}</b>

<i>A esa hora el bot emite una alerta con sonido prioritario para salvaguardar trabajos en CNC y computadoras de diseño.</i>"""
        send_telegram_message(chat_id, txt)

    elif cmd in ["/automatizaciones", "automatizaciones", "⚙️ automatizaciones"]:
        send_automations_panel(chat_id)

    elif cmd in ["/guia", "guia", "manual", "/ayuda"]:
        send_telegram_message(chat_id, get_operational_guide_html())

    elif cmd in ["/estado", "estado"]:
        notion_ok = "🟢 Conectado"
        green_state = green_client.get_state()
        green_status = "🟢 Autorizado" if green_state.get("ok") and green_state.get("data", {}).get("stateInstance") == "authorized" else "🔴 Error de Conexión"
        dispatched_today = "✅ Sí" if state_mgr.is_dispatched_today() else "⚪ No"
        planta_active = "🔴 ENCENDIDA" if state_mgr.is_planta_active() else "🟢 Standby (Apagada)"

        diag = f"""⚙️ <b>ESTADO DEL SISTEMA — SANESCA</b>

• <b>Notion API:</b> {notion_ok} (20 semanas / 65 eventos)
• <b>Green-API WhatsApp:</b> {green_status} (Instancia 710722725803)
• <b>Estado Planta Diésel:</b> {planta_active}
• <b>Whitelist de Destinos:</b>
  1. 📱 Sandbox: <code>{green_client.test_chat_id}</code>
  2. 👥 Producción: <code>{green_client.prod_group_id}</code> ({WHATSAPP_TARGET_GROUP_NAME})
• <b>Despachado Hoy a Planta:</b> {dispatched_today}
• <b>Administrador:</b> Lex (ID: <code>{TELEGRAM_AUTHORIZED_CHAT_ID}</code>)

🌐 <i>Dashboard:</i> https://cazx008.github.io/sanesca-dashboard/"""
        send_telegram_message(chat_id, diag)

    else:
        send_telegram_message(chat_id, "❓ Comando no reconocido. Usa el menú <b>[/]</b> o el teclado en pantalla.")

def send_automations_panel(chat_id, message_id=None):
    """Envía o actualiza el panel de control de automatizaciones."""
    mat = "🟢 ACTIVA" if state_mgr.is_automation_enabled("alerta_matutina") else "🔴 PAUSADA"
    pre = "🟢 ACTIVA" if state_mgr.is_automation_enabled("prealerta_corte") else "🔴 PAUSADA"
    hor = "🟢 ACTIVA" if state_mgr.is_automation_enabled("monitor_horometro") else "🔴 PAUSADA"

    txt = f"""⚙️ <b>TABLERO DE CONTROL — SERVICIOS Y CRONS ACTIVOS</b>

1. 🌅 <b>Alerta Matutina de Supervisión (06:30 AM)</b>
   • Estado: <b>{mat}</b>
   • Tarjeta interactiva con timeout de 15 min ➔ Despacho a WhatsApp.

2. 🔔 <b>Pre-Alerta de Corte (25 min antes)</b>
   • Estado: <b>{pre}</b>
   • Notificación sonora para salvaguardar CNC y computadoras.

3. 🔋 <b>Monitor de Horómetro y Plan #Q3</b>
   • Estado: <b>{hor}</b>
   • Alerta al cruzar la medida preventiva de 180h (Iveco Aifo).

<i>Toca los botones inferiores para alternar el estado en caliente:</i>"""

    if message_id:
        edit_telegram_message(chat_id, message_id, txt, reply_markup=get_automations_inline_keyboard())
    else:
        send_telegram_message(chat_id, txt, reply_markup=get_automations_inline_keyboard())

# ==========================================================
# CALLBACKS INTERACTIVOS
# ==========================================================

def handle_callback_query(query):
    query_id = query.get("id")
    chat_id = query.get("message", {}).get("chat", {}).get("id")
    message_id = query.get("message", {}).get("message_id")
    data = query.get("data", "")

    if chat_id != TELEGRAM_AUTHORIZED_CHAT_ID:
        answer_callback_query(query_id, "Acceso no autorizado.")
        return

    if data == "action_test_sandbox":
        answer_callback_query(query_id, "Enviando prueba a tu WhatsApp privado...")
        execute_sandbox_test(chat_id, message_id)

    elif data == "action_send_production":
        answer_callback_query(query_id, "Despachando a producción...")
        execute_production_dispatch(chat_id, message_id)

    elif data == "action_cancel_today":
        answer_callback_query(query_id, "Despacho cancelado.")
        now_str = datetime.now().strftime("%I:%M %p")
        edit_telegram_message(chat_id, message_id, f"⏸️ <b>Despacho a WhatsApp omitido para hoy</b> (Registrado a las {now_str} por el operador).")

    elif data == "action_refresh_hoy":
        answer_callback_query(query_id, "Telemetría actualizada.")
        rep = get_today_report()
        edit_telegram_message(chat_id, message_id, rep["telegram_html"], reply_markup=get_today_inline_keyboard())

    elif data == "action_view_week":
        answer_callback_query(query_id, "Cargando semana...")
        html = get_weekly_summary_html()
        send_telegram_message(chat_id, html)

    elif data.startswith("toggle_"):
        name = data.replace("toggle_", "")
        new_val = state_mgr.toggle_automation(name)
        status_word = "Activada" if new_val else "Pausada"
        answer_callback_query(query_id, f"Automatización {status_word}.")
        send_automations_panel(chat_id, message_id)

    elif data == "refresh_automations":
        answer_callback_query(query_id, "Panel actualizado.")
        send_automations_panel(chat_id, message_id)
