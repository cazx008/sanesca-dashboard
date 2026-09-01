/**
 * fetch-notion.js
 * Extrae datos de las bases de datos de Notion de Sanesca y genera data/dashboard.json
 * 
 * DB5: Dashboard de Actualidad y Monitoreo en Vivo (1 fila)
 * DB2: Resumen Semanal de Cortes (7 filas: Lunes a Domingo)
 * 
 * Gestiona conversión de huso horario a Venezuela (UTC-4 / America/Caracas)
 * y proporciona valores base estadísticos en caso de que rollups de relaciones externas
 * no estén disponibles.
 */

const { Client } = require('@notionhq/client');
const fs = require('fs');
const path = require('path');

// --- Configuration ---
const NOTION_TOKEN = process.env.SANESCATOKEN || process.env.NOTION_TOKEN;
const DB5_ID = process.env.NOTION_DB5_ID || '3c386805-4e27-81ff-add6-c35fb3a40c03';
const DB2_ID = process.env.NOTION_DB2_ID || '3aa86805-4e27-8133-8d94-de72d7fc0d23';
const OUTPUT_DIR = path.join(__dirname, '..', 'data');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'dashboard.json');

let notion = null;
if (NOTION_TOKEN) {
  notion = new Client({ auth: NOTION_TOKEN });
} else {
  console.warn('⚠️ AVISO: Variable NOTION_TOKEN o SANESCATOKEN no definida. Se utilizarán datos base.');
}

// Línea base estadística histórica de Sanesca (20 semanas observadas / 65 cortes) - Horas de Venezuela (UTC-4)
const BASELINE_WEEKLY = {
  "Lunes": {
    dia: "Lunes", diaNumero: 1, jsDay: 1,
    horaCorteFmt: "12:28 PM", horaRetornoFmt: "5:05 PM", ventanaRiesgo: "12:28 PM – 5:05 PM",
    duracionProm: "4h 36m", probabilidad: "🟠 Alta (65%)", pctTotal: "20.0%",
    conteo: 13, semanasObservadas: 20,
    horaInicioMin: 748, horaFinMin: 1025, duracionMin: 276
  },
  "Martes": {
    dia: "Martes", diaNumero: 2, jsDay: 2,
    horaCorteFmt: "12:57 PM", horaRetornoFmt: "5:02 PM", ventanaRiesgo: "12:57 PM – 5:02 PM",
    duracionProm: "4h 06m", probabilidad: "🟠 Alta (55%)", pctTotal: "16.9%",
    conteo: 11, semanasObservadas: 20,
    horaInicioMin: 777, horaFinMin: 1022, duracionMin: 246
  },
  "Miércoles": {
    dia: "Miércoles", diaNumero: 3, jsDay: 3,
    horaCorteFmt: "11:49 AM", horaRetornoFmt: "4:11 PM", ventanaRiesgo: "11:49 AM – 4:11 PM",
    duracionProm: "4h 22m", probabilidad: "🔴 Muy Alta (80%)", pctTotal: "24.6%",
    conteo: 16, semanasObservadas: 20,
    horaInicioMin: 709, horaFinMin: 971, duracionMin: 262
  },
  "Jueves": {
    dia: "Jueves", diaNumero: 4, jsDay: 4,
    horaCorteFmt: "12:27 PM", horaRetornoFmt: "4:32 PM", ventanaRiesgo: "12:27 PM – 4:32 PM",
    duracionProm: "4h 04m", probabilidad: "🟠 Alta (65%)", pctTotal: "20.0%",
    conteo: 13, semanasObservadas: 20,
    horaInicioMin: 747, horaFinMin: 992, duracionMin: 244
  },
  "Viernes": {
    dia: "Viernes", diaNumero: 5, jsDay: 5,
    horaCorteFmt: "10:57 AM", horaRetornoFmt: "3:57 PM", ventanaRiesgo: "10:57 AM – 3:57 PM",
    duracionProm: "5h 00m", probabilidad: "🔵 Media (45%)", pctTotal: "13.8%",
    conteo: 9, semanasObservadas: 20,
    horaInicioMin: 657, horaFinMin: 957, duracionMin: 300
  },
  "Sábado": {
    dia: "Sábado", diaNumero: 6, jsDay: 6,
    horaCorteFmt: "11:00 AM", horaRetornoFmt: "4:20 PM", ventanaRiesgo: "11:00 AM – 4:20 PM",
    duracionProm: "5h 20m", probabilidad: "🟢 Baja (15%)", pctTotal: "4.6%",
    conteo: 3, semanasObservadas: 20,
    horaInicioMin: 660, horaFinMin: 980, duracionMin: 320
  },
  "Domingo": {
    dia: "Domingo", diaNumero: 7, jsDay: 0,
    horaCorteFmt: "—", horaRetornoFmt: "—", ventanaRiesgo: "—",
    duracionProm: "—", probabilidad: "⚪ Ninguna", pctTotal: "0%",
    conteo: 0, semanasObservadas: 20,
    horaInicioMin: 0, horaFinMin: 0, duracionMin: 0
  }
};

// --- Notion Property Extractors ---

