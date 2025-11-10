# ⚙️ Configuração da API Applio TTS Inference

## 📋 Arquivo de Configuração

A API usa um arquivo `.env` para configurações. Crie um arquivo `.env` na pasta `api/` baseado no `.env.example`:

```bash
cd api/
cp .env.example .env
```

## 🔐 Variáveis de Ambiente

### API Settings

```env
API_HOST=0.0.0.0          # Host onde a API vai rodar
API_PORT=8000              # Porta da API
```

### Whisper (Transcrição)

```env
WHISPER_MODEL_SIZE=turbo    # Tamanho do modelo: turbo, large-v3, large, medium, small, base, tiny
WHISPER_PRELOAD=true        # Pré-carregar Whisper no startup (true/false)
```

**Modelos disponíveis:**
- `turbo` - Mais rápido e moderno (recomendado)
- `large-v3` - Alta qualidade, mais lento
- `large` - Alta qualidade
- `medium` - Qualidade média
- `small` - Qualidade menor, mais rápido
- `base` - Básico
- `tiny` - Muito rápido, menor qualidade

### Pyannote (Diarização)

```env
PYANNOTE_TOKEN=seu_token_aqui    # Token do Hugging Face (obrigatório para diarização)
PYANNOTE_PRELOAD=true            # Pré-carregar diarização no startup (só funciona se token configurado)
```

**Como obter o token:**
1. Acesse: https://huggingface.co/settings/tokens
2. Crie um token com permissões de leitura
3. Aceite os termos do modelo: https://huggingface.co/pyannote/speaker-diarization-3.1
4. Cole o token no arquivo `.env`

**Nota:** Se `PYANNOTE_TOKEN` não estiver configurado, a diarização não será pré-carregada e não estará disponível.

### GPU Settings (Opcional)

```env
CUDA_VISIBLE_DEVICES=0      # Controlar quais GPUs usar (ex: "0" ou "0,1")
```

### Paths (Opcional)

```env
OUTPUT_DIR=                 # Diretório para salvar áudios (padrão: assets/audios)
UPLOAD_DIR=                 # Diretório para uploads temporários (padrão: assets/uploads)
```

## 📝 Exemplo Completo

```env
# API
API_HOST=0.0.0.0
API_PORT=8000

# Whisper
WHISPER_MODEL_SIZE=turbo
WHISPER_PRELOAD=true

# Pyannote (Diarização)
PYANNOTE_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PYANNOTE_PRELOAD=true

# GPU (opcional)
CUDA_VISIBLE_DEVICES=0
```

## 🔄 Como Funciona

1. **No startup da API:**
   - Carrega configurações do arquivo `.env` ou variáveis de ambiente
   - Mostra resumo das configurações
   - Pré-carrega Whisper se `WHISPER_PRELOAD=true`
   - Pré-carrega diarização se `PYANNOTE_PRELOAD=true` E `PYANNOTE_TOKEN` configurado

2. **Nas requisições:**
   - Usa modelos já pré-carregados (sem delay)
   - Se modelo não estiver carregado, carrega sob demanda

## ⚠️ Importante

- O arquivo `.env` não deve ser commitado no Git (já está no `.gitignore`)
- Use variáveis de ambiente em produção para maior segurança
- Tokens e secrets nunca devem ser expostos publicamente

