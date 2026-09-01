"""
Cliente de Extracción y Formateo de Telemetría desde Notion API
Soporta DB2 (Semanal), DB5 (Dashboard), DB1 (Historial) y DB Planes de Mantenimiento (#Q3)
"""
import requests
from datetime import datetime, timezone, timedelta
from config import (
    NOTION_TOKEN, NOTION_BASE_URL, NOTION_VERSION,
    NOTION_RESUMEN_DB, NOTION_DASHBOARD_DB, NOTION_HISTORIAL_DB,
    NOTION_PLAN_Q3_PAGE_ID, NOTION_GENERADOR_MAQUINARIA_PAGE_ID,
    SEMANAS_FALLBACK, TZ_OFFSET_MIN, GENERADOR_SPECS
)

VENEZUELA_TZ = timezone(timedelta(hours=-4))
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
}

DIAS_MAP = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo"
}

def mins_to_time_str(mins):
    """Convierte minutos desde medianoche a formato legible 12h (hh:mm AM/PM)."""
    mins = int(mins) % 1440
    h = mins // 60
    m = mins % 60
    am_pm = "AM" if h < 12 else "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{m:02d} {am_pm}"

def get_today_report():
    """Extrae y formatea el reporte de telemetría de hoy desde Notion."""
    now_vzla = datetime.now(VENEZUELA_TZ)
    weekday_idx = now_vzla.weekday()
    dia_nombre = DIAS_MAP[weekday_idx]
    fecha_legible = now_vzla.strftime("%d de %B %Y").replace(
        "January", "Enero").replace("February", "Febrero").replace("March", "Marzo").replace(
        "April", "Abril").replace("May", "Mayo").replace("June", "Junio").replace(
        "July", "Julio").replace("August", "Agosto").replace("September", "Septiembre").replace(
        "October", "Octubre").replace("November", "Noviembre").replace("December", "Diciembre")

    stats_base = {
        "Lunes":     {"prob": 40, "prob_label": "🟡 Media (40%)",     "inicio": 690, "dur": 240, "eventos": 8},
        "Martes":    {"prob": 55, "prob_label": "🟠 Alta (55%)",      "inicio": 777, "dur": 246, "eventos": 11},
        "Miércoles": {"prob": 30, "prob_label": "🟡 Media (30%)",     "inicio": 780, "dur": 210, "eventos": 6},
        "Jueves":    {"prob": 45, "prob_label": "🟡 Media (45%)",     "inicio": 810, "dur": 255, "eventos": 9},
        "Viernes":   {"prob": 25, "prob_label": "🟢 Baja (25%)",      "inicio": 840, "dur": 180, "eventos": 5},
        "Sábado":    {"prob": 15, "prob_label": "🟢 Baja (15%)",      "inicio": 720, "dur": 120, "eventos": 3},
        "Domingo":   {"prob": 0,  "prob_label": "⚪ Inactivo (0%)",   "inicio": 0,   "dur": 0,   "eventos": 0}
    }

    dia_stat = stats_base.get(dia_nombre, stats_base["Martes"])

    try:
        url = f"{NOTION_BASE_URL}/databases/{NOTION_RESUMEN_DB}/query"
        payload = {
            "filter": {
                "property": "Día",
                "title": {"equals": dia_nombre}
            }
        }
        res = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                props = results[0].get("properties", {})
                conteo = props.get("Conteo", {}).get("number")
                if conteo:
                    dia_stat["eventos"] = conteo
                    dia_stat["prob"] = round((conteo / SEMANAS_FALLBACK) * 100)
                    if dia_stat["prob"] >= 70:
                        dia_stat["prob_label"] = f"🔴 Muy Alta ({dia_stat['prob']}%)"
                    elif dia_stat["prob"] >= 50:
                        dia_stat["prob_label"] = f"🟠 Alta ({dia_stat['prob']}%)"
                    elif dia_stat["prob"] >= 30:
                        dia_stat["prob_label"] = f"🟡 Media ({dia_stat['prob']}%)"
                    else:
                        dia_stat["prob_label"] = f"🟢 Baja ({dia_stat['prob']}%)"
    except Exception as e:
        print(f"Advertencia Notion DB2: {e}")

    hora_corte_str = mins_to_time_str(dia_stat["inicio"])
    hora_retorno_str = mins_to_time_str(dia_stat["inicio"] + dia_stat["dur"])
    dur_h = dia_stat["dur"] // 60
    dur_m = dia_stat["dur"] % 60
    dur_str = f"{dur_h}h {dur_m:02d}m" if dur_h > 0 else f"{dur_m}m"

    if dia_stat["prob"] >= 50:
        dir_emoji = "🟠"
        dir_titulo = "Riesgo Alto de interrupción eléctrica."
        dir_1 = "Priorizar corte y plegado antes de las 12:00 PM."
        dir_2 = "Respaldar archivos de diseño y órdenes de trabajo activas."
        dir_3 = "Mantener generador en Standby listo para transferencia."
    else:
        dir_emoji = "🟢"
        dir_titulo = "Jornada con estabilidad eléctrica favorable."
        dir_1 = "Turno estándar de mecanizado continuo permitido."
        dir_2 = "Monitoreo preventivo del tablero de transferencia."
        dir_3 = "Aprovechar franja dorada para órdenes de alta precisión."

    whatsapp_text = f"""⚡ *SANESCA — MONITOREO OPERATIVO DE ENERGÍA*
📅 *{dia_nombre}, {fecha_legible}*

🔋 *PRONÓSTICO DE HOY ({dia_nombre.upper()}):*
• *Probabilidad de corte:* {dia_stat['prob_label']}
• *Historial auditado:* {dia_stat['eventos']} cortes en {SEMANAS_FALLBACK} semanas (65 cortes totales)

⏰ *VENTANA DE RIESGO ESTIMADA:*
🔴 *Corte probable:* ~{hora_corte_str}
🟢 *Retorno probable:* ~{hora_retorno_str}
⏱️ *Duración media:* ~{dur_str}

🛡️ *FRANJA DORADA SEGURA (100% ESTABLE):*
• *06:00 AM – 11:00 AM*
• Concentrar producción continua de Láser CNC y Plegadora.

📋 *DIRECTIVA OPERATIVA:*
{dir_emoji} *{dir_titulo}*
• {dir_1}
• {dir_2}
• {dir_3}

⚙️ _{GENERADOR_SPECS['modelo']} ({GENERADOR_SPECS['potencia']})_
🌐 _Dashboard en vivo:_ https://cazx008.github.io/sanesca-dashboard/"""

    telegram_html = f"""⚡ <b>SANESCA · CENTRO DE CONTROL ENERGÉTICO</b>
📅 <b>{dia_nombre}, {fecha_legible}</b>

━━━━━━━━━━━━━━━━━━━━━
🔋 <b>Pronóstico para Hoy ({dia_nombre}):</b>
• <b>Probabilidad:</b> {dia_stat['prob_label']}
• <b>Base auditada:</b> {dia_stat['eventos']} cortes en {SEMANAS_FALLBACK} semanas (Total: 65)

⏰ <b>Ventana de Riesgo:</b>
🔴 <b>Corte:</b> ~{hora_corte_str}
🟢 <b>Retorno:</b> ~{hora_retorno_str}
⏱️ <b>Duración media:</b> ~{dur_str}

🛡️ <b>Franja Dorada Segura:</b>
• 06:00 AM – 11:00 AM (100% red comercial)

📋 <b>Directiva de Planta:</b>
{dir_emoji} <i>{dir_titulo}</i>
• {dir_1}
• {dir_2}
• {dir_3}"""

    return {
        "dia": dia_nombre,
        "fecha": fecha_legible,
        "prob": dia_stat["prob"],
        "prob_label": dia_stat["prob_label"],
        "hora_corte": hora_corte_str,
        "hora_retorno": hora_retorno_str,
        "duracion": dur_str,
        "inicio_min": dia_stat["inicio"],
        "whatsapp_text": whatsapp_text,
        "telegram_html": telegram_html
    }