function extractProperty(prop) {
  if (!prop) return null;

  switch (prop.type) {
    case 'title':
      return prop.title?.map(t => t.plain_text).join('') || '';
    case 'rich_text':
      return prop.rich_text?.map(t => t.plain_text).join('') || '';
    case 'number':
      return prop.number;
    case 'select':
      return prop.select?.name || null;
    case 'multi_select':
      return prop.multi_select?.map(s => s.name) || [];
    case 'date':
      return prop.date?.start || null;
    case 'checkbox':
      return prop.checkbox || false;
    case 'url':
      return prop.url || null;
    case 'formula':
      return extractFormulaValue(prop.formula);
    case 'rollup':
      return extractRollupValue(prop.rollup);
    case 'relation':
      return prop.relation?.map(r => r.id) || [];
    default:
      return null;
  }
}

function extractFormulaValue(formula) {
  if (!formula) return null;
  switch (formula.type) {
    case 'string': return formula.string;
    case 'number': return formula.number;
    case 'boolean': return formula.boolean;
    case 'date': return formula.date?.start || null;
    default: return null;
  }
}

function extractRollupValue(rollup) {
  if (!rollup) return null;
  switch (rollup.type) {
    case 'number': return rollup.number;
    case 'date': return rollup.date?.start || null;
    case 'array': return rollup.array?.map(item => extractProperty(item)) || [];
    default: return null;
  }
}

// Convert UTC minutes to Venezuela minutes (UTC-4 -> -240 mins)
function convertUtcMinutesToVzla(minutes) {
  if (minutes === null || minutes === undefined || minutes === 0) return 0;
  let vzlaMins = minutes - 240;
  if (vzlaMins < 0) vzlaMins += 1440;
  return vzlaMins;
}

function formatMinutesTo12h(minutes) {
  if (!minutes || minutes === 0) return '—';
  const totalMins = Math.round(minutes);
  const hours24 = Math.floor(totalMins / 60);
  const mins = totalMins % 60;
  const h12 = hours24 === 0 ? 12 : hours24 > 12 ? hours24 - 12 : hours24;
  const ampm = hours24 < 12 ? 'AM' : 'PM';
  const minsStr = mins < 10 ? '0' + mins : mins;
  return `${h12}:${minsStr} ${ampm}`;
}

// --- Data Fetching ---

async function queryDatabase(databaseId, sorts = []) {
  const allPages = [];
  let cursor = undefined;

  do {
    const response = await notion.databases.query({
      database_id: databaseId,
      start_cursor: cursor,
      page_size: 100,
      sorts: sorts,
    });

    allPages.push(...response.results);
    cursor = response.has_more ? response.next_cursor : undefined;
  } while (cursor);

  return allPages;
}

async function fetchDB5() {
  if (!notion) return null;
  console.log('📡 Consultando DB5: Dashboard de Actualidad y Monitoreo en Vivo...');
  try {
    const pages = await queryDatabase(DB5_ID);
    if (pages.length === 0) return null;

    const page = pages[0];
    const props = page.properties;

    return {
      panel: extractProperty(props['Panel']) || "⚡ Monitoreo Operativo en Tiempo Real",
      cortesDelMes: extractProperty(props['Cortes del Mes (auto)']),
      minutosTotalesMes: extractProperty(props['Minutos Totales Mes (auto)']),
      totalHorasPlanta: extractProperty(props['Total Horas Planta (Mes)']) || "0 hrs",
      frecuenciaSemanal: extractProperty(props['Frecuencia Semanal']) || "—",
      estresEnergetico: extractProperty(props['🌡️ Estrés Energético (Mes)']) || "🟡 En rango histórico normal (±15%)",
      probabilidadDeHoy: extractProperty(props['🔴 Probabilidad de Hoy']),
      progresoAnual: extractProperty(props['📅 Progreso Anual']),
      patronDeHoy: extractProperty(props['Patrón de Hoy']),
      medidorTiempo: extractProperty(props['⏱️ Medidor de Tiempo al Corte']),
      estadoOperativo: extractProperty(props['Estado Operativo']),
    };
  } catch (err) {
    console.warn('⚠️ Error al consultar DB5:', err.message);
    return null;
  }
}

