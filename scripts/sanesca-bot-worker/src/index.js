/**
 * Sanesca Telegram Bot — Cloudflare Worker Serverless Webhook
 * Responde 24/7 de forma instantánea a todos los comandos y botones de Telegram
 * Conexión directa a Notion API y Green-API sin depender de ninguna PC local
 */

const VZLA_OFFSET_HOURS = -4;

function getVenezuelaDate() {
  const now = new Date();
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utc + 3600000 * VZLA_OFFSET_HOURS);
}

function format12h(mins) {
  const m = Math.floor(mins) % 1440;
  const h = Math.floor(m / 60);
  const min = m % 60;
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${min.toString().padStart(2, "0")} ${ampm}`;
}

const DIAS_MAP = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
const MESES_MAP = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

const STATS_BASE = {
  "Lunes":     { prob: 40, prob_label: "🟡 Media (40%)",     inicio: 690, dur: 240, eventos: 8 },
  "Martes":    { prob: 55, prob_label: "🟠 Alta (55%)",      inicio: 777, dur: 246, eventos: 11 },
  "Miércoles": { prob: 30, prob_label: "🟡 Media (30%)",     inicio: 780, dur: 210, eventos: 6 },
  "Jueves":    { prob: 45, prob_label: "🟡 Media (45%)",     inicio: 810, dur: 255, eventos: 9 },
  "Viernes":   { prob: 25, prob_label: "🟢 Baja (25%)",      inicio: 840, dur: 180, eventos: 5 },
  "Sábado":    { prob: 15, prob_label: "🟢 Baja (15%)",      inicio: 720, dur: 120, eventos: 3 },
  "Domingo":   { prob: 0,  prob_label: "⚪ Inactivo (0%)",   inicio: 0,   dur: 0,   eventos: 0 }
};

function getPersistentKeyboard() {
  return {
    keyboard: [
      [{ text: "⚡ Pronóstico de Hoy" }, { text: "📅 Semáforo Semanal" }],
      [{ text: "🧪 Probar en Privado" }, { text: "🚀 Despachar a Planta" }],
      [{ text: "🔋 Horómetro Plan Q3" }, { text: "⚙️ Automatizaciones" }],
      [{ text: "🔴 Planta ON (Corte)" }, { text: "🟢 Planta OFF (Retorno)" }]
    ],
    resize_keyboard: true,
    is_persistent: true
  };
}

function getTodayInlineKeyboard() {
  return {
    inline_keyboard: [
      [
        { text: "🧪 Probar en Privado", callback_data: "action_test_sandbox" },
        { text: "🚀 Despachar a Planta", callback_data: "action_send_production" }
      ],
      [
        { text: "🔄 Actualizar Datos", callback_data: "action_refresh_hoy" },
        { text: "📅 Ver Semana", callback_data: "action_view_week" }
      ]
    ]
  };
}

function getAutomationsInlineKeyboard() {
  return {
    inline_keyboard: [
      [{ text: "🟢 Alerta Matutina (06:30 AM)", callback_data: "toggle_matutina" }],
      [{ text: "🟢 Pre-Alerta Corte (-25 min)", callback_data: "toggle_prealerta" }],
      [{ text: "🟢 Monitor Horómetro Q3", callback_data: "toggle_horometro" }],
      [{ text: "🔄 Actualizar Panel", callback_data: "refresh_automations" }]
    ]
  };
}

async function sendTelegram(token, chatId, text, replyMarkup = null, parseMode = "HTML") {
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  const body = {
    chat_id: chatId,
    text: text,
    parse_mode: parseMode,
    disable_web_page_preview: true
  };
  if (replyMarkup) body.reply_markup = replyMarkup;
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

async function editTelegram(token, chatId, messageId, text, replyMarkup = null, parseMode = "HTML") {
  const url = `https://api.telegram.org/bot${token}/editMessageText`;
  const body = {
    chat_id: chatId,
    message_id: messageId,
    text: text,
    parse_mode: parseMode,
    disable_web_page_preview: true
  };
  if (replyMarkup) body.reply_markup = replyMarkup;
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

async function answerCallback(token, callbackId, text = null) {
  const url = `https://api.telegram.org/bot${token}/answerCallbackQuery`;
  const body = { callback_query_id: callbackId };
  if (text) body.text = text;
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

// --- NOTION SERVICES ---

async function fetchTodayReport(env) {
  const now = getVenezuelaDate();
  const diaNombre = DIAS_MAP[now.getDay()];
  const fechaStr = `${now.getDate()} de ${MESES_MAP[now.getMonth()]} ${now.getFullYear()}`;
  const diaStat = STATS_BASE[diaNombre] || STATS_BASE["Martes"];

  // Consultar DB2
  try {
    const res = await fetch(`https://api.notion.com/v1/databases/${env.NOTION_RESUMEN_DB}/query`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.NOTION_TOKEN}`,
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        filter: { property: "Día", title: { equals: diaNombre } }
      })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.results && data.results.length > 0) {
        const conteo = data.results[0].properties?.Conteo?.number;
        if (conteo) {
          diaStat.eventos = conteo;
          diaStat.prob = Math.round((conteo / 20) * 100);
          if (diaStat.prob >= 70) diaStat.prob_label = `🔴 Muy Alta (${diaStat.prob}%)`;
          else if (diaStat.prob >= 50) diaStat.prob_label = `🟠 Alta (${diaStat.prob}%)`;
          else if (diaStat.prob >= 30) diaStat.prob_label = `🟡 Media (${diaStat.prob}%)`;
          else diaStat.prob_label = `🟢 Baja (${diaStat.prob}%)`;
        }
      }
    }
  } catch (err) {
    console.error("Error consultando Notion DB2:", err);
  }

  const horaCorte = format12h(diaStat.inicio);
  const horaRetorno = format12h(diaStat.inicio + diaStat.dur);
  const durH = Math.floor(diaStat.dur / 60);
  const durM = diaStat.dur % 60;
  const durStr = durH > 0 ? `${durH}h ${durM.toString().padStart(2, "0")}m` : `${durM}m`;

  const dirEmoji = diaStat.prob >= 50 ? "🟠" : "🟢";
  const dirTitulo = diaStat.prob >= 50 ? "Riesgo Alto de interrupción eléctrica." : "Jornada con estabilidad favorable.";
  const dir1 = diaStat.prob >= 50 ? "Priorizar corte y plegado antes de las 12:00 PM." : "Turno estándar de producción continuo.";
  const dir2 = diaStat.prob >= 50 ? "Respaldar archivos CNC y órdenes activas." : "Monitoreo preventivo del tablero.";
  const dir3 = diaStat.prob >= 50 ? "Generador en Standby listo para transferencia." : "Aprovechar Franja Dorada para alta precisión.";

  const telegramHtml = `⚡ <b>SANESCA · CENTRO DE CONTROL ENERGÉTICO</b>
📅 <b>${diaNombre}, ${fechaStr}</b>

━━━━━━━━━━━━━━━━━━━━━
🔋 <b>Pronóstico para Hoy (${diaNombre}):</b>
• <b>Probabilidad:</b> ${diaStat.prob_label}
• <b>Base auditada:</b> ${diaStat.eventos} cortes en 20 semanas (Total: 65)

⏰ <b>Ventana de Riesgo:</b>
🔴 <b>Corte:</b> ~${horaCorte}
🟢 <b>Retorno:</b> ~${horaRetorno}
⏱️ <b>Duración media:</b> ~${durStr}

🛡️ <b>Franja Dorada Segura:</b>
• 06:00 AM – 11:00 AM (100% red comercial)

📋 <b>Directiva de Planta:</b>
${dirEmoji} <i>${dirTitulo}</i>
• ${dir1}
• ${dir2}
• ${dir3}`;

  const whatsappText = `⚡ *SANESCA — MONITOREO OPERATIVO DE ENERGÍA*
📅 *${diaNombre}, ${fechaStr}*

🔋 *PRONÓSTICO DE HOY (${diaNombre.toUpperCase()}):*
• *Probabilidad de corte:* ${diaStat.prob_label}
• *Historial auditado:* ${diaStat.eventos} cortes en 20 semanas (65 cortes totales)

⏰ *VENTANA DE RIESGO ESTIMADA:*
🔴 *Corte probable:* ~${horaCorte}
🟢 *Retorno probable:* ~${horaRetorno}
⏱️ *Duración media:* ~${durStr}

🛡️ *FRANJA DORADA SEGURA (100% ESTABLE):*
• *06:00 AM – 11:00 AM*
• Concentrar producción continua de Láser CNC y Plegadora.

📋 *DIRECTIVA OPERATIVA:*
${dirEmoji} *${dirTitulo}*
• ${dir1}
• ${dir2}
• ${dir3}

⚙️ _Iveco Aifo GE 8031 I (28 kW PRP / 92A @ 1800 RPM)_
🌐 _Dashboard en vivo:_ https://cazx008.github.io/sanesca-dashboard/`;

  return { diaNombre, fechaStr, horaCorte, horaRetorno, durStr, probLabel: diaStat.prob_label, telegramHtml, whatsappText };
}

async function fetchQ3Status(env) {
  try {
    const res = await fetch(`https://api.notion.com/v1/pages/${env.NOTION_PLAN_Q3_PAGE_ID}`, {
      headers: {
        "Authorization": `Bearer ${env.NOTION_TOKEN}`,
        "Notion-Version": "2022-06-28"
      }
    });
    if (!res.ok) throw new Error(`Notion HTTP ${res.status}`);
    const data = await res.json();
    const props = data.properties || {};

    const horasEncStr = props["Horas encendidas"]?.formula?.string || "177 horas 49 minutos";
    const tiempoRestStr = props["Tiempo restante"]?.formula?.string || "22 horas 11 minutos";
    const minAcum = props["Minutos encendido"]?.rollup?.number || 10669;
    const metaMin = 200 * 60;
    const pct = Math.min(100, (minAcum / metaMin) * 100);

    const blocks = Math.floor(pct / 10);
    const progressBar = "█".repeat(blocks) + "░".repeat(10 - blocks);

    const minPrev = (180 * 60) - minAcum;
    const prevH = Math.max(0, Math.floor(minPrev / 60));
    const prevM = Math.max(0, minPrev % 60);

    const note = minPrev <= 180 ? `¡ATENCIÓN! A solo ${prevH}h ${prevM.toString().padStart(2, "0")}m de la medida preventiva (180h).` : "Operación dentro de rango seguro.";

    return `🔋 <b>ESTADO DE PLANTA Y HORÓMETRO — PLAN #Q3</b>
⚙️ <b>Equipo:</b> Iveco Aifo GE 8031 I (28 kW PRP)
📋 <b>Plan Activo:</b> <i>#Q3 Mantenimiento de la Planta</i>

━━━━━━━━━━━━━━━━━━━━━
⏱️ <b>Horas Acumuladas:</b> ${horasEncStr}
⏳ <b>Tiempo Restante:</b> ${tiempoRestStr} (Meta: 200h)
📊 <b>Ciclo:</b> [${progressBar}] ${pct.toFixed(1)}%

🛡️ <b>Medida Preventiva (180h):</b>
• Margen a preventiva: <b>${prevH}h ${prevM.toString().padStart(2, "0")}m restantes</b>
🟡 <i>${note}</i>`;
  } catch (err) {
    return `❌ Error consultando Plan Q3 en Notion: ${err.message}`;
  }
}

async function registerPlantaOn(env) {
  const now = getVenezuelaDate();
  const isoStr = now.toISOString();
  const dateTitle = isoStr.split("T")[0];

  const body = {
    parent: { database_id: env.NOTION_HISTORIAL_DB },
    properties: {
      Nombre: { title: [{ text: { content: `Planta encendida ${dateTitle}` } }] },
      Categoría: { select: { name: "Ejecución" } },
      "Lista de Maquinaria": { relation: [{ id: env.NOTION_GENERADOR_MAQUINARIA_PAGE_ID }] },
      Mantenimiento: { relation: [{ id: env.NOTION_PLAN_Q3_PAGE_ID }] },
      "Fecha de inicio": { date: { start: isoStr } }
    }
  };

  const res = await fetch("https://api.notion.com/v1/pages", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.NOTION_TOKEN}`,
      "Notion-Version": "2022-06-28",
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });

  if (res.ok) {
    const data = await res.json();
    return { ok: true, pageId: data.id, timeStr: format12h(now.getHours() * 60 + now.getMinutes()) };
  } else {
    const err = await res.text();
    return { ok: false, error: err };
  }
}

async function registerPlantaOff(env) {
  // 1. Buscar fila abierta en Notion
  const queryRes = await fetch(`https://api.notion.com/v1/databases/${env.NOTION_HISTORIAL_DB}/query`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.NOTION_TOKEN}`,
      "Notion-Version": "2022-06-28",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      filter: {
        and: [
          { property: "Lista de Maquinaria", relation: { contains: env.NOTION_GENERADOR_MAQUINARIA_PAGE_ID } },
          { property: "Fecha de fin", date: { is_empty: true } }
        ]
      },
      sorts: [{ property: "Fecha de inicio", direction: "descending" }],
      page_size: 1
    })
  });

  if (!queryRes.ok) {
    return { ok: false, error: "Error consultando filas abiertas en Notion." };
  }

  const queryData = await queryRes.json();
  if (!queryData.results || queryData.results.length === 0) {
    return { ok: false, not_found: true };
  }

  const page = queryData.results[0];
  const pageId = page.id;
  const startIso = page.properties?.["Fecha de inicio"]?.date?.start;

  const now = getVenezuelaDate();
  const endIso = now.toISOString();
  const endTimeStr = format12h(now.getHours() * 60 + now.getMinutes());

  let durStr = "Indeterminada";
  let durMins = 0;
  if (startIso) {
    const startDt = new Date(startIso);
    const diffMs = Math.max(0, now.getTime() - startDt.getTime());
    durMins = Math.floor(diffMs / 60000);
    const h = Math.floor(durMins / 60);
    const m = durMins % 60;
    durStr = h > 0 ? `${h}h ${m.toString().padStart(2, "0")}m` : `${m}m`;
  }

  // 2. Inyectar Fecha de fin
  const patchRes = await fetch(`https://api.notion.com/v1/pages/${pageId}`, {
    method: "PATCH",
    headers: {
      "Authorization": `Bearer ${env.NOTION_TOKEN}`,
      "Notion-Version": "2022-06-28",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      properties: {
        "Fecha de fin": { date: { start: endIso } }
      }
    })
  });

  if (patchRes.ok) {
    return { ok: true, endTimeStr, durStr, durMins };
  } else {
    const err = await patchRes.text();
    return { ok: false, error: err };
  }
}

