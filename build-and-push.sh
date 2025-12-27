#!/bin/bash
# ============================================
# Script para Build e Push da Imagem Docker
# Applio API
# ============================================

set -e  # Parar em caso de erro

# Configurações
IMAGE_NAME="mateuus27/applio-api"
VERSION="${1:-latest}"  # Versão como argumento ou "latest" por padrão
DOCKERFILE="Dockerfile"

echo "🐳 Build e Push - Applio API"
echo "================================"
echo ""

# Verificar se está logado no Docker Hub
if ! docker info | grep -q "Username"; then
    echo "⚠️  Você não está logado no Docker Hub"
    echo "📝 Execute: docker login"
    echo ""
    read -p "Deseja fazer login agora? (s/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        docker login
    else
        echo "❌ Login cancelado. Saindo..."
        exit 1
    fi
fi

echo "✅ Logado no Docker Hub"
echo ""

# Build da imagem
echo "🔨 Construindo imagem: ${IMAGE_NAME}:${VERSION}"
echo ""

docker build \
    -t "${IMAGE_NAME}:${VERSION}" \
    -t "${IMAGE_NAME}:latest" \
    -f "${DOCKERFILE}" \
    .

echo ""
echo "✅ Build concluído!"
echo ""

# Mostrar imagens criadas
echo "📦 Imagens criadas:"
docker images | grep "${IMAGE_NAME}" | head -2
echo ""

# Confirmar push
read -p "🚀 Deseja fazer push para o Docker Hub? (s/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "⏭️  Push cancelado."
    echo "💡 Para fazer push manualmente:"
    echo "   docker push ${IMAGE_NAME}:${VERSION}"
    echo "   docker push ${IMAGE_NAME}:latest"
    exit 0
fi

# Push da imagem
echo "📤 Fazendo push da imagem..."
echo ""

# Push da versão específica
if [ "$VERSION" != "latest" ]; then
    echo "📤 Push: ${IMAGE_NAME}:${VERSION}"
    docker push "${IMAGE_NAME}:${VERSION}"
    echo ""
fi

# Push da latest
echo "📤 Push: ${IMAGE_NAME}:latest"
docker push "${IMAGE_NAME}:latest"

echo ""
echo "✅ Push concluído!"
echo ""
echo "🎉 Imagem disponível em: https://hub.docker.com/r/${IMAGE_NAME}"
echo ""

