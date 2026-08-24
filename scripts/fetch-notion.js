/**
 * fetch-notion.js
 * Extrae datos de dos bases de datos de Notion y genera data/dashboard.json
 * 
 * DB5: Dashboard de Actualidad y Monitoreo en Vivo (1 fila)
 * DB2: Resumen Semanal de Cortes (7 filas: Lunes a Domingo)
 * 
 * Uso: NOTION_TOKEN=ntn_xxx NOTION_DB5_ID=xxx NOTION_DB2_ID=xxx node scripts/fetch-notion.js
 */

const { Client } = require('@notionhq/client');
const fs = require('fs');
const path = require('path');

// --- Configuration ---
const NOTION_TOKEN = process.env.NOTION_TOKEN;
const DB5_ID = process.env.NOTION_DB5_ID || '3c386805-4e27-81ff-add6-c35fb3a40c03';
const DB2_ID = process.env.NOTION_DB2_ID || '3aa86805-4e27-8133-8d94-de72d7fc0d23';
const OUTPUT_DIR = path.join(__dirname, '..', 'data');
const OUTPUT_FILE = path.join(OUTPUT_DIR, 'dashboard.json');

if (!NOTION_TOKEN) {
  console.error('❌ ERROR: NOTION_TOKEN environment variable is required.');
  console.error('   Set it via: export NOTION_TOKEN=ntn_your_token');
  process.exit(1);
}

const notion = new Client({ auth: NOTION_TOKEN });

// --- Notion Property Extractors ---

/**
 * Safely extracts a value from a Notion property object.
 * Handles the deeply nested structure of Notion API responses.
 */
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

    case 'created_time':
      return prop.created_time;

    case 'last_edited_time':
      return prop.last_edited_time;

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

// --- Data Fetching ---

/**
 * Queries a Notion database with automatic pagination.
 * Returns all pages (rows) from the database.
 */
async function queryDatabase(databaseId, sorts = []) {
  const allPages = [];
  let cursor = undefined;
  let pageCount = 0;

  do {
    const response = await notion.databases.query({
      database_id: databaseId,
      start_cursor: cursor,
      page_size: 100,
      sorts: sorts,
    });

    allPages.push(...response.results);
    cursor = response.has_more ? response.next_cursor : undefined;
    pageCount++;

    if (pageCount > 10) {
      console.warn('⚠️  Pagination safety limit reached (1000 rows). Stopping.');
      break;
    }
  } while (cursor);

  return allPages;
}

/**
 * Extracts and transforms DB5 (Monitoreo en Vivo) data.
 * Expected: 1 row with monthly stats and today's indicators.
 */
async function fetchDB5() {
  console.log('📡 Fetching DB5: Dashboard de Actualidad y Monitoreo en Vivo...');

  const pages = await queryDatabase(DB5_ID);

  if (pages.length === 0) {
    console.error('❌ DB5 returned 0 rows. Check that the integration has access.');
    return null;
  }

  const page = pages[0];
  const props = page.properties;

  return {
    panel: extractProperty(props['Panel']),
    cortesDelMes: extractProperty(props['Cortes del Mes (auto)']),
    minutosTotalesMes: extractProperty(props['Minutos Totales Mes (auto)']),
    totalHorasPlanta: extractProperty(props['Total Horas Planta (Mes)']),
    frecuenciaSemanal: extractProperty(props['Frecuencia Semanal']),
    estresEnergetico: extractProperty(props['🌡️ Estrés Energético (Mes)']),
    probabilidadDeHoy: extractProperty(props['🔴 Probabilidad de Hoy']),
    progresoAnual: extractProperty(props['📅 Progreso Anual']),
    patronDeHoy: extractProperty(props['Patrón de Hoy']),
    medidorTiempo: extractProperty(props['⏱️ Medidor de Tiempo al Corte']),
    estadoOperativo: extractProperty(props['Estado Operativo']),
  };
}

/**
 * Extracts and transforms DB2 (Resumen Semanal) data.
 * Expected: 7 rows (Lunes to Domingo), filtered to exclude TOTALES/PROMEDIOS.
 */
