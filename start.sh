#!/bin/bash

# Script de inicio rápido para PMA-Agent

echo "🚀 Iniciando PMA-Agent..."
echo ""

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no encontrado. Por favor instale Python 3.11+"
    exit 1
fi

# Verificar Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js no encontrado. Por favor instale Node.js 18+"
    exit 1
fi

echo -e "${BLUE}📦 Instalando dependencias del backend...${NC}"
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
cd ..

echo -e "${BLUE}📦 Instalando dependencias del frontend...${NC}"
cd frontend
if [ ! -d "node_modules" ]; then
    npm install --silent
fi
cd ..

echo ""
echo -e "${GREEN}✅ Instalación completada${NC}"
echo ""
echo "Para iniciar la aplicación:"
echo ""
echo "1. Backend (en una terminal):"
echo "   cd backend && source venv/bin/activate && python main.py"
echo ""
echo "2. Frontend (en otra terminal):"
echo "   cd frontend && npm run dev"
echo ""
echo "Luego abra: http://localhost:5173"