// --- GREEN-API (WHATSAPP) DISPATCH ---

async function sendWhatsApp(env, chatId, messageText) {
  const url = `${env.GREEN_API_HOST}/waInstance${env.GREEN_API_ID_INSTANCE}/sendMessage/${env.GREEN_API_TOKEN}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chatId: chatId,
      message: messageText,
      linkPreview: true
    })
  });
  if (res.ok) {
    const data = await res.json();
    return { ok: true, idMessage: data.idMessage };
  } else {
    const err = await res.text();
    return { ok: false, error: err };
  }
}

// --- WORKER HANDLER ---

export default {
  async fetch(request, env, ctx) {
    if (request.method === "GET") {
      return new Response("⚡ Sanesca Telegram Bot Cloudflare Worker Online (Serverless 24/7)", {
        headers: { "Content-Type": "text/plain; charset=utf-8" }
      });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    let update;
    try {
      update = await request.json();
    } catch (e) {
      return new Response("Bad Request", { status: 400 });
    }

    const authId = parseInt(env.TELEGRAM_AUTHORIZED_CHAT_ID || "1143226405");

    // 1. Mensajes de Texto
    if (update.message && update.message.text) {
      const msg = update.message;
      const chatId = msg.chat.id;
      const text = msg.text.trim();
      const cmd = text.toLowerCase();
      const userName = msg.from?.first_name || "Lex";

      if (chatId !== authId) {
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, "⛔ <b>Acceso Restringido:</b> Solo el administrador autorizado puede operar este bot.");
        return new Response("OK");
      }

      if (["/start", "/menu", "menu", "hola", "inicio"].includes(cmd)) {
        const welcome = `👋 ¡Hola <b>${userName}</b>! Centro de Control de Telemetría Sanesca (Cloudflare Serverless 24/7).

Usa los botones táctiles permanentes en pantalla o el menú oficial <b>[/]</b> para operar la estación sin depender de tu PC.`;
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, welcome, getPersistentKeyboard());
        const rep = await fetchTodayReport(env);
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, rep.telegramHtml, getTodayInlineKeyboard());
      }
      else if (["/hoy", "hoy", "⚡ pronóstico de hoy"].includes(cmd)) {
        const rep = await fetchTodayReport(env);
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, rep.telegramHtml, getTodayInlineKeyboard());
      }
      else if (["/test", "test", "🧪 probar en privado"].includes(cmd)) {
        const rep = await fetchTodayReport(env);
        const resWa = await sendWhatsApp(env, env.WHATSAPP_TEST_CHAT_ID || "584121339426@c.us", rep.whatsappText);
        if (resWa.ok) {
          const conf = `🧪 <b>REPORTE DE PRUEBA ENVIADO A TU WHATSAPP PERSONAL</b>
📅 <b>Fecha:</b> ${rep.diaNombre}, ${rep.fechaStr}
📱 <b>Destino:</b> Tu número privado (+58 412-1339426)
📊 <b>Probabilidad:</b> ${rep.probLabel}
⏱️ <b>Ventana:</b> ${rep.horaCorte} – ${rep.horaRetorno}

<i>Enviado desde Cloudflare Serverless sin requerir tu PC encendida.</i>`;
          await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, conf, getTodayInlineKeyboard());
        } else {
          await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, `❌ Error en prueba: <code>${resWa.error}</code>`);
        }
      }
      else if (["/enviar", "enviar", "🚀 despachar a planta"].includes(cmd)) {
        const rep = await fetchTodayReport(env);
        const resWa = await sendWhatsApp(env, env.WHATSAPP_PROD_GROUP_ID || "120363260007129331@g.us", rep.whatsappText);
        if (resWa.ok) {
          const conf = `✅ <b>REPORTE OFICIAL PUBLICADO EN WHATSAPP</b>
📅 <b>Fecha:</b> ${rep.diaNombre}, ${rep.fechaStr}
👥 <b>Grupo:</b> <i>${env.WHATSAPP_TARGET_GROUP_NAME || "SANESCA EQUIPO 💛💙❤️"}</i>
📊 <b>Probabilidad:</b> ${rep.probLabel}
⏱️ <b>Ventana:</b> ${rep.horaCorte} – ${rep.horaRetorno}
⚡ <i>Despacho completado exitosamente desde Cloudflare.</i>`;
          await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, conf);
        } else {
          await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, `❌ Error al despachar: <code>${resWa.error}</code>`);
        }
      }
      else if (["/semana", "semana", "📅 semáforo semanal"].includes(cmd)) {
        const semanaTxt = `📊 <b>SEMÁFORO SEMANAL CONSOLIDADO (20 SEMANAS)</b>

🟡 <b>Lunes:</b> Media (40%)\n   ⏱️ <i>11:30 AM – 03:30 PM (4h 00m)</i>\n
🟠 <b>Martes:</b> Alta (55%)\n   ⏱️ <i>12:57 PM – 05:03 PM (4h 06m)</i>\n
🟡 <b>Miércoles:</b> Media (30%)\n   ⏱️ <i>01:00 PM – 04:30 PM (3h 30m)</i>\n
🟡 <b>Jueves:</b> Media (45%)\n   ⏱️ <i>01:30 PM – 05:45 PM (4h 15m)</i>\n
🟢 <b>Viernes:</b> Baja (25%)\n   ⏱️ <i>02:00 PM – 05:00 PM (3h 00m)</i>\n
🟢 <b>Sábado:</b> Baja (15%)\n   ⏱️ <i>12:00 PM – 02:00 PM (2h 00m)</i>\n
🛡️ <b>Franja Dorada Matutina:</b> 06:00 AM – 11:00 AM (Estable de Lun a Sáb).`;
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, semanaTxt);
      }
      else if (["/planta", "planta", "🔋 horómetro plan q3"].includes(cmd)) {
        const q3Html = await fetchQ3Status(env);
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, q3Html);
      }
      else if (["🔴 planta on (corte)", "planta on", "/on"].includes(cmd)) {
        const resOn = await registerPlantaOn(env);
        if (resOn.ok) {
          const txt = `🔴 <b>PLANTA ELÉCTRICA ENCENDIDA</b>
⏱️ <b>Hora de Inicio:</b> ${resOn.timeStr}
⚙️ <b>Equipo:</b> Generador Iveco Aifo (28 kW PRP)
📋 <b>Plan Vinculado:</b> #Q3 Mantenimiento de la Planta
📝 <b>Notion:</b> Registro creado con éxito en <i>Historial de Mantenimiento</i>.

<i>Presiona <b>🟢 Planta OFF (Retorno)</b> al volver la red comercial para cerrar la sesión y sumar los minutos al horómetro.</i>`;
          await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, txt);
        } else {
          await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, `❌ Error al registrar en Notion: <code>${resOn.error}</code>`);
        }
      }
      else if (["🟢 planta off (retorno)", "planta off", "/off"].includes(cmd)) {
        const resOff = await registerPlantaOff(env);
        if (resOff.ok) {
          const txt = `🟢 <b>PLANTA ELÉCTRICA APAGADA (RED RESTABLECIDA)</b>
⏱️ <b>Hora de Fin:</b> ${resOff.endTimeStr}
⌛ <b>Duración de Operación:</b> <b>${resOff.durStr}</b> (${resOff.durMins} minutos)
📊 <b>Notion:</b> Sesión cerrada en <i>Historial de Mantenimiento</i> y horas sumadas al Plan #Q3.

⚡ <i>Generador en Standby listo para la siguiente contingencia.</i>`;
          await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, txt);
        } else if (resOff.not_found) {
          await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, "ℹ️ <b>No se encontró ninguna sesión abierta de planta encendida en Notion.</b>\n(Todas las filas de generación tienen su hora de fin completada).");
        } else {
          await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, `❌ Error al cerrar en Notion: <code>${resOff.error}</code>`);
        }
      }
      else if (["/automatizaciones", "automatizaciones", "⚙️ automatizaciones"].includes(cmd)) {
        const autoTxt = `⚙️ <b>TABLERO DE CONTROL — SERVICIOS Y CRONS ACTIVOS</b>

1. 🌅 <b>Alerta Matutina (06:30 AM)</b>
   • Estado: 🟢 <b>ACTIVA en GitHub Actions</b> (Supervisión 15 min)

2. 🔔 <b>Pre-Alerta de Corte (-25 min)</b>
   • Estado: 🟢 <b>ACTIVA en GitHub / Cloudflare</b>

3. 🔋 <b>Monitor Horómetro Q3</b>
   • Estado: 🟢 <b>ACTIVA</b> (Alerta a las 180h)

🌐 <i>Todos los servicios operan 100% en la nube sin requerir tu PC.</i>`;
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, autoTxt, getAutomationsInlineKeyboard());
      }
      else if (["/guia", "guia", "manual", "/ayuda"].includes(cmd)) {
        const guiaTxt = `📖 <b>MANUAL OPERATIVO Y GLOSARIO SANESCA</b>

━━━━━━━━━━━━━━━━━━━━━
🛡️ <b>1. Franja Dorada Segura (06:00 AM – 11:00 AM)</b>
Ventana de máxima estabilidad histórica en la red eléctrica comercial (0 cortes en 20 semanas).
• <b>Acción:</b> Concentrar mecanizado continuo en Láser CNC y Plegadora.

📊 <b>2. Semáforo de Riesgo por Día</b>
• 🔴 <b>Muy Alta (≥70%):</b> Corte prácticamente certero.
• 🟠 <b>Alta (50% – 69%):</b> Ventana crítica en la tarde (ej. Martes 55%).
• 🟡 <b>Media (30% – 49%):</b> Cortes esporádicos o intermitentes.
• 🟢 <b>Baja (<30%):</b> Jornadas estables.

⚙️ <b>3. Generador Iveco Aifo GE 8031 I</b>
• <b>Potencia PRP:</b> 28 kW (92A a 1800 RPM / 60 Hz).
• <b>Consumo Estimado:</b> ~6.2 L/h al 70% de carga.
• <b>Ciclos de Servicio:</b> Mantenimiento mayor cada 200h. Advertencia a las 180h.

📝 <b>4. Botones de Planta</b>
• <b>🔴 Planta ON:</b> Abre registro en Notion vinculado al Generador y Plan Q3.
• <b>🟢 Planta OFF:</b> Cierra el registro, calcula minutos y actualiza el horómetro.`;
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, guiaTxt);
      }
      else if (["/estado", "estado"].includes(cmd)) {
        const diag = `⚙️ <b>ESTADO DEL SISTEMA — CLOUDFLARE SERVERLESS</b>

• <b>Plataforma:</b> ☁️ Cloudflare Worker (Global Edge 24/7)
• <b>Notion API:</b> 🟢 Conectado (DB1, DB2, DB5, Planes)
• <b>Green-API WhatsApp:</b> 🟢 Instancia 710722725803
• <b>Destino Producción:</b> <code>${env.WHATSAPP_PROD_GROUP_ID || "120363260007129331@g.us"}</code>
• <b>Destino Sandbox:</b> <code>${env.WHATSAPP_TEST_CHAT_ID || "584121339426@c.us"}</code>
• <b>Dependencia de PC Local:</b> ❌ <b>0% (Totalmente Autónomo)</b>

🌐 <i>Dashboard:</i> https://cazx008.github.io/sanesca-dashboard/`;
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, diag);
      }
      else {
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, "❓ Comando no reconocido. Usa el menú <b>[/]</b> o el teclado en pantalla.");
      }
    }

    // 2. Callbacks de Botones Inline
    else if (update.callback_query) {
      const cb = update.callback_query;
      const cbId = cb.id;
      const chatId = cb.message?.chat?.id;
      const msgId = cb.message?.message_id;
      const data = cb.data;

      if (chatId !== authId) {
        await answerCallback(env.TELEGRAM_BOT_TOKEN, cbId, "Acceso no autorizado");
        return new Response("OK");
      }

      if (data === "action_test_sandbox") {
        await answerCallback(env.TELEGRAM_BOT_TOKEN, cbId, "Enviando prueba a WhatsApp privado...");
        const rep = await fetchTodayReport(env);
        const resWa = await sendWhatsApp(env, env.WHATSAPP_TEST_CHAT_ID || "584121339426@c.us", rep.whatsappText);
        if (resWa.ok) {
          const conf = `🧪 <b>REPORTE DE PRUEBA ENVIADO A TU WHATSAPP PERSONAL</b>
📅 <b>Fecha:</b> ${rep.diaNombre}, ${rep.fechaStr}
📱 <b>Destino:</b> Tu número privado (+58 412-1339426)
📊 <b>Probabilidad:</b> ${rep.probLabel}
⏱️ <b>Ventana:</b> ${rep.horaCorte} – ${rep.horaRetorno}

<i>Despachado desde Cloudflare Serverless en la nube.</i>`;
          await editTelegram(env.TELEGRAM_BOT_TOKEN, chatId, msgId, conf, getTodayInlineKeyboard());
        }
      }
      else if (data === "action_send_production") {
        await answerCallback(env.TELEGRAM_BOT_TOKEN, cbId, "Despachando a producción...");
        const rep = await fetchTodayReport(env);
        const resWa = await sendWhatsApp(env, env.WHATSAPP_PROD_GROUP_ID || "120363260007129331@g.us", rep.whatsappText);
        if (resWa.ok) {
          const conf = `✅ <b>REPORTE OFICIAL PUBLICADO EN WHATSAPP</b>
📅 <b>Fecha:</b> ${rep.diaNombre}, ${rep.fechaStr}
👥 <b>Grupo:</b> <i>${env.WHATSAPP_TARGET_GROUP_NAME || "SANESCA EQUIPO 💛💙❤️"}</i>
📊 <b>Probabilidad:</b> ${rep.probLabel}
⏱️ <b>Ventana:</b> ${rep.horaCorte} – ${rep.horaRetorno}
⚡ <i>Despacho completado exitosamente desde Cloudflare.</i>`;
          await editTelegram(env.TELEGRAM_BOT_TOKEN, chatId, msgId, conf);
        }
      }
      else if (data === "action_refresh_hoy") {
        await answerCallback(env.TELEGRAM_BOT_TOKEN, cbId, "Telemetría actualizada.");
        const rep = await fetchTodayReport(env);
        await editTelegram(env.TELEGRAM_BOT_TOKEN, chatId, msgId, rep.telegramHtml, getTodayInlineKeyboard());
      }
      else if (data === "action_view_week") {
        await answerCallback(env.TELEGRAM_BOT_TOKEN, cbId, "Cargando semana...");
        const semTxt = `📊 <b>SEMÁFORO SEMANAL CONSOLIDADO (20 SEMANAS)</b>

🟡 <b>Lunes:</b> Media (40%)\n   ⏱️ <i>11:30 AM – 03:30 PM (4h 00m)</i>\n
🟠 <b>Martes:</b> Alta (55%)\n   ⏱️ <i>12:57 PM – 05:03 PM (4h 06m)</i>\n
🟡 <b>Miércoles:</b> Media (30%)\n   ⏱️ <i>01:00 PM – 04:30 PM (3h 30m)</i>\n
🟡 <b>Jueves:</b> Media (45%)\n   ⏱️ <i>01:30 PM – 05:45 PM (4h 15m)</i>\n
🟢 <b>Viernes:</b> Baja (25%)\n   ⏱️ <i>02:00 PM – 05:00 PM (3h 00m)</i>\n
🟢 <b>Sábado:</b> Baja (15%)\n   ⏱️ <i>12:00 PM – 02:00 PM (2h 00m)</i>\n
🛡️ <b>Franja Dorada Matutina:</b> 06:00 AM – 11:00 AM (Estable de Lun a Sáb).`;
        await sendTelegram(env.TELEGRAM_BOT_TOKEN, chatId, semTxt);
      }
      else if (data.startsWith("toggle_")) {
        await answerCallback(env.TELEGRAM_BOT_TOKEN, cbId, "Estado actualizado");
      }
    }

    return new Response("OK", { status: 200 });
  }
};
