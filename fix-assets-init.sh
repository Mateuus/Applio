#!/bin/bash
# ============================================
# Script para criar arquivos __init__.py
# necessários para o módulo assets funcionar
# ============================================

set -e

echo "🔧 Criando arquivos __init__.py para assets..."

# Criar __init__.py em assets/
if [ ! -f "assets/__init__.py" ]; then
    echo "# assets package" > assets/__init__.py
    echo "✅ Criado: assets/__init__.py"
else
    echo "ℹ️  assets/__init__.py já existe"
fi

# Criar __init__.py em assets/i18n/
if [ ! -f "assets/i18n/__init__.py" ]; then
    mkdir -p assets/i18n
    echo "# i18n package" > assets/i18n/__init__.py
    echo "✅ Criado: assets/i18n/__init__.py"
else
    echo "ℹ️  assets/i18n/__init__.py já existe"
fi

# Criar __init__.py em assets/themes/
if [ ! -f "assets/themes/__init__.py" ]; then
    mkdir -p assets/themes
    echo "# themes package" > assets/themes/__init__.py
    echo "✅ Criado: assets/themes/__init__.py"
else
    echo "ℹ️  assets/themes/__init__.py já existe"
fi

echo ""
echo "✅ Todos os arquivos __init__.py foram criados!"
echo ""
echo "📝 Próximos passos:"
echo "   1. Reinicie os containers:"
echo "      docker-compose -f docker-compose.prod.yml restart"
echo "   2. Ou recrie os containers:"
echo "      docker-compose -f docker-compose.prod.yml up -d --force-recreate"

