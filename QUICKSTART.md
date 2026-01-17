# 🚀 Guía de Inicio Rápido - PMA-Agent

## Instalación en 3 Pasos

### 1️⃣ Instalar Backend

```bash
cd backend

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2️⃣ Instalar Frontend

```bash
cd frontend

# Instalar dependencias
npm install
```

### 3️⃣ Ejecutar Aplicación

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python main.py
```

Backend disponible en: `http://localhost:8000`

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Frontend disponible en: `http://localhost:5173`

## 🎯 Uso Básico

1. Abrir navegador en `http://localhost:5173`

2. **Paso 1: Conectar**
   - Ingresar datos de conexión PostgreSQL
   - Hacer clic en "Probar Conexión"
   - Verificar mensaje de éxito

3. **Paso 2: Configurar Análisis**
   - Seleccionar agentes (o dejar todos)
   - Ingresar esquemas: `public` (o múltiples separados por coma)
   - Hacer clic en "Ejecutar Auditoría"

4. **Paso 3: Ver Resultados**
   - Observar logs en tiempo real
   - Navegar por pestañas: Resumen, Hallazgos, Recomendaciones
   - Descargar reportes en MD, HTML o JSON

## 🔧 Configuración de Base de Datos de Prueba

Si no tienes una base de datos PostgreSQL, puedes usar Docker:

```bash
# Iniciar PostgreSQL con Docker
docker run -d \
  --name postgres-test \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=testdb \
  -p 5432:5432 \
  postgres:15

# Cargar datos de prueba
docker exec -i postgres-test psql -U postgres -d testdb < backend/postgres_agent/infra/init-db.sql
```

Luego conectar con:
- **Host:** localhost
- **Puerto:** 5432
- **Base de datos:** testdb
- **Usuario:** postgres
- **Contraseña:** postgres

## 📊 Endpoints API (opcional)

Si prefieres usar la API directamente:

```bash
# Probar conexión
curl -X POST http://localhost:8000/connect \
  -H "Content-Type: application/json" \
  -d '{
    "connection": {
      "host": "localhost",
      "port": 5432,
      "database": "testdb",
      "user": "postgres",
      "password": "postgres"
    }
  }'

# Iniciar análisis
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "connection": {
      "host": "localhost",
      "port": 5432,
      "database": "testdb",
      "user": "postgres",
      "password": "postgres"
    },
    "schemas": ["public"]
  }'

# Ver estado (reemplazar {audit_id})
curl http://localhost:8000/status/{audit_id}

# Descargar reporte
curl http://localhost:8000/download/{audit_id}/markdown -o reporte.md
```

## ❓ Problemas Comunes

**Backend no inicia:**
```bash
# Verificar que el puerto 8000 esté libre
lsof -i :8000

# Reinstalar dependencias
pip install --upgrade -r requirements.txt
```

**Frontend no conecta:**
```bash
# Verificar que el backend esté ejecutándose
curl http://localhost:8000

# Verificar configuración de proxy en vite.config.js
```

**Error de conexión PostgreSQL:**
```bash
# Verificar que PostgreSQL esté ejecutándose
pg_isready

# Verificar credenciales y permisos
psql -h localhost -U postgres -d testdb
```

## 🎨 Capturas de Interfaz

La aplicación tiene:
- ✨ Modo oscuro profesional
- 📊 Consola de progreso en tiempo real
- 📈 Visualización de hallazgos por severidad
- 💾 Descarga de reportes en múltiples formatos
- 🎯 Interfaz paso a paso intuitiva

## 📚 Documentación Completa

Ver `README.md` para documentación detallada.

---

¿Listo? ¡Ejecuta `./start.sh` y comienza el análisis! 🚀
