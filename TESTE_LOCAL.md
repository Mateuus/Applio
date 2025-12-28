# 🧪 Teste Local - Applio

Guia rápido para testar o Applio localmente sem Traefik.

## 🚀 Quick Start

### Opção 1: Usar docker-compose.local.yml (Recomendado)

Este arquivo expõe as portas diretamente, sem precisar do Traefik:

```bash
# Criar rede web (se não existir)
docker network create web 2>/dev/null || true

# Iniciar serviços
docker-compose -f docker-compose.local.yml up -d

# Ver logs
docker-compose -f docker-compose.local.yml logs -f

# Parar serviços
docker-compose -f docker-compose.local.yml down
```

**Acessos:**
- Interface Gradio: http://localhost:6969
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Opção 2: Usar docker-compose.prod.yml (com Traefik)

Se você tem Traefik rodando localmente:

```bash
# Criar rede web (se não existir)
docker network create web 2>/dev/null || true

# Iniciar serviços
docker-compose -f docker-compose.prod.yml up -d

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f
```

**Acessos (via Traefik):**
- Interface Gradio: https://voice-ui.eopix.me (com login/senha)
- API: https://voice.eopix.me

## 📋 Pré-requisitos

1. **Rede `web` criada:**
   ```bash
   docker network create web
   ```

2. **Arquivo `.env` (opcional):**
   ```bash
   cp .env.example .env
   # Edite conforme necessário
   ```

3. **GPU NVIDIA (opcional, mas recomendado):**
   - Drivers NVIDIA instalados
   - nvidia-container-runtime configurado

## 🔧 Comandos Úteis

### Ver status dos containers
```bash
docker-compose -f docker-compose.local.yml ps
```

### Ver logs em tempo real
```bash
docker-compose -f docker-compose.local.yml logs -f applio-gradio
docker-compose -f docker-compose.local.yml logs -f applio-api
```

### Reiniciar um serviço
```bash
docker-compose -f docker-compose.local.yml restart applio-gradio
```

### Parar todos os serviços
```bash
docker-compose -f docker-compose.local.yml down
```

### Limpar tudo (incluindo volumes)
```bash
docker-compose -f docker-compose.local.yml down -v
```

## 🐛 Troubleshooting

### Erro: "network web declared as external, but could not be found"

```bash
docker network create web
```

### Erro: "env file .env not found"

O arquivo `.env` é opcional. Se quiser usar:
```bash
cp .env.example .env
```

Ou comente a linha `env_file:` no docker-compose.

### Container reiniciando constantemente

Verifique os logs:
```bash
docker-compose -f docker-compose.local.yml logs applio-gradio
```

### Porta já em uso

Se a porta 6969 ou 8000 já estiver em uso:
1. Pare o processo que está usando a porta
2. Ou altere as portas no docker-compose.local.yml:
   ```yaml
   ports:
     - "6969:6969"  # Altere para outra porta, ex: "6968:6969"
   ```

## 📝 Diferenças entre os arquivos

| Arquivo | Uso | Portas Expostas | Traefik |
|---------|-----|-----------------|---------|
| `docker-compose.local.yml` | Testes locais | Sim (6969, 8000) | Não |
| `docker-compose.prod.yml` | Produção | Não (via Traefik) | Sim |

## ✅ Checklist de Teste

- [ ] Rede `web` criada
- [ ] Arquivo `.env` configurado (opcional)
- [ ] Container iniciado sem erros
- [ ] Interface Gradio acessível em http://localhost:6969
- [ ] API acessível em http://localhost:8000
- [ ] Health check funcionando: http://localhost:8000/health
- [ ] API Docs acessível: http://localhost:8000/docs