def get_weekly_summary_html():
    semana = [
        ("Lunes",     "🟡", "Media (40%)",    "11:30 AM – 03:30 PM", "4h 00m"),
        ("Martes",    "🟠", "Alta (55%)",     "12:57 PM – 05:03 PM", "4h 06m"),
        ("Miércoles", "🟡", "Media (30%)",    "01:00 PM – 04:30 PM", "3h 30m"),
        ("Jueves",    "🟡", "Media (45%)",    "01:30 PM – 05:45 PM", "4h 15m"),
        ("Viernes",   "🟢", "Baja (25%)",     "02:00 PM – 05:00 PM", "3h 00m"),
        ("Sábado",    "🟢", "Baja (15%)",     "12:00 PM – 02:00 PM", "2h 00m")
    ]
    txt = "📊 <b>SEMÁFORO SEMANAL CONSOLIDADO (20 SEMANAS)</b>\n\n"
    for dia, emoji, prob, ventana, dur in semana:
        txt += f"{emoji} <b>{dia}:</b> {prob}\n   ⏱️ <i>{ventana} ({dur})</i>\n\n"
    txt += "🛡️ <b>Franja Dorada Matutina:</b> 06:00 AM – 11:00 AM (Estable de Lun a Sáb)."
    return txt

# ==========================================================
# GESTIÓN DEL PLAN #Q3 Y HORÓMETRO DEL GENERADOR
# ==========================================================

