#!/bin/sh
printf "\033]0;Applio\007"
. .venv/bin/activate

export PYTORCH_ENABLE_MPS_FALLBACK=1
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0

# Função para limpar processos ao sair
cleanup() {
    echo ""
    echo "Encerrando API..."
    if [ ! -z "$API_PID" ]; then
        kill $API_PID 2>/dev/null || true
        wait $API_PID 2>/dev/null || true
    fi
    exit 0
}

# Capturar Ctrl+C e chamar cleanup
trap cleanup INT TERM

clear

# Verificar se a API deve ser iniciada
START_API="${START_API:-true}"

if [ "$START_API" = "true" ] && [ -f "api/app.py" ]; then
    echo "🚀 Iniciando Applio TTS Inference API..."
    
    # Configurações da API
    API_HOST="${API_HOST:-0.0.0.0}"
    API_PORT="${API_PORT:-8000}"
    
    # Iniciar API em background (manter no diretório raiz para caminhos relativos funcionarem)
    python -m uvicorn api.app:app --host "$API_HOST" --port "$API_PORT" > api.log 2>&1 &
    API_PID=$!
    
    echo "✅ API iniciada em http://${API_HOST}:${API_PORT} (PID: $API_PID)"
    echo "📚 Swagger UI: http://${API_HOST}:${API_PORT}/docs"
    echo "📖 ReDoc: http://${API_HOST}:${API_PORT}/redoc"
    echo "📝 Logs da API: api.log"
    echo ""
    sleep 2
else
    echo "⚠️ API não será iniciada (START_API=false ou api/app.py não encontrado)"
    echo ""
fi

# Iniciar Applio em foreground
echo "🎤 Iniciando Applio..."
echo ""
python app.py --open
