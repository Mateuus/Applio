#!/bin/bash
# ============================================
# Script para gerar hash de senha para Traefik BasicAuth
# ============================================

echo "🔐 Gerador de Hash de Senha para Traefik BasicAuth"
echo "=================================================="
echo ""

# Verificar se htpasswd está instalado
if ! command -v htpasswd &> /dev/null; then
    echo "❌ htpasswd não está instalado."
    echo ""
    echo "📦 Instalar:"
    echo "   Ubuntu/Debian: sudo apt-get install apache2-utils"
    echo "   CentOS/RHEL: sudo yum install httpd-tools"
    echo "   macOS: brew install httpd"
    echo ""
    exit 1
fi

# Solicitar usuário e senha
read -p "👤 Usuário: " username
read -sp "🔒 Senha: " password
echo ""

# Gerar hash
hash=$(htpasswd -nb "$username" "$password")

# Escapar $ para docker-compose
escaped_hash=$(echo "$hash" | sed 's/\$/\$\$/g')

echo ""
echo "✅ Hash gerado:"
echo "=================================================="
echo "$escaped_hash"
echo "=================================================="
echo ""
echo "📝 Adicione esta linha no docker-compose.prod.yml:"
echo ""
echo "   - \"traefik.http.middlewares.applio-gradio-auth.basicauth.users=$escaped_hash\""
echo ""
echo "💡 Para múltiplos usuários, separe com vírgula:"
echo "   - \"traefik.http.middlewares.applio-gradio-auth.basicauth.users=user1:\$\$hash1,user2:\$\$hash2\""
echo ""

