#!/bin/bash
# Script para iniciar a API do Applio

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Iniciando Applio TTS Inference API...${NC}"

# Obter diretório do script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
API_DIR="$SCRIPT_DIR"
APP_DIR="$(dirname "$API_DIR")"

# Mudar para diretório do Applio
cd "$APP_DIR" || exit 1

# Verificar se Python está disponível
if ! command -v python &> /dev/null; then
    echo -e "${YELLOW}⚠️ Python não encontrado. Tentando python3...${NC}"
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Verificar se virtual environment existe
if [ -d ".venv" ]; then
    echo -e "${GREEN}✅ Virtual environment encontrado. Ativando...${NC}"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo -e "${GREEN}✅ Virtual environment encontrado. Ativando...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}⚠️ Virtual environment não encontrado. Usando Python global.${NC}"
fi

# Verificar se FastAPI está instalado
if ! $PYTHON_CMD -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}⚠️ FastAPI não encontrado. Instalando dependências...${NC}"
    pip install -r "$API_DIR/requirements.txt"
fi

# Configurações padrão
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-false}"

echo -e "${GREEN}📡 Iniciando servidor em http://${HOST}:${PORT}${NC}"
echo -e "${GREEN}📚 Documentação Swagger: http://${HOST}:${PORT}/docs${NC}"
echo -e "${GREEN}📖 Documentação ReDoc: http://${HOST}:${PORT}/redoc${NC}"
echo ""

# Iniciar servidor
cd "$API_DIR"
$PYTHON_CMD -m uvicorn app:app --host "$HOST" --port "$PORT" ${RELOAD:+--reload}

