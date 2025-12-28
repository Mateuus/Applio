#!/bin/bash
# ============================================
# Script para criar arquivos __init__.py
# necessários para o módulo assets funcionar
# ============================================

set -e

echo "🔧 Verificando e criando arquivos __init__.py para assets..."
echo ""

# Verificar se o diretório assets existe
if [ ! -d "assets" ]; then
    echo "❌ ERRO: Diretório 'assets' não encontrado!"
    echo "   Execute 'git pull' para baixar todos os arquivos do repositório."
    exit 1
fi

# Verificar se arquivos críticos existem
if [ ! -f "assets/i18n/i18n.py" ]; then
    echo "⚠️  AVISO: assets/i18n/i18n.py não encontrado!"
    echo "   O diretório assets pode estar incompleto."
    echo "   Execute 'git pull' para garantir que todos os arquivos estão presentes."
    echo ""
fi

# Criar __init__.py em assets/
if [ ! -f "assets/__init__.py" ]; then
    echo "# assets package" > assets/__init__.py
    echo "✅ Criado: assets/__init__.py"
else
    echo "ℹ️  assets/__init__.py já existe"
fi

# Criar __init__.py em assets/i18n/
if [ ! -d "assets/i18n" ]; then
    echo "⚠️  AVISO: Diretório assets/i18n não existe!"
    echo "   Execute 'git pull' para baixar todos os arquivos."
    exit 1
fi

if [ ! -f "assets/i18n/__init__.py" ]; then
    echo "# i18n package" > assets/i18n/__init__.py
    echo "✅ Criado: assets/i18n/__init__.py"
else
    echo "ℹ️  assets/i18n/__init__.py já existe"
fi

# Verificar se i18n.py existe
if [ ! -f "assets/i18n/i18n.py" ]; then
    echo "❌ ERRO: assets/i18n/i18n.py não encontrado!"
    echo "   Execute 'git pull' para baixar todos os arquivos do repositório."
    exit 1
fi

# Criar __init__.py em assets/themes/
if [ ! -d "assets/themes" ]; then
    mkdir -p assets/themes
    echo "ℹ️  Criado diretório: assets/themes"
fi

if [ ! -f "assets/themes/__init__.py" ]; then
    echo "# themes package" > assets/themes/__init__.py
    echo "✅ Criado: assets/themes/__init__.py"
else
    echo "ℹ️  assets/themes/__init__.py já existe"
fi

echo ""
echo "✅ Verificação concluída!"
echo ""
echo "📝 IMPORTANTE: Certifique-se de que o diretório 'assets' está completo."
echo "   Se faltar arquivos, execute: git pull"
echo ""
echo "📝 Próximos passos:"
echo "   1. Reinicie os containers:"
echo "      docker-compose -f docker-compose.prod.yml restart"
echo "   2. Ou recrie os containers:"
echo "      docker-compose -f docker-compose.prod.yml up -d --force-recreate"

