# Applio TTS Inference API

API REST para geração de áudio usando Text-to-Speech (TTS) com Voice Conversion (RVC) do Applio.

## 🚀 Início Rápido

### Instalação

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Configure as variáveis de ambiente (opcional):
```bash
# Crie um arquivo .env na pasta api/ (veja README_CONFIG.md para detalhes)
# Ou use variáveis de ambiente diretamente
export PYANNOTE_TOKEN=seu_token_huggingface  # Opcional, só para diarização
```

3. Inicie a API:
```bash
# Usando o script
./start.sh

# Ou diretamente com Python
python app.py

# Ou com uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000
```

### ⚙️ Configuração

Para mais detalhes sobre configuração, veja [README_CONFIG.md](./README_CONFIG.md).

As principais configurações:
- **Whisper**: Modelo de transcrição (padrão: `turbo`)
- **Pyannote**: Token do Hugging Face para diarização (opcional)
- **API**: Host e porta (padrão: `0.0.0.0:8000`)

### Acessar Documentação

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📡 Endpoints

### Informações

- `GET /` - Informações da API
- `GET /health` - Health check

### TTS (Text-to-Speech)

- `GET /voices` - Lista todas as vozes TTS disponíveis (Edge TTS)
- `POST /tts/generate` - Gera áudio usando TTS + RVC (versão simplificada)
- `POST /tts/inference` - Gera áudio usando TTS + RVC (versão completa)
- `GET /tts/download/{filename}` - Download de arquivo de áudio gerado

### Transcription (Transcrição)

- `POST /transcribe` - Transcreve áudio usando Whisper V3 Turbo + Pyannote diarization

### RVC (Retrieval-Based Voice Conversion)

- `GET /models` - Lista todos os modelos RVC disponíveis

## 📝 Exemplos de Uso

### Listar Vozes Disponíveis

```bash
curl http://localhost:8000/voices
```

Com filtro de idioma:
```bash
curl "http://localhost:8000/voices?language=pt-BR"
```

### Listar Modelos RVC

```bash
curl http://localhost:8000/models
```

### Gerar Áudio TTS + RVC

```bash
curl -X POST "http://localhost:8000/tts/inference" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Olá, este é um teste de síntese de voz.",
    "tts_voice": "pt-BR-FranciscaNeural",
    "model_path": "logs/modelo_exemplo/modelo.pth",
    "index_path": "logs/modelo_exemplo/modelo.index",
    "pitch": 0,
    "index_rate": 0.75,
    "export_format": "WAV"
  }'
```

### Gerar Áudio e Receber em Base64

```bash
curl -X POST "http://localhost:8000/tts/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Olá, este é um teste de síntese de voz.",
    "tts_voice": "pt-BR-FranciscaNeural",
    "model_path": "logs/modelo_exemplo/modelo.pth",
    "output_format": "OGG"
  }'
```

### Transcrever Áudio com Diarização

```bash
curl -X POST "http://localhost:8000/transcribe" \
  -F "file=@audio.mp3" \
  -F "language=pt" \
  -F "enable_diarization=true" \
  -F "model_size=turbo"
```

## 🔧 Parâmetros de TTS Inference

### Obrigatórios

- `text`: Texto para sintetizar (1-5000 caracteres)
- `tts_voice`: Voz TTS (ShortName da voz Edge TTS)
- `model_path`: Caminho do modelo RVC (.pth)

### Opcionais

#### TTS
- `tts_rate`: Taxa de velocidade (-100 a 100, padrão: 0)
- `index_path`: Caminho do arquivo index (auto-detectado se não fornecido)

#### RVC
- `pitch`: Pitch do áudio (-24 a 24, padrão: 0)
- `index_rate`: Taxa de influência do index (0.0 a 1.0, padrão: 0.75)
- `volume_envelope`: Volume envelope (0.0 a 1.0, padrão: 1.0)
- `protect`: Proteção de consoantes sem voz (0.0 a 0.5, padrão: 0.5)
- `f0_method`: Método de extração de pitch (crepe, crepe-tiny, rmvpe, fcpe, padrão: rmvpe)

#### Avançados
- `split_audio`: Dividir áudio em chunks (padrão: false)
- `f0_autotune`: Aplicar autotune (padrão: false)
- `f0_autotune_strength`: Força do autotune (0.0 a 1.0, padrão: 1.0)
- `proposed_pitch`: Ajustar pitch proposto (padrão: false)
- `proposed_pitch_threshold`: Threshold do pitch proposto (50.0 a 1200.0, padrão: 155.0)
- `clean_audio`: Limpar áudio (padrão: false)
- `clean_strength`: Força da limpeza (0.0 a 1.0, padrão: 0.5)
- `export_format`: Formato de exportação (WAV, MP3, FLAC, OGG, M4A, padrão: WAV)
- `embedder_model`: Modelo embedder (contentvec, spin, spin-v2, etc., padrão: contentvec)
- `embedder_model_custom`: Caminho do embedder customizado (se embedder_model='custom')
- `sid`: Speaker ID (padrão: 0)

