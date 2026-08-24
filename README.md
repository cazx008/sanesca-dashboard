# ⚡ Sanesca Dashboard — Monitoreo de Cortes Eléctricos

Dashboard web estático que visualiza patrones de interrupciones eléctricas para Sanesca Exhibidores. Los datos provienen de bases de datos de Notion y se actualizan automáticamente cada día.

## 🖥️ Vista General

- **Barra de estado en vivo**: Countdown al próximo corte estimado, probabilidad del día, patrón esperado
- **Vista semanal**: 7 tarjetas (Lunes a Domingo) con hora promedio de corte, retorno, duración y probabilidad
- **Estadísticas mensuales**: Cortes del mes, horas de planta, frecuencia semanal, estrés energético
- **Tema claro/oscuro**: Selector manual con persistencia en localStorage

## 🏗️ Arquitectura

```
Notion (2 DBs) → GitHub Actions (cron diario) → JSON estático → GitHub Pages
```

| Componente | Tecnología |
|:---|:---|
| Fuente de datos | Notion API (`@notionhq/client`) |
| Frontend | HTML5 + Tailwind CSS (CDN) + Alpine.js (CDN) |
| Build pipeline | GitHub Actions (cron 00:01 UTC-4) |
| Hosting | GitHub Pages (CDN global, gratis) |

## 📋 Setup

### 1. Crear Integración en Notion

1. Ir a [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Crear nueva integración con permisos de **solo lectura**
3. Copiar el token (`ntn_...`)
4. En Notion, compartir las dos bases de datos con la integración:
   - 🎛️ Dashboard de Actualidad y Monitoreo en Vivo
   - Resumen Semanal de Cortes

### 2. Configurar GitHub Secrets

En el repositorio de GitHub → Settings → Secrets and Variables → Actions:

| Secret | Valor |
|:---|:---|
| `NOTION_TOKEN` | `ntn_...` (token de la integración) |
| `NOTION_DB5_ID` | `3c386805-4e27-81ff-add6-c35fb3a40c03` |
| `NOTION_DB2_ID` | `3aa86805-4e27-8133-8d94-de72d7fc0d23` |

### 3. Activar GitHub Pages

1. Settings → Pages → Source: **GitHub Actions**
2. El workflow se ejecuta automáticamente cada día a las 00:01

### 4. Desarrollo Local

```bash
# Clonar repositorio
git clone https://github.com/your-username/sanesca-dashboard.git
cd sanesca-dashboard

# Instalar dependencias
npm install

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tu NOTION_TOKEN

# Ejecutar extracción (genera data/dashboard.json)
# En PowerShell:
$env:NOTION_TOKEN="ntn_your_token"; node scripts/fetch-notion.js

# Abrir dashboard en navegador
# Usar un servidor local (por CORS con fetch):
npx serve .
```

## 📁 Estructura

```
sanesca-dashboard/
├── .github/workflows/deploy.yml   # CI/CD: cron diario + deploy
├── assets/logo-sanesca.png        # Logo de Sanesca
├── data/dashboard.json            # Datos generados (gitignored)
├── scripts/fetch-notion.js        # Script de extracción de Notion
├── index.html                     # Dashboard principal
├── package.json
└── .env.example                   # Template de variables de entorno
```

## 🔄 Actualización Manual

Si necesitas forzar una actualización fuera del cron diario:
1. Ir a GitHub → Actions → "Deploy Sanesca Dashboard"
2. Click en "Run workflow" → "Run workflow"

## 📊 Bases de Datos de Notion

| DB | Descripción | Filas |
|:---|:---|:---|
| DB5 | Monitoreo en Vivo (KPIs mensuales) | 1 |
| DB2 | Resumen Semanal (patrones por día) | 7 |

---

*Sanesca Exhibidores · Powered by Notion API · Hosted on GitHub Pages*
