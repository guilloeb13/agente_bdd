# 🔍 PMA-Agent - Analizador Multi-Agente de PostgreSQL

Sistema web completo para análisis exhaustivo de bases de datos PostgreSQL mediante agentes especializados de IA.

## 🌟 Características

### Backend (FastAPI)
- ✅ API REST completa con FastAPI
- ✅ WebSockets para logs en tiempo real
- ✅ 11 agentes especializados de análisis
- ✅ Generación de reportes (Markdown, HTML, JSON)
- ✅ Solo lectura - sin modificaciones a la BD

### Frontend (React + Vite)
- ✅ Interfaz moderna en modo oscuro
- ✅ Formulario de conexión intuitivo
- ✅ Selector de agentes con checkboxes
- ✅ Consola de progreso en tiempo real
- ✅ Visor de reportes integrado
- ✅ Descarga de reportes en múltiples formatos

## 📋 Agentes Especializados

1. **Agente de Seguridad** - Roles, permisos, OWASP/CIS
2. **Agente de Esquema** - Estructuras, tipos, convenciones
3. **Agente de Integridad** - FKs faltantes, relaciones
4. **Agente de Huérfanos** - Datos huérfanos, jerarquías
5. **Agente de Normalización** - 1NF, 2NF, 3NF, BCNF
6. **Agente de Rendimiento** - Scans, bloat, cache
7. **Agente de Índices** - B-Tree, GIN, GiST
8. **Agente de Calidad de Datos** - Duplicados, NULLs
9. **Agente de Anomalías** - Outliers, temporal
10. **Agente de DDL** - Reconstrucción DDL
11. **Agente de Recomendaciones** - Plan de acción

## 🚀 Instalación y Ejecución

### Requisitos Previos

- Python 3.11+
- Node.js 18+
- PostgreSQL 12+

### Backend

```bash
cd backend

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
python main.py
# O con uvicorn:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

El backend estará disponible en `http://localhost:8000`

### Frontend

```bash
cd frontend

# Instalar dependencias
npm install

# Ejecutar en modo desarrollo
npm run dev

# Construir para producción
npm run build
```

El frontend estará disponible en `http://localhost:5173`

## 📖 Uso

1. **Conectar a la Base de Datos**
   - Ingrese los datos de conexión (host, puerto, base de datos, usuario, contraseña)
   - Presione "Probar Conexión"
   - Verifique que la conexión sea exitosa

2. **Configurar Análisis**
   - Seleccione los agentes que desea ejecutar (o deje vacío para todos)
   - Ingrese los esquemas a analizar (separados por coma)
   - Presione "Ejecutar Auditoría"

3. **Ver Progreso**
   - Observe los logs en tiempo real en la consola
   - El progreso se actualiza automáticamente vía WebSocket

4. **Revisar Resultados**
   - Navegue por las pestañas: Resumen, Hallazgos, Recomendaciones
   - Descargue los reportes en el formato deseado (MD, HTML, JSON)

## 📡 API Endpoints

### `POST /connect`
Probar conexión a la base de datos

```json
{
  "connection": {
    "host": "localhost",
    "port": 5432,
    "database": "mydb",
    "user": "postgres",
    "password": "secret"
  }
}
```

### `POST /analyze`
Iniciar análisis

```json
{
  "connection": { ... },
  "schemas": ["public", "app"],
  "agents": ["security", "performance"]
}
```

### `GET /status/{audit_id}`
Obtener estado del análisis

### `GET /results/{audit_id}`
Obtener resultados completos

### `GET /download/{audit_id}/{format}`
Descargar reporte (format: markdown, html, json)

### `WebSocket /ws/{audit_id}`
Logs en tiempo real

## 🏗️ Estructura del Proyecto

```
.
├── backend/
│   ├── main.py                 # Servidor FastAPI
│   ├── requirements.txt        # Dependencias Python
│   └── postgres_agent/         # Sistema de agentes
│       ├── engine/             # Motor de conexión
│       ├── manager/            # Orquestador
│       ├── agents/             # 11 agentes especializados
│       └── reports/            # Generadores de reportes
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Componente principal
│   │   ├── components/        # Componentes React
│   │   │   ├── ConnectionForm.jsx
│   │   │   ├── AgentSelector.jsx
│   │   │   ├── ProgressConsole.jsx
│   │   │   └── ReportViewer.jsx
│   │   └── index.css          # Estilos Tailwind
│   ├── package.json
│   └── vite.config.js
│
└── outputs/                    # Reportes generados
```

## 🔒 Seguridad

- ✅ Solo consultas de lectura (SELECT, SHOW)
- ✅ Validación de queries
- ✅ Sin modificaciones a la base de datos
- ✅ Auditoría pasiva
- ✅ Timeout de conexiones

## 🎨 Tecnologías

**Backend:**
- FastAPI
- asyncpg / psycopg2
- Pydantic
- WebSockets

**Frontend:**
- React 18
- Vite
- TailwindCSS
- Axios
- react-markdown
- Lucide Icons

## 📝 Notas

- El idioma de la interfaz es **español**
- El código usa nombres en **inglés**
- Los reportes se generan en **español**
- Compatible con PostgreSQL 12+

## 🐛 Troubleshooting

**Error de CORS:**
```bash
# Asegúrese de que el backend esté ejecutándose en el puerto 8000
# El frontend está configurado para usar proxy hacia localhost:8000
```

**Error de conexión a PostgreSQL:**
```bash
# Verifique que PostgreSQL esté ejecutándose
# Verifique las credenciales
# Verifique que el usuario tenga permisos de lectura
```

**WebSocket no funciona:**
```bash
# El sistema tiene fallback a polling automático
# Verifique que no haya firewall bloqueando el puerto 8000
```

## 📄 Licencia

MIT

## 👥 Contribuir

Las contribuciones son bienvenidas. Por favor:
1. Fork el proyecto
2. Cree una rama para su feature
3. Commit sus cambios
4. Push a la rama
5. Abra un Pull Request

---

Hecho con ❤️ para análisis de PostgreSQL