#### Saída
- `return_base64`: Retornar áudio em base64 (padrão: false)
- `output_filename`: Nome do arquivo de saída (opcional)

## 🐍 Exemplo Python

```python
import requests
import base64

# URL da API
API_URL = "http://localhost:8000"

# Listar vozes
response = requests.get(f"{API_URL}/voices")
voices = response.json()
print(f"Vozes disponíveis: {voices['total']}")

# Listar modelos
response = requests.get(f"{API_URL}/models")
models = response.json()
print(f"Modelos disponíveis: {models['total']}")

# Gerar áudio
payload = {
    "text": "Olá, este é um teste de síntese de voz.",
    "tts_voice": "pt-BR-FranciscaNeural",
    "model_path": "logs/modelo_exemplo/modelo.pth",
    "return_base64": True
}

response = requests.post(f"{API_URL}/tts/inference", json=payload)
result = response.json()

if result["success"]:
    # Salvar áudio de base64
    if result["base64"]:
        audio_data = base64.b64decode(result["base64"])
        with open("output.wav", "wb") as f:
            f.write(audio_data)
        print(f"Áudio salvo: output.wav")
    else:
        print(f"Arquivo gerado: {result['output_path']}")
else:
    print(f"Erro: {result['message']}")
```

## 🔍 Variáveis de Ambiente

Você pode configurar a API usando variáveis de ambiente:

```bash
export HOST=0.0.0.0
export PORT=8000
export RELOAD=true  # Para desenvolvimento
```

## 🎤 Transcrição de Áudio

### Endpoint `/transcribe`

Transcreve áudio usando **Whisper V3 Turbo** (modelo mais moderno) com **Pyannote diarization** para identificar diferentes speakers.

#### Parâmetros

- `file` (obrigatório): Arquivo de áudio para transcrever
- `language` (opcional): Idioma do áudio (pt, en, es, etc.) ou 'auto' para detecção automática (padrão: pt)
- `enable_diarization` (opcional): Ativar diarização para identificar speakers (padrão: true)
- `word_timestamps` (opcional): Incluir timestamps por palavra (padrão: false)
- `model_size` (opcional): Tamanho do modelo Whisper - turbo, large-v3, large, medium, small, base, tiny (padrão: turbo)

#### Formatos Suportados

MP3, WAV, M4A, FLAC, OGG, WEBM, MP4, AAC

#### Exemplo de Resposta

```json
{
  "success": true,
  "message": "✅ Áudio transcrito com sucesso (com diarização)",
  "text": "Olá, este é um teste de transcrição com diarização.",
  "language": "pt",
  "duration": 5.2,
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "segments": [
    {
      "speaker": "SPEAKER_00",
      "start": 0.0,
      "end": 2.5,
      "text": "Olá, este é um teste"
    },
    {
      "speaker": "SPEAKER_01",
      "start": 2.5,
      "end": 5.2,
      "text": "de transcrição com diarização."
    }
  ]
}
```

### Configuração do Pyannote

Para usar diarização, você precisa de um token do Hugging Face:

1. Crie uma conta no [Hugging Face](https://huggingface.co/)
2. Aceite os termos do modelo [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
3. Gere um token em [Settings > Access Tokens](https://huggingface.co/settings/tokens)
3. Configure a variável de ambiente:

```bash
export PYANNOTE_TOKEN=seu_token_aqui
```

**Nota:** Se o token não estiver configurado, a transcrição funcionará normalmente, mas sem diarização.

## 📋 Requisitos

- Python 3.8+
- Applio instalado e configurado
- Modelos RVC treinados (em `logs/`)
- Dependências do Applio instaladas
- Whisper V3 Turbo (instalado automaticamente via requirements.txt)
- Pyannote.audio (instalado automaticamente via requirements.txt)

## 🛠️ Troubleshooting

### Erro: "Modelo não encontrado"
- Verifique se o caminho do modelo está correto
- Use `/models` para listar modelos disponíveis

### Erro: "Voz TTS não encontrada"
- Use `/voices` para listar vozes disponíveis
- Use o `ShortName` da voz (ex: "pt-BR-FranciscaNeural")

### Erro: "Arquivo index não encontrado"
- O index pode ser auto-detectado se não fornecido
- Verifique se o index está no mesmo diretório do modelo

## 📚 Documentação Adicional

- [Applio Documentation](https://docs.applio.org)
- [Edge TTS Voices](https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list)

## 📄 Licença

Consulte o arquivo LICENSE do projeto Applio.

