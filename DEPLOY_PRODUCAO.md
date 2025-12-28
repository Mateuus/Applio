# 🚀 Deploy Applio - Produção com Traefik

Guia completo para fazer deploy do Applio (API + Gradio) no servidor de produção com Traefik.

## 📋 Pré-requisitos

- ✅ Servidor com Docker e Docker Compose instalados
- ✅ Traefik rodando e configurado
- ✅ Network `web` criada e Traefik conectado
- ✅ **CPU apenas** - GPU desabilitada em produção (configuração otimizada para CPU)
- ✅ Domínios configurados:
  - `voice.eopix.me` → API FastAPI
  - `voice-ui.eopix.me` → Interface Gradio

## 🔧 Passo a Passo

### 1. Preparar o Ambiente no Servidor

```bash
# Acessar o servidor
ssh usuario@seu-servidor.com

# Criar diretório do Applio (ajuste o caminho conforme necessário)
mkdir -p /opt/apps/applio
cd /opt/apps/applio

# Clonar o repositório (ou fazer pull se já existir)
git clone https://github.com/Mateuus/Applio.git .
# OU se já existe:
# git pull origin main
```

### 2. Verificar/Criar a Network 'web'

```bash
# Verificar se a network 'web' existe
docker network ls | grep web

# Se não existir, criar:
docker network create web

# Verificar se Traefik está na network 'web'
docker network inspect web | grep traefik

# Se não estiver, conectar o Traefik:
docker network connect web traefik
```

### 3. Configurar o .env

```bash
# Copiar o exemplo
cp .env.example .env

# Editar o .env
nano .env
```

**Variáveis importantes a configurar:**

```bash
# API
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=SUA_CHAVE_SECRETA_AQUI  # Gere: openssl rand -base64 32

# Whisper
WHISPER_MODEL_SIZE=turbo
WHISPER_PRELOAD=true

# Pyannote (opcional, para diarização)
PYANNOTE_TOKEN=seu_token_aqui
PYANNOTE_PRELOAD=false
PYANNOTE_MODEL=pyannote/speaker-diarization-3.1

# GPU (desabilitado em produção - CPU apenas)
# CUDA_VISIBLE_DEVICES=0

# Diretórios
OUTPUT_DIR=/app/assets/audios
UPLOAD_DIR=/app/assets/uploads

# Docker
DISABLE_DISCORD_PRESENCE=1
DOCKER_CONTAINER=1
PYTHONUNBUFFERED=1
```

### 4. Configurar Autenticação Gradio (Opcional)

Se quiser alterar a senha do Gradio:

```bash
# Gerar hash da senha
./generate-password-hash.sh

# Copiar o hash gerado e atualizar no docker-compose.prod.yml
# Linha 60: traefik.http.middlewares.applio-gradio-auth.basicauth.users
```

### 5. Fazer Pull da Imagem Docker

```bash
# Fazer pull da imagem mais recente do Docker Hub
docker-compose -f docker-compose.prod.yml pull
```

### 6. Remover Portas Expostas (Produção)

**IMPORTANTE:** Em produção, remova a seção `ports` do `applio-gradio` no `docker-compose.prod.yml`:

```yaml
# Comentar ou remover estas linhas (linhas 41-42):
# ports:
#   - "6969:6969"
```

Ou edite o arquivo:

```bash
nano docker-compose.prod.yml
# Comente as linhas 41-42 (ports do applio-gradio)
```

### 7. Iniciar os Serviços

```bash
# Parar containers antigos (se existirem)
docker-compose -f docker-compose.prod.yml down

# Iniciar ambos os serviços (API + Gradio)
docker-compose -f docker-compose.prod.yml up -d

# OU iniciar apenas um serviço:
# docker-compose -f docker-compose.prod.yml up -d applio-api
# docker-compose -f docker-compose.prod.yml up -d applio-gradio
```

### 8. Verificar Status

```bash
# Ver status dos containers
docker-compose -f docker-compose.prod.yml ps

# Ver logs em tempo real
docker-compose -f docker-compose.prod.yml logs -f

# Ver logs de um serviço específico
docker-compose -f docker-compose.prod.yml logs -f applio-api
docker-compose -f docker-compose.prod.yml logs -f applio-gradio
```

### 9. Verificar Traefik

```bash
# Reiniciar Traefik para detectar os novos containers
docker restart traefik

# Aguardar alguns segundos
sleep 20

# Ver logs do Traefik procurando por "applio"
docker logs traefik --tail=50 | grep -i applio

# Verificar se os serviços foram detectados
# Acesse o dashboard do Traefik: http://seu-servidor:8080
```

### 10. Testar os Serviços