async function fetchDB2() {
  if (!notion) {
    return Object.values(BASELINE_WEEKLY);
  }
  console.log('📡 Consultando DB2: Resumen Semanal de Cortes...');
  try {
    const pages = await queryDatabase(DB2_ID);
    const dayOrder = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

    const rawDays = pages
      .map(page => {
        const props = page.properties;
        const dia = extractProperty(props['Día']);
        if (!dia || dia.includes('TOTALES') || dia.includes('PROMEDIOS')) return null;

        const baseline = BASELINE_WEEKLY[dia] || {};

        let horaInicioMinRaw = extractProperty(props['Prom. Hora Inicio (auto)']);
        let horaFinMinRaw = extractProperty(props['Prom. Hora Fin (auto)']);
        let duracionMinRaw = extractProperty(props['Prom. Duración (auto)']);
        
        // Convert UTC minutes to Venezuela local time (UTC-4 / -240 min)
        let horaInicioMin = horaInicioMinRaw ? convertUtcMinutesToVzla(horaInicioMinRaw) : baseline.horaInicioMin;
        let horaFinMin = horaFinMinRaw ? convertUtcMinutesToVzla(horaFinMinRaw) : baseline.horaFinMin;
        let duracionMin = duracionMinRaw ? Math.round(duracionMinRaw) : baseline.duracionMin;

        let horaCorteFmt = (horaInicioMin && horaInicioMin > 0) ? formatMinutesTo12h(horaInicioMin) : baseline.horaCorteFmt;
        let horaRetornoFmt = (horaFinMin && horaFinMin > 0) ? formatMinutesTo12h(horaFinMin) : baseline.horaRetornoFmt;
        let ventanaRiesgo = (horaCorteFmt && horaRetornoFmt && horaCorteFmt !== '—') ? `${horaCorteFmt} – ${horaRetornoFmt}` : baseline.ventanaRiesgo;
        
        let duracionProm = (duracionMin && duracionMin > 0) 
          ? `${Math.floor(duracionMin / 60)}h ${String(duracionMin % 60).padStart(2, '0')}m` 
          : baseline.duracionProm;

        // Fórmulas dinámicas vivas de Notion (con fallback si el rollup cruzado viene vacío en la API)
        let probabilidadRaw = extractProperty(props['Probabilidad']);
        let pctTotalRaw = extractProperty(props['% del Total']);
        let conteoRaw = extractProperty(props['Conteo (auto)']);

        let isWeekdayEmpty = dia !== "Domingo" && (probabilidadRaw === "⚪ Ninguna" || probabilidadRaw === null);

        let probabilidad = isWeekdayEmpty ? baseline.probabilidad : (probabilidadRaw || baseline.probabilidad);
        let pctTotal = (isWeekdayEmpty || pctTotalRaw === "0%" || pctTotalRaw === null) && dia !== "Domingo" ? baseline.pctTotal : (pctTotalRaw || baseline.pctTotal);
        let conteo = (conteoRaw !== null && conteoRaw !== undefined && conteoRaw > 0) ? conteoRaw : baseline.conteo;
        let semanasObservadas = extractProperty(props['Semanas Observadas']) || baseline.semanasObservadas || 20;

        return {
          dia,
          diaNumero: baseline.diaNumero || extractProperty(props['Día (número)']),
          horaCorteFmt,
          horaRetornoFmt,
          ventanaRiesgo,
          duracionProm,
          probabilidad,
          pctTotal,
          conteo,
          semanasObservadas,
          horaInicioMin,
          horaFinMin,
          duracionMin
        };
      })
      .filter(Boolean);

    // Sort Lunes -> Domingo
    const sortedDays = dayOrder.map(dName => {
      const found = rawDays.find(d => d.dia === dName);
      return found || BASELINE_WEEKLY[dName];
    });

    return sortedDays;
  } catch (err) {
    console.warn('⚠️ Error al consultar DB2:', err.message);
    return Object.values(BASELINE_WEEKLY);
  }
}

function buildPatronesLookup(weeklyData) {
  const notionToJsDay = { 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 0 };
  const lookup = {};

  for (const day of weeklyData) {
    const jsDay = notionToJsDay[day.diaNumero];
    if (jsDay !== undefined) {
      lookup[jsDay] = {
        dia: day.dia,
        horaInicioMin: day.horaInicioMin ? Math.round(day.horaInicioMin) : 0,
        horaFinMin: day.horaFinMin ? Math.round(day.horaFinMin) : 0,
        duracionMin: day.duracionMin ? Math.round(day.duracionMin) : 0,
        horaCorteFmt: day.horaCorteFmt,
        duracionProm: day.duracionProm,
        probabilidad: day.probabilidad
      };
    }
  }

  return lookup;
}

// --- Main ---

async function main() {
  console.log('🚀 Sanesca Dashboard — Extracción de Datos de Notion');
  console.log(`   Timestamp: ${new Date().toISOString()}`);

  try {
    const [monthly, weekly] = await Promise.all([fetchDB5(), fetchDB2()]);
    const patronesPorDia = buildPatronesLookup(weekly);

    const dashboard = {
      buildTimestamp: new Date().toISOString(),
      monthly: monthly || {
        panel: "⚡ Monitoreo Operativo en Tiempo Real",
        cortesDelMes: 12,
        minutosTotalesMes: 510,
        totalHorasPlanta: "8.5 hrs (8h 30m)",
        frecuenciaSemanal: "3.4 cortes/sem (en curso)",
        estresEnergetico: "🟡 En rango histórico normal (±15%)",
        progresoAnual: "████████░░░░ 67% · Semana #35 (17 sem. restantes)"
      },
      weekly,
      patronesPorDia,
    };

    if (!fs.existsSync(OUTPUT_DIR)) {
      fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    }

    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(dashboard, null, 2), 'utf-8');
    console.log(`✅ Datos guardados correctamente en ${OUTPUT_FILE}`);
  } catch (error) {
    console.error('❌ Error en el proceso de extracción:', error.message);
    process.exit(1);
  }
}

main();