def get_q3_maintenance_status():
    """Consulta en Notion el estado vivo del Plan #Q3 del Generador Eléctrico."""
    url = f"{NOTION_BASE_URL}/pages/{NOTION_PLAN_Q3_PAGE_ID}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        props = r.json().get("properties", {})

        horas_encendidas_str = props.get("Horas encendidas", {}).get("formula", {}).get("string", "177 horas 49 minutos")
        tiempo_restante_str = props.get("Tiempo restante", {}).get("formula", {}).get("string", "22 horas 11 minutos")
        minutos_acumulados = props.get("Minutos encendido", {}).get("rollup", {}).get("number", 10669)
        minutos_restantes = props.get("Resta", {}).get("formula", {}).get("number", 1331)
        meta_horas = 200
        medida_preventiva_horas = props.get("Medida preventiva", {}).get("number", 180)

        total_minutos_meta = meta_horas * 60
        pct = min(100.0, (minutos_acumulados / total_minutos_meta) * 100) if total_minutos_meta else 0

        num_blocks = int(pct / 10)
        progress_bar = "█" * num_blocks + "░" * (10 - num_blocks)

        minutos_a_preventiva = (medida_preventiva_horas * 60) - minutos_acumulados
        prev_h = max(0, minutos_a_preventiva // 60)
        prev_m = max(0, minutos_a_preventiva % 60)

        status_emoji = "🟢"
        status_note = "Operación dentro de rango seguro."
        if minutos_a_preventiva <= 0:
            status_emoji = "🔴"
            status_note = "¡UMBRAL PREVENTIVO SUPERADO (180h)! Programar servicio mayor."
        elif minutos_a_preventiva <= 180:
            status_emoji = "🟡"
            status_note = f"¡ATENCIÓN! A solo {prev_h}h {prev_m:02d}m de la medida preventiva (180h)."

        html = f"""🔋 <b>ESTADO DE PLANTA Y HORÓMETRO — PLAN #Q3</b>
⚙️ <b>Equipo:</b> {GENERADOR_SPECS['modelo']} (28 kW PRP)
📋 <b>Plan Activo:</b> <i>#Q3 Mantenimiento de la Planta</i>

━━━━━━━━━━━━━━━━━━━━━
⏱️ <b>Horas Acumuladas:</b> {horas_encendidas_str}
⏳ <b>Tiempo Restante:</b> {tiempo_restante_str} (Meta: {meta_horas}h)
📊 <b>Ciclo:</b> [{progress_bar}] {pct:.1f}%

🛡️ <b>Medida Preventiva (180h):</b>
• Margen a preventiva: <b>{prev_h}h {prev_m:02d}m restantes</b>
{status_emoji} <i>{status_note}</i>"""

        return {
            "ok": True,
            "horas_acumuladas": horas_encendidas_str,
            "tiempo_restante": tiempo_restante_str,
            "porcentaje": pct,
            "minutos_acumulados": minutos_acumulados,
            "minutos_restantes": minutos_restantes,
            "margen_preventivo_str": f"{prev_h}h {prev_m:02d}m",
            "html": html
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ==========================================================
# REGISTRO BIDIRECCIONAL DE CORTES (Telegram ➔ Notion DB1)
# ==========================================================

def find_open_planta_entry():
    """
    Busca directamente en Notion DB1 si existe alguna fila del Generador
    cuya Fecha de fin esté vacía (sesión de planta encendida sin cerrar).
    Permite tolerar reinicios del bot o encendidos hechos desde la web de Notion.
    """
    url = f"{NOTION_BASE_URL}/databases/{NOTION_HISTORIAL_DB}/query"
    payload = {
        "filter": {
            "and": [
                {
                    "property": "Lista de Maquinaria",
                    "relation": {
                        "contains": NOTION_GENERADOR_MAQUINARIA_PAGE_ID
                    }
                },
                {
                    "property": "Fecha de fin",
                    "date": {
                        "is_empty": True
                    }
                }
            ]
        },
        "sorts": [
            {
                "property": "Fecha de inicio",
                "direction": "descending"
            }
        ],
        "page_size": 1
    }

    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=10)
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            page = results[0]
            start_date_obj = page["properties"].get("Fecha de inicio", {}).get("date", {})
            start_iso = start_date_obj.get("start") if start_date_obj else None
            return {
                "found": True,
                "page_id": page["id"],
                "start_iso": start_iso
            }
        return {"found": False}
    except Exception as e:
        print(f"Error consultando filas abiertas en Notion: {e}")
        return {"found": False, "error": str(e)}

def create_planta_on_entry():
    """Crea una fila en Historial de Mantenimiento al encender la planta."""
    now_vzla = datetime.now(VENEZUELA_TZ)
    now_iso = now_vzla.isoformat()
    fecha_titulo = now_vzla.strftime("%Y-%m-%d")

    url = f"{NOTION_BASE_URL}/pages"
    payload = {
        "parent": {"database_id": NOTION_HISTORIAL_DB},
        "properties": {
            "Nombre": {
                "title": [
                    {"text": {"content": f"Planta encendida {fecha_titulo}"}}
                ]
            },
            "Categoría": {
                "select": {"name": "Ejecución"}
            },
            "Lista de Maquinaria": {
                "relation": [{"id": NOTION_GENERADOR_MAQUINARIA_PAGE_ID}]
            },
            "Mantenimiento": {
                "relation": [{"id": NOTION_PLAN_Q3_PAGE_ID}]
            },
            "Fecha de inicio": {
                "date": {"start": now_iso}
            }
        }
    }

    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=15)
        r.raise_for_status()
        page_id = r.json().get("id")
        return {
            "ok": True,
            "page_id": page_id,
            "start_iso": now_iso,
            "start_time_str": now_vzla.strftime("%I:%M %p")
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def close_planta_off_entry(page_id, start_iso):
    """Cierra la fila en Historial de Mantenimiento al apagar la planta."""
    now_vzla = datetime.now(VENEZUELA_TZ)
    end_iso = now_vzla.isoformat()
    end_str = now_vzla.strftime("%I:%M %p")

    dur_mins = 0
    dur_str = "Indeterminada"
    if start_iso:
        try:
            start_dt = datetime.fromisoformat(start_iso)
            dur_seconds = max(0, int((now_vzla - start_dt).total_seconds()))
            dur_mins = dur_seconds // 60
            dur_h = dur_mins // 60
            dur_m = dur_mins % 60
            dur_str = f"{dur_h}h {dur_m:02d}m" if dur_h > 0 else f"{dur_m}m"
        except Exception:
            pass

    url = f"{NOTION_BASE_URL}/pages/{page_id}"
    payload = {
        "properties": {
            "Fecha de fin": {
                "date": {"start": end_iso}
            }
        }
    }

    try:
        r = requests.patch(url, headers=HEADERS, json=payload, timeout=15)
        r.raise_for_status()
        return {
            "ok": True,
            "end_time_str": end_str,
            "duracion_str": dur_str,
            "duracion_minutos": dur_mins
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