```bash
# Testar API via HTTPS
curl https://voice.eopix.me/health

# Deve retornar algo como:
# {"status":"ok"}

# Testar API endpoint específico
curl -X GET https://voice.eopix.me/api/v1/models

# Testar Gradio (deve pedir autenticação)
curl -I https://voice-ui.eopix.me/
# Deve retornar 401 Unauthorized (sem credenciais) ou 200 (com credenciais)
```

## 🔄 Comandos Úteis

### Atualizar Serviços

```bash
# Fazer pull da nova imagem
docker-compose -f docker-compose.prod.yml pull

# Recriar containers com nova imagem
docker-compose -f docker-compose.prod.yml up -d --force-recreate

# OU apenas um serviço:
docker-compose -f docker-compose.prod.yml up -d --force-recreate applio-api
```

### Escalar API (Múltiplas Instâncias)

```bash
# Escalar para 2 instâncias da API
docker-compose -f docker-compose.prod.yml up -d --scale applio-api=2

# Verificar instâncias
docker-compose -f docker-compose.prod.yml ps
```

### Parar Serviços

```bash
# Parar todos os serviços
docker-compose -f docker-compose.prod.yml down

# Parar apenas um serviço
docker-compose -f docker-compose.prod.yml stop applio-api
```

### Reiniciar Serviços

```bash
# Reiniciar todos
docker-compose -f docker-compose.prod.yml restart

# Reiniciar apenas um
docker-compose -f docker-compose.prod.yml restart applio-api
```

### Ver Logs

```bash
# Logs de todos os serviços
docker-compose -f docker-compose.prod.yml logs -f

# Logs das últimas 100 linhas
docker-compose -f docker-compose.prod.yml logs --tail=100

# Logs de um serviço específico
docker-compose -f docker-compose.prod.yml logs -f applio-api
```

## ✅ Checklist de Verificação

Antes de considerar o deploy completo, verifique:

- [ ] Network `web` existe: `docker network ls | grep web`
- [ ] Traefik está na network `web`: `docker network inspect web | grep traefik`
- [ ] Containers estão rodando: `docker-compose -f docker-compose.prod.yml ps`
- [ ] Containers estão na network `web`: `docker network inspect web | grep applio`
- [ ] API responde: `curl https://voice.eopix.me/health`
- [ ] Gradio acessível: `curl -I https://voice-ui.eopix.me/`
- [ ] Traefik detectou os serviços: Dashboard Traefik mostra `applio@docker` e `applio-gradio@docker`
- [ ] Certificados SSL válidos: Verificado no browser
- [ ] Health check passando: `docker ps` mostra containers como "healthy"
- [ ] CPU funcionando: Verificar logs para confirmar que está rodando em CPU

## 🐛 Troubleshooting

### Containers não iniciam

```bash
# Ver logs detalhados
docker-compose -f docker-compose.prod.yml logs

# Verificar se a imagem existe
docker images | grep applio-api

# Verificar se há conflito de portas
docker ps | grep -E "6969|8000"
```

### Traefik não roteia

```bash
# Verificar se Traefik está na network 'web'
docker network inspect web | grep traefik

# Se não estiver, conectar:
docker network connect web traefik

# Reiniciar Traefik
docker restart traefik

# Verificar logs do Traefik
docker logs traefik --tail=100
```

### Erro relacionado a GPU (se aparecer)

**Nota:** Em produção, a GPU está desabilitada e os serviços rodam apenas com CPU.

Se você ver erros relacionados a GPU (`could not select device driver "nvidia"`), isso significa que a configuração de GPU ainda está ativa. Verifique o `docker-compose.prod.yml` e certifique-se de que a seção `deploy.resources` com `nvidia` está comentada ou removida.

```bash
# Verificar se há configuração de GPU no docker-compose
grep -A 5 "driver: nvidia" docker-compose.prod.yml

# Se aparecer, remova ou comente essas linhas
```

### Certificado SSL não funciona

```bash
# Verificar se o domínio aponta para o servidor
dig voice.eopix.me +short

# Verificar se a porta 80 está aberta (necessária para validação Let's Encrypt)
sudo netstat -tlnp | grep :80

# Ver logs do Traefik para erros de ACME
docker logs traefik | grep -i acme
```

## 📝 Resumo dos Comandos Principais

```bash
# 1. Preparar ambiente
cd /opt/apps/applio
cp .env.example .env
nano .env

# 2. Verificar network
docker network create web  # Se não existir
docker network connect web traefik  # Se Traefik não estiver conectado

# 3. Pull e iniciar
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# 4. Verificar
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f

# 5. Testar
curl https://voice.eopix.me/health
curl -I https://voice-ui.eopix.me/
```

## 🔐 Segurança

- ✅ API Key configurada no `.env`
- ✅ Gradio protegido com BasicAuth
- ✅ HTTPS via Traefik (Let's Encrypt)
- ✅ Portas não expostas diretamente (apenas via Traefik)
- ✅ Volumes com permissões adequadas
- ✅ Logs limitados (max-size: 10m, max-file: 3)