async function fetchDB2() {
  console.log('📡 Fetching DB2: Resumen Semanal de Cortes...');

  const pages = await queryDatabase(DB2_ID);

  const days = pages
    .map(page => {
      const props = page.properties;
      const dia = extractProperty(props['Día']);

      // Filter out aggregate rows (TOTALES, PROMEDIOS)
      if (!dia || dia.includes('TOTALES') || dia.includes('PROMEDIOS')) {
        return null;
      }

      return {
        dia,
        diaNumero: extractProperty(props['Día (número)']),
        horaCorteFmt: extractProperty(props['Hora Prom. Corte']),
        horaRetornoFmt: extractProperty(props['Hora Prom. Retorno']),
        ventanaRiesgo: extractProperty(props['Ventana de Riesgo']),
        duracionProm: extractProperty(props['Duración Prom.']),
        probabilidad: extractProperty(props['Probabilidad']),
        pctTotal: extractProperty(props['% del Total']),
        conteo: extractProperty(props['Conteo (auto)']),
        semanasObservadas: extractProperty(props['Semanas Observadas']),
        // Raw numeric values for client-side countdown calculations
        horaInicioMin: extractProperty(props['Prom. Hora Inicio (auto)']),
        horaFinMin: extractProperty(props['Prom. Hora Fin (auto)']),
        duracionMin: extractProperty(props['Prom. Duración (auto)']),
      };
    })
    .filter(Boolean)
    .sort((a, b) => (a.diaNumero || 0) - (b.diaNumero || 0));

  return days;
}

/**
 * Builds a lookup map from weekly data for quick client-side access.
 * Keys are JS day numbers (0=Sunday, 1=Monday, ..., 6=Saturday).
 */
function buildPatronesLookup(weeklyData) {
  // Map Notion day numbers (1=Lunes...7=Domingo) to JS day numbers (0=Domingo, 1=Lunes...6=Sábado)
  const notionToJsDay = { 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 0 };
  const lookup = {};

  for (const day of weeklyData) {
    const jsDay = notionToJsDay[day.diaNumero];
    if (jsDay !== undefined) {
      lookup[jsDay] = {
        horaInicioMin: day.horaInicioMin ? Math.round(day.horaInicioMin) : 0,
        horaFinMin: day.horaFinMin ? Math.round(day.horaFinMin) : 0,
        duracionMin: day.duracionMin ? Math.round(day.duracionMin) : 0,
      };
    }
  }

  // Ensure Sunday exists with zeros if not in data
  if (!lookup[0]) {
    lookup[0] = { horaInicioMin: 0, horaFinMin: 0, duracionMin: 0 };
  }

  return lookup;
}

// --- Main ---

async function main() {
  console.log('🚀 Sanesca Dashboard — Notion Data Extraction');
  console.log(`   Build timestamp: ${new Date().toISOString()}`);
  console.log('');

  try {
    // Fetch both databases in parallel
    const [monthly, weekly] = await Promise.all([fetchDB5(), fetchDB2()]);

    if (!monthly) {
      throw new Error('Failed to fetch DB5 (Monitoreo en Vivo)');
    }
    if (!weekly || weekly.length === 0) {
      throw new Error('Failed to fetch DB2 (Resumen Semanal)');
    }

    const patronesPorDia = buildPatronesLookup(weekly);

    const dashboard = {
      buildTimestamp: new Date().toISOString(),
      monthly,
      weekly,
      patronesPorDia,
    };

    // Ensure output directory exists
    if (!fs.existsSync(OUTPUT_DIR)) {
      fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    }

    // Write JSON
    fs.writeFileSync(OUTPUT_FILE, JSON.stringify(dashboard, null, 2), 'utf-8');

    console.log(`✅ Dashboard data written to ${OUTPUT_FILE}`);
    console.log(`   Monthly stats: ${monthly.cortesDelMes ?? '?'} cortes, ${monthly.totalHorasPlanta ?? '?'}`);
    console.log(`   Weekly data: ${weekly.length} days`);
    console.log(`   Patrones lookup: ${Object.keys(patronesPorDia).length} entries`);

  } catch (error) {
    console.error('❌ Extraction failed:', error.message);

    // If we have a previous successful build, keep it
    if (fs.existsSync(OUTPUT_FILE)) {
      console.log('⚠️  Keeping previous dashboard.json as fallback.');
    }

    process.exit(1);
  }
}

main();
