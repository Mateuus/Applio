# 🐳 Docker - Applio API (Produção)

Este documento explica como usar o Docker Compose para produção com Traefik.

## 📦 Build e Push da Imagem Docker

### Método 1: Usando o Script Automatizado (Recomendado)

```bash
# Build e push da versão latest
./build-and-push.sh

# Build e push de uma versão específica
./build-and-push.sh v1.0.0
```

O script irá:
1. Verificar se você está logado no Docker Hub
2. Fazer o build da imagem
3. Criar tags `latest` e a versão especificada
4. Fazer push para o Docker Hub

### Método 2: Manual

#### 1. Login no Docker Hub

```bash
docker login
# Digite seu username e password do Docker Hub
```

#### 2. Build da Imagem

```bash
# Build com tag latest
docker build -t mateuus27/applio-api:latest -f Dockerfile .

# Build com versão específica (opcional)
docker build -t mateuus27/applio-api:v1.0.0 -f Dockerfile .
```

#### 3. Verificar a Imagem

```bash
docker images | grep applio-api
```

#### 4. Push para Docker Hub

```bash
# Push da versão latest
docker push mateuus27/applio-api:latest

# Push da versão específica (se criou)
docker push mateuus27/applio-api:v1.0.0
```

### Verificar no Docker Hub

Após o push, a imagem estará disponível em:
- https://hub.docker.com/r/mateuus27/applio-api

---

## 📋 Pré-requisitos

1. **Docker** e **Docker Compose** instalados
2. **Traefik** configurado e rodando na rede `web`
3. **GPU NVIDIA** com drivers e Docker GPU runtime configurado
4. **Rede externa `web`** criada pelo Traefik:
   ```bash
   docker network create web
   ```

## 🚀 Quick Start

### 1. Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```bash
cp api/.env.example .env
# Edite o .env com suas configurações
nano .env
```

**Variáveis importantes:**
- `PYANNOTE_TOKEN` - Token do Hugging Face (opcional, para diarização)
- `API_KEY` - Chave de autenticação da API (opcional)
- `CUDA_VISIBLE_DEVICES` - Controlar quais GPUs usar (opcional)

### 2. Usar Imagem do Docker Hub ou Build Local

**Opção A: Usar imagem do Docker Hub (Recomendado)**

A imagem já está configurada no `docker-compose.prod.yml`:
```yaml
image: mateuus27/applio-api:latest
```

**Opção B: Build local**

Se quiser fazer build local ao invés de usar a imagem do Docker Hub:

```bash
# Edite docker-compose.prod.yml e descomente a seção build
# build:
#   context: .
#   dockerfile: Dockerfile

# Depois execute:
docker-compose -f docker-compose.prod.yml build
```

### 3. Iniciar os Serviços

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 4. Verificar Logs

```bash
docker-compose -f docker-compose.prod.yml logs -f applio-api
```

### 5. Testar a API

```bash
# Health check
curl https://voice.eopix.me/health

# Ou via Traefik (se configurado)
curl http://localhost:8000/health
```

## 🔧 Configuração do Traefik

O `docker-compose.prod.yml` está configurado para usar o Traefik como reverse proxy:

- **Domínio:** `voice.eopix.me`
- **Porta interna:** `8000`
- **SSL/TLS:** Automático via Let's Encrypt
- **Sticky Sessions:** Habilitado para WebSockets

### Labels do Traefik

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.applio.rule=Host(`voice.eopix.me`)"
  - "traefik.http.routers.applio.entrypoints=websecure"
  - "traefik.http.routers.applio.tls.certresolver=le"
  - "traefik.http.services.applio.loadbalancer.server.port=8000"
```

## 📦 Múltiplas Instâncias

Para rodar múltiplas instâncias (load balancing):

```bash
# Escalar para 2 instâncias
docker-compose -f docker-compose.prod.yml up -d --scale applio-api=2
```

**Importante:**
- Sticky sessions estão habilitados para manter conexões WebSocket na mesma instância
- O Traefik faz load balancing automaticamente entre as instâncias
- Cada instância precisa de GPU dedicada (ou compartilhar via `CUDA_VISIBLE_DEVICES`)

## 🔍 Health Check

O container tem health check configurado:

```yaml
healthcheck:
  test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s  # Tempo maior para carregar modelos
```

## 📁 Volumes

Os seguintes volumes são montados:

- `./logs:/app/logs` - Logs da aplicação
- `./api/logs:/app/api/logs` - Logs da API
- `./assets:/app/assets:ro` - Assets (read-only)
- `./rvc/models:/app/rvc/models` - Modelos RVC
- `./api/config:/app/api/config:ro` - Configurações (read-only)
- `./outputs:/app/outputs` - Áudios gerados
- `./uploads:/app/uploads` - Uploads temporários

## 🛑 Parar os Serviços

```bash
docker-compose -f docker-compose.prod.yml down
```

Para remover volumes também:

```bash
docker-compose -f docker-compose.prod.yml down -v
```

## 🔄 Atualizar

```bash
# Parar serviços
docker-compose -f docker-compose.prod.yml down

# Atualizar código (se usar build local)
git pull
docker-compose -f docker-compose.prod.yml build

# Reiniciar
docker-compose -f docker-compose.prod.yml up -d
```

## 🐛 Troubleshooting

### GPU não detectada

```bash
# Verificar se NVIDIA runtime está disponível
docker run --rm --gpus all nvidia/cuda:11.0.3-base-ubuntu20.04 nvidia-smi

# Verificar logs do container
docker-compose -f docker-compose.prod.yml logs applio-api | grep -i gpu
```

### Traefik não encontra o serviço

1. Verifique se a rede `web` existe:
   ```bash
   docker network ls | grep web
   ```

2. Verifique se o Traefik está rodando:
   ```bash
   docker ps | grep traefik
   ```

3. Verifique os logs do Traefik:
   ```bash
   docker logs traefik
   ```

### Porta 8000 já em uso

Se a porta 8000 estiver em uso, você pode:

1. Mudar a porta no `docker-compose.prod.yml` (mas não é necessário, pois o Traefik roteia via domínio)
2. Verificar qual processo está usando:
   ```bash
   sudo lsof -i :8000
   ```

## 📚 Mais Informações

- [README_CONFIG.md](./api/README_CONFIG.md) - Configuração detalhada da API
- [README.md](./README.md) - Documentação geral do Applio

