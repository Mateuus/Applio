# 🔐 Configuração de Autenticação - Interface Gradio

Guia para adicionar login/senha na interface Gradio do Applio usando Traefik BasicAuth.

## 📋 Pré-requisitos

- Traefik rodando e configurado
- `htpasswd` instalado (geralmente vem com `apache2-utils`)

## 🚀 Passo a Passo

### 1. Gerar Hash da Senha

**Opção A: Usando o script (Recomendado)**

```bash
./generate-password-hash.sh
```

O script vai pedir:
- Usuário
- Senha
- E gerar o hash formatado para o docker-compose

**Opção B: Manual**

```bash
# Gerar hash
htpasswd -nb admin senha_secreta

# Exemplo de saída:
# admin:$apr1$xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Escapar $ para docker-compose
echo $(htpasswd -nb admin senha_secreta) | sed 's/\$/\$\$/g'

# Saída formatada:
# admin:$$apr1$$xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. Atualizar docker-compose.prod.yml

Edite o arquivo `docker-compose.prod.yml` e substitua a linha:

```yaml
- "traefik.http.middlewares.applio-gradio-auth.basicauth.users=admin:$$apr1$$xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Pelo hash gerado:

```yaml
- "traefik.http.middlewares.applio-gradio-auth.basicauth.users=admin:$$apr1$$SEU_HASH_AQUI"
```

### 3. Múltiplos Usuários

Para adicionar múltiplos usuários, separe com vírgula:

```yaml
- "traefik.http.middlewares.applio-gradio-auth.basicauth.users=admin:$$apr1$$hash1,usuario2:$$apr1$$hash2"
```

### 4. Configurar DNS

Configure o DNS para o domínio da interface:

```
voice-ui.eopix.me -> IP_DO_SERVIDOR
```

### 5. Iniciar Serviços

```bash
docker-compose -f docker-compose.prod.yml up -d applio-gradio
```

### 6. Testar

Acesse: `https://voice-ui.eopix.me`

Você verá um popup de login pedindo usuário e senha.

## 🔧 Configuração Atual

### Domínios Configurados

- **API (sem autenticação)**: `voice.eopix.me` → Porta 8000
- **Interface Gradio (com autenticação)**: `voice-ui.eopix.me` → Porta 6969

### Estrutura

```
voice.eopix.me          → API FastAPI (pública, com API_KEY)
voice-ui.eopix.me       → Interface Gradio (com login/senha)
```

## 🔒 Segurança

### Recomendações

1. **Use senhas fortes**: Mínimo 12 caracteres, com números e símbolos
2. **HTTPS obrigatório**: Já configurado via Traefik
3. **API Key na API**: A API também tem autenticação via `API_KEY` no header
4. **Limite de tentativas**: Considere adicionar rate limiting

### Adicionar Rate Limiting

```yaml
labels:
  # Rate limiting
  - "traefik.http.middlewares.applio-gradio-ratelimit.ratelimit.average=10"
  - "traefik.http.middlewares.applio-gradio-ratelimit.ratelimit.period=1m"
  - "traefik.http.middlewares.applio-gradio-ratelimit.ratelimit.burst=5"
  # Aplicar ambos: auth + rate limit
  - "traefik.http.routers.applio-gradio.middlewares=applio-gradio-auth,applio-gradio-ratelimit"
```

## 🐛 Troubleshooting

### Hash não funciona

1. Verifique se os `$` estão duplicados (`$$`)
2. Certifique-se de que não há espaços extras
3. Teste o hash gerado com: `htpasswd -v usuario hash senha`

### Popup não aparece

1. Verifique se o middleware está aplicado no router
2. Verifique logs do Traefik: `docker logs traefik`
3. Teste diretamente: `curl -u usuario:senha https://voice-ui.eopix.me`

### Erro 401 Unauthorized

- Verifique usuário e senha
- Certifique-se de que o hash está correto
- Limpe cache do navegador

## 📝 Exemplo Completo

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.applio-gradio.rule=Host(`voice-ui.eopix.me`)"
  - "traefik.http.routers.applio-gradio.entrypoints=websecure"
  - "traefik.http.routers.applio-gradio.tls.certresolver=le"
  - "traefik.http.routers.applio-gradio.tls=true"
  - "traefik.http.services.applio-gradio.loadbalancer.server.port=6969"
  # Autenticação
  - "traefik.http.middlewares.applio-gradio-auth.basicauth.users=admin:$$apr1$$SEU_HASH"
  - "traefik.http.routers.applio-gradio.middlewares=applio-gradio-auth"
```

## 🔄 Atualizar Senha

1. Gere novo hash: `./generate-password-hash.sh`
2. Atualize no `docker-compose.prod.yml`
3. Reinicie: `docker-compose -f docker-compose.prod.yml up -d applio-gradio`

