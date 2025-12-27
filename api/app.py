#!/usr/bin/env python3
"""
FastAPI para TTS Inference do Applio
API REST para geração de áudio usando Text-to-Speech com Voice Conversion (RVC)
"""

import os
import sys
import base64
import json
import tempfile
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

# Adicionar paths necessários
# Obter diretório raiz do Applio (um nível acima de api/)
now_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Mudar para o diretório raiz para que os caminhos relativos funcionem
os.chdir(now_dir)
sys.path.insert(0, now_dir)

# Importar configurações
from api.config import settings, print_config_summary

# Importar funções do Applio
from core import run_tts_script, run_tts_only_script, load_voices_data
from tabs.inference.inference import get_files, match_index, get_speakers_id
from rvc.configs.config import Config, get_gpu_info
import torch

# Configurações de diretórios (usando settings)
OUTPUT_DIR = Path(settings.OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Variáveis globais
_voices_data = None
_whisper_model = None
_WHISPER_READY = False
_diarization_pipeline = None
_DIARIZATION_READY = False
_models_config = None


def load_models_config():
    """Carrega configuração de modelos (mapeamento ID -> model_path)"""
    global _models_config
    if _models_config is None:
        config_path = os.path.join(os.path.dirname(__file__), "config", "models_config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    _models_config = json.load(f)
            else:
                # Criar arquivo padrão se não existir
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                _models_config = {"models": []}
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(_models_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Erro ao carregar models_config.json: {e}")
            _models_config = {"models": []}
    return _models_config


def get_model_by_id(model_id: str) -> Optional[dict]:
    """
    Busca modelo por ID no arquivo de configuração
    
    Args:
        model_id: ID do modelo (ex: "operario6532df")
    
    Returns:
        Dicionário com informações do modelo ou None se não encontrado
    """
    config = load_models_config()
    for model in config.get("models", []):
        if model.get("id") == model_id:
            return model
    return None


def resolve_model_path(model_path_or_id: str) -> tuple[Optional[str], Optional[str], Optional[dict]]:
    """
    Resolve model_path que pode ser um ID ou caminho completo
    
    Args:
        model_path_or_id: ID do modelo (ex: "16c19771-9ece-45fd-8ce5-53bb5263a63d") ou caminho completo (ex: "logs/Lula/Lula.pth")
    
    Returns:
        Tupla (model_path, index_path, model_info)
        - model_path: Caminho completo do modelo .pth
        - index_path: Caminho do arquivo index (do config se disponível, senão auto-detectado)
        - model_info: Informações do modelo do config (None se não estiver no config)
    """
    # Primeiro, tentar buscar por ID no config
    model_info = get_model_by_id(model_path_or_id)
    
    if model_info:
        # Encontrou no config, usar o model_path e index_path do config
        # Suporta ambos os formatos: model_path/path e index_path/model_index (retrocompatibilidade)
        model_path = model_info.get("model_path") or model_info.get("path")
        if model_path and os.path.exists(model_path):
            # Usar index_path ou model_index do config (prioriza index_path)
            index_path = model_info.get("index_path") or model_info.get("model_index")
            if not index_path or not os.path.exists(index_path):
                # Se não tem no config ou não existe, auto-detectar
                index_path = match_index(model_path)
            return model_path, index_path, model_info
    
    # Se não encontrou no config ou não existe, verificar se é um caminho válido
    if os.path.exists(model_path_or_id):
        # É um caminho válido
        index_path = match_index(model_path_or_id)
        return model_path_or_id, index_path, None
    
    # Não encontrou nem no config nem como caminho
    return None, None, None


def load_tts_voices():
    """Carrega dados das vozes TTS"""
    global _voices_data
    if _voices_data is None:
        _voices_data = load_voices_data()
    return _voices_data


def load_whisper_model(model_size: str = "turbo", force_reload: bool = False):
    """Carrega modelo Whisper V3 Turbo"""
    global _whisper_model, _WHISPER_READY
    
    # Se já está carregado e não é para forçar reload, retornar o existente
    if _whisper_model is not None and _WHISPER_READY and not force_reload:
        # Se o modelo solicitado é diferente, avisar mas usar o carregado
        if model_size != "turbo":
            print(f"⚠️ Modelo {model_size} solicitado, mas turbo já está carregado. Usando turbo.")
        return _whisper_model
    
    print(f"🔄 Carregando Whisper {model_size}...")
    try:
        import whisper
        
        # Whisper V3 Turbo é o modelo mais recente e rápido
        # Se turbo não estiver disponível, tenta large-v3
        try:
            _whisper_model = whisper.load_model(model_size)
        except Exception as e:
            if model_size == "turbo":
                print("⚠️ Modelo turbo não encontrado, usando large-v3...")
                try:
                    _whisper_model = whisper.load_model("large-v3")
                except:
                    print("⚠️ large-v3 também não encontrado, tentando large...")
                    _whisper_model = whisper.load_model("large")
            else:
                raise
        
        _WHISPER_READY = True
        print(f"✅ Whisper {model_size} carregado!")
        return _whisper_model
    except ImportError:
        print(f"⚠️ Erro: openai-whisper não está instalado!")
        print("   Instale com: pip install openai-whisper")
        _WHISPER_READY = False
        return None
    except Exception as e:
        print(f"⚠️ Erro ao carregar Whisper: {e}")
        _WHISPER_READY = False
        return None


def load_diarization_pipeline():
    """Carrega pipeline de diarização Pyannote (lazy loading)"""
    global _diarization_pipeline, _DIARIZATION_READY
    
    if _diarization_pipeline is not None and _DIARIZATION_READY:
        return _diarization_pipeline
    
    # Verificar se token está configurado
    if not settings.has_pyannote_token:
        print("⚠️ PYANNOTE_TOKEN não configurado. Diarização não está disponível.")
        print("   Configure no arquivo .env ou variável de ambiente:")
        print("   PYANNOTE_TOKEN=seu_token_huggingface")
        _DIARIZATION_READY = False
        return None
    
    print("🔄 Carregando pipeline de diarização Pyannote...")
    try:
        from pyannote.audio import Pipeline
        
        # Carregar pipeline de diarização usando token das configurações
        _diarization_pipeline = Pipeline.from_pretrained(
            settings.PYANNOTE_MODEL,
            use_auth_token=settings.PYANNOTE_TOKEN
        )
        
        # Mover para GPU se disponível
        config = Config()
        if config.device.startswith("cuda"):
            _diarization_pipeline = _diarization_pipeline.to(torch.device(config.device))
        
        _DIARIZATION_READY = True
        print("✅ Pipeline de diarização Pyannote carregado!")
        return _diarization_pipeline
    except ImportError:
        print("⚠️ pyannote.audio não está instalado. Instale com: pip install pyannote.audio")
        _DIARIZATION_READY = False
        return None
    except Exception as e:
        print(f"⚠️ Erro ao carregar pipeline Pyannote: {e}")
        print("   Verifique se o token do Hugging Face está configurado corretamente no .env")
        _DIARIZATION_READY = False
        return None


# Lifespan event handler
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Gerencia o ciclo de vida da aplicação"""
    print("\n🔄 Inicializando API do Applio...")
    
    # Mostrar resumo das configurações
    print_config_summary()
    
    load_tts_voices()
    load_models_config()  # Carregar configuração de modelos
    
    # Pré-carregar Whisper no startup se configurado
    if settings.WHISPER_PRELOAD:
        print(f"🔄 Pré-carregando Whisper {settings.WHISPER_MODEL_SIZE}...")
        whisper_model = load_whisper_model(settings.WHISPER_MODEL_SIZE)
        if whisper_model and _WHISPER_READY:
            print(f"✅ Whisper {settings.WHISPER_MODEL_SIZE} pré-carregado!")
        else:
            print("⚠️ Whisper não foi carregado. Verifique os logs.")
    else:
        print("ℹ️ Whisper não será pré-carregado (WHISPER_PRELOAD=false)")
    
    # Pré-carregar diarização apenas se token estiver configurado E preload estiver habilitado
    if settings.should_preload_diarization:
        print("🔄 Pré-carregando pipeline de diarização...")
        diarization_pipeline = load_diarization_pipeline()
        if diarization_pipeline and _DIARIZATION_READY:
            print("✅ Pipeline de diarização pré-carregado!")
        else:
            print("⚠️ Diarização não foi carregada. Verifique o token PYANNOTE_TOKEN no .env")
    elif settings.has_pyannote_token and not settings.PYANNOTE_PRELOAD:
        print("ℹ️ Diarização não será pré-carregada (PYANNOTE_PRELOAD=false)")
    else:
        print("ℹ️ Diarização não será pré-carregada (PYANNOTE_TOKEN não configurado)")
    
    print("✅ API do Applio pronta!\n")
    
    yield  # Aplicação rodando
    
    # Shutdown: Limpeza (opcional)
    print("\n🔄 Encerrando API do Applio...")


# Criar app FastAPI com lifespan
app = FastAPI(
    title="🎤 Applio TTS Inference API",
    description="API REST para geração de áudio usando Text-to-Speech com Voice Conversion (RVC)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Security
security = HTTPBearer(auto_error=False)


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verifica a API key se estiver configurada
    Se API_KEY não estiver configurada, permite acesso público
    """
    if not settings.has_api_key:
        # API pública - não requer autenticação
        return True
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="API key requerida. Use: Authorization: Bearer <api_key>"
        )
    
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(
            status_code=403,
            detail="API key inválida"
        )
    
    return True


# ==================== Models Pydantic ====================

def clean_text(text: str) -> str:
    """Remove caracteres de controle inválidos do texto"""
    import re
    # Remover caracteres de controle exceto quebras de linha e tabs
    # Permitir: \n (LF), \r\n (CRLF), \t (TAB)
    # Remover outros caracteres de controle (0x00-0x1F exceto \n, \r, \t)
    cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    # Normalizar quebras de linha
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
    return cleaned.strip()


class GenerateRequest(BaseModel):
    """Request model para endpoint /generate - TTS com ou sem RVC"""
    text: str = Field(..., description="Texto para sintetizar", min_length=1, max_length=5000)
    tts_voice: Optional[str] = Field(None, description="Voz TTS (Edge TTS) - ShortName da voz (ex: pt-BR-FranciscaNeural). Use /voices para listar. Se model_id for fornecido e tts_voice não for especificado, será usado o tts_voice do modelo no config")
    model_id: Optional[str] = Field(None, description="ID do modelo (ex: '16c19771-9ece-45fd-8ce5-53bb5263a63d') ou caminho completo (ex: 'logs/Lula/Lula.pth'). Se não fornecido, gera apenas TTS sem RVC. Use /models para listar IDs e caminhos disponíveis. O index será obtido automaticamente do config ou auto-detectado")
    tts_rate: int = Field(0, description="Taxa de velocidade TTS (-100 a 100)", ge=-100, le=100)
    output_format: str = Field("WAV", description="Formato de saída (WAV, MP3, FLAC, OGG, M4A)")
    
    @classmethod
    def validate_text(cls, v):
        """Valida e limpa o texto"""
        if isinstance(v, str):
            return clean_text(v)
        return v


class SimpleTTSRequest(BaseModel):
    """Request model simplificado para TTS - similar à interface do Applio"""
    text: str = Field(..., description="Texto para sintetizar", min_length=1, max_length=5000)
    tts_voice: str = Field(..., description="Voz TTS (Edge TTS) - ShortName da voz (ex: pt-BR-FranciscaNeural)")
    model_id: str = Field(..., description="ID do modelo (ex: '16c19771-9ece-45fd-8ce5-53bb5263a63d') ou caminho completo (ex: 'logs/Lula/Lula.pth'). Use /models para listar IDs e caminhos disponíveis. O index será obtido automaticamente do config ou auto-detectado")
    tts_rate: int = Field(0, description="Taxa de velocidade TTS (-100 a 100)", ge=-100, le=100)
    return_base64: bool = Field(True, description="Retornar áudio em base64 (padrão: true - sempre retorna base64)")
    output_format: str = Field("OGG", description="Formato de saída quando return_base64=true (WAV, MP3, FLAC, OGG, M4A). Padrão: OGG para R2")
    
    @classmethod
    def validate_text(cls, v):
        """Valida e limpa o texto"""
        if isinstance(v, str):
            return clean_text(v)
        return v


class TTSInferenceRequest(BaseModel):
    """Request model completo para TTS Inference com todas as opções avançadas"""
    text: str = Field(..., description="Texto para sintetizar", min_length=1, max_length=5000)
    tts_voice: str = Field(..., description="Voz TTS (Edge TTS) - ShortName da voz")
    model_id: str = Field(..., description="ID do modelo (ex: '16c19771-9ece-45fd-8ce5-53bb5263a63d') ou caminho completo (ex: 'logs/Lula/Lula.pth'). Use /models para listar IDs e caminhos disponíveis. O index será obtido automaticamente do config ou auto-detectado")
    
    # Parâmetros TTS
    tts_rate: int = Field(0, description="Taxa de velocidade TTS (-100 a 100)", ge=-100, le=100)
    
    # Parâmetros RVC
    pitch: int = Field(0, description="Pitch do áudio (-24 a 24)", ge=-24, le=24)
    index_rate: float = Field(0.75, description="Taxa de influência do index (0.0 a 1.0)", ge=0.0, le=1.0)
    volume_envelope: float = Field(1.0, description="Volume envelope (0.0 a 1.0)", ge=0.0, le=1.0)
    protect: float = Field(0.5, description="Proteção de consoantes sem voz (0.0 a 0.5)", ge=0.0, le=0.5)
    f0_method: str = Field("rmvpe", description="Método de extração de pitch (crepe, crepe-tiny, rmvpe, fcpe)")
    
    # Opções avançadas
    split_audio: bool = Field(False, description="Dividir áudio em chunks")
    f0_autotune: bool = Field(False, description="Aplicar autotune")
    f0_autotune_strength: float = Field(1.0, description="Força do autotune (0.0 a 1.0)", ge=0.0, le=1.0)
    proposed_pitch: bool = Field(False, description="Ajustar pitch proposto")
    proposed_pitch_threshold: float = Field(155.0, description="Threshold do pitch proposto (50.0 a 1200.0)", ge=50.0, le=1200.0)
    clean_audio: bool = Field(False, description="Limpar áudio")
    clean_strength: float = Field(0.5, description="Força da limpeza (0.0 a 1.0)", ge=0.0, le=1.0)
    export_format: str = Field("WAV", description="Formato de exportação (WAV, MP3, FLAC, OGG, M4A)")
    embedder_model: str = Field("contentvec", description="Modelo embedder (contentvec, spin, spin-v2, chinese-hubert-base, japanese-hubert-base, korean-hubert-base, custom)")
    embedder_model_custom: Optional[str] = Field(None, description="Caminho do embedder customizado (se embedder_model='custom')")
    sid: int = Field(0, description="Speaker ID", ge=0)
    
    # Opções de saída
    return_base64: bool = Field(False, description="Retornar áudio em base64 ao invés de arquivo")
    output_filename: Optional[str] = Field(None, description="Nome do arquivo de saída (opcional)")


class TTSInferenceResponse(BaseModel):
    """Response model para TTS Inference"""
    success: bool
    message: str
    text: str
    tts_voice: str
    model_path: Optional[str] = None  # Opcional quando não há modelo RVC
    index_path: Optional[str] = None
    output_file: Optional[str] = None
    output_path: Optional[str] = None
    base64: Optional[str] = None  # Sempre presente quando return_base64=true (endpoint /tts/generate)
    format: Optional[str] = None  # Formato do áudio (WAV, OGG, MP3, etc) - útil para conversão
    size_kb: Optional[float] = None
    duration_seconds: Optional[float] = None


class VoiceInfo(BaseModel):
    """Informações sobre uma voz TTS"""
    short_name: str
    name: str
    locale: str
    gender: str
    language: str


class VoicesListResponse(BaseModel):
    """Response model para lista de vozes"""
    success: bool
    voices: List[VoiceInfo]
    total: int
    language_filter: Optional[str] = None


class ModelInfo(BaseModel):
    """Informações sobre um modelo RVC"""
    id: Optional[str] = None  # ID do modelo (se estiver no config)
    path: str
    name: str
    index_path: Optional[str] = None
    description: Optional[str] = None  # Descrição do modelo (se estiver no config)


class ModelsListResponse(BaseModel):
    """Response model para lista de modelos"""
    success: bool
    models: List[ModelInfo]
    total: int


class ModelIndexResponse(BaseModel):
    """Response model para index file de um modelo"""
    success: bool
    model_path: str
    index_path: Optional[str]
    message: str


class SpeakerIDsResponse(BaseModel):
    """Response model para speaker IDs de um modelo"""
    success: bool
    model_path: str
    speaker_ids: List[int]
    total: int


class SpeakerSegment(BaseModel):
    """Segmento de fala de um speaker"""
    speaker: str
    start: float
    end: float
    text: str


class TranscribeResponse(BaseModel):
    """Response model para transcrição"""
    success: bool
    message: str
    text: str
    language: str
    duration: float
    segments: Optional[List[SpeakerSegment]] = None
    speakers: Optional[List[str]] = None
    word_timestamps: Optional[List[dict]] = None


# ==================== Endpoints ====================

@app.get("/", tags=["Info"])
async def root():
    """Endpoint raiz - informações da API"""
    return {
        "name": "Applio TTS Inference API",
        "version": "1.0.0",
        "description": "API REST para geração de áudio usando Text-to-Speech com Voice Conversion (RVC)",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", tags=["Info"])
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/gpu/status", tags=["Info"])
async def gpu_status():
    """
    Verifica o status da GPU e qual device está sendo usado pelo Applio
    
    Returns:
        Informações sobre GPU/CPU disponível e qual está sendo usado
    """
    try:
        config = Config()
        cuda_available = torch.cuda.is_available()
        gpu_count = torch.cuda.device_count() if cuda_available else 0
        
        gpu_info_list = []
        if cuda_available:
            for i in range(gpu_count):
                gpu_name = torch.cuda.get_device_name(i)
                props = torch.cuda.get_device_properties(i)
                mem_gb = props.total_memory / (1024**3)
                is_current = i == int(config.device.split(":")[-1]) if config.device.startswith("cuda") else False
                gpu_info_list.append({
                    "id": i,
                    "name": gpu_name,
                    "memory_gb": round(mem_gb, 2),
                    "current_device": is_current
                })
        
        return {
            "cuda_available": cuda_available,
            "device": config.device,
            "gpu_name": config.gpu_name,
            "gpu_count": gpu_count,
            "gpus": gpu_info_list,
            "gpu_memory_gb": config.gpu_mem if config.gpu_mem else None,
            "message": f"Usando {config.device}" + (f" ({config.gpu_name})" if config.gpu_name else " (CPU)")
        }
    except Exception as e:
        return {
            "cuda_available": torch.cuda.is_available() if 'torch' in globals() else False,
            "device": "unknown",
            "error": str(e)
        }


@app.get("/voices", response_model=VoicesListResponse, tags=["TTS"])
async def list_voices(language: Optional[str] = None, _: bool = Depends(verify_api_key)):
    """
    Lista todas as vozes TTS disponíveis (Edge TTS)
    
    Args:
        language: Filtrar por idioma (ex: 'pt-BR', 'en-US')
    
    Returns:
        Lista de vozes disponíveis
    """
    try:
        voices_data = load_tts_voices()
        
        # Filtrar por idioma se fornecido
        if language:
            filtered_voices = [
                voice for voice in voices_data
                if language.lower() in voice.get("ShortName", "").lower()
            ]
        else:
            filtered_voices = voices_data
        
        # Converter para formato de resposta
        voices_list = []
        for voice in filtered_voices:
            voices_list.append(VoiceInfo(
                short_name=voice.get("ShortName", ""),
                name=voice.get("Name", ""),
                locale=voice.get("Locale", ""),
                gender=voice.get("Gender", ""),
                language=voice.get("Locale", "").split("-")[0] if "-" in voice.get("Locale", "") else voice.get("Locale", "")
            ))
        
        return VoicesListResponse(
            success=True,
            voices=voices_list,
            total=len(voices_list),
            language_filter=language
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar vozes: {str(e)}"
        )


@app.get("/models", response_model=ModelsListResponse, tags=["RVC"])
async def list_models(_: bool = Depends(verify_api_key)):
    """
    Lista todos os modelos RVC disponíveis
    
    Retorna modelos de duas fontes:
    1. Modelos configurados em models_config.json (com ID)
    2. Modelos encontrados no sistema de arquivos (sem ID)
    
    Returns:
        Lista de modelos RVC com seus respectivos index files e IDs (se disponíveis)
    """
    try:
        # Carregar modelos do config
        config = load_models_config()
        config_models = {m.get("model_path"): m for m in config.get("models", [])}
        
        # Buscar modelos no sistema de arquivos
        models = get_files("model")
        
        models_list = []
        processed_paths = set()
        
        # Primeiro, adicionar modelos do config (com ID)
        for model_info in config.get("models", []):
            model_path = model_info.get("model_path")
            if model_path and os.path.exists(model_path):
                # Usar model_index do config se disponível, senão auto-detectar
                index_path = model_info.get("model_index")
                if not index_path or not os.path.exists(index_path):
                    index_path = match_index(model_path)
                models_list.append(ModelInfo(
                    id=model_info.get("id"),
                    path=model_path,
                    name=model_info.get("name", os.path.basename(model_path)),
                    index_path=index_path,
                    description=model_info.get("description")
                ))
                processed_paths.add(model_path)
        
        # Depois, adicionar modelos não configurados (sem ID)
        for model_path in models:
            if model_path not in processed_paths:
                index_path = match_index(model_path)
                models_list.append(ModelInfo(
                    id=None,
                    path=model_path,
                    name=os.path.basename(model_path),
                    index_path=index_path,
                    description=None
                ))
        
        return ModelsListResponse(
            success=True,
            models=models_list,
            total=len(models_list)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar modelos: {str(e)}"
        )


@app.get("/models/{model_path:path}/index", response_model=ModelIndexResponse, tags=["RVC"])
async def get_model_index(model_path: str, _: bool = Depends(verify_api_key)):
    """
    Obtém o arquivo index correspondente a um modelo RVC
    
    Args:
        model_path: ID do modelo (ex: '16c19771-9ece-45fd-8ce5-53bb5263a63d') ou caminho completo (ex: logs/Lula/Lula.pth)
    
    Returns:
        Caminho do arquivo index correspondente
    """
    try:
        # Resolver model_path (pode ser ID ou caminho completo)
        resolved_model_path, index_path, _ = resolve_model_path(model_path)
        
        if not resolved_model_path:
            raise HTTPException(
                status_code=404,
                detail=f"Modelo não encontrado: {model_path}. Use /models para listar IDs e caminhos disponíveis."
            )
        
        return ModelIndexResponse(
            success=True,
            model_path=resolved_model_path,
            index_path=index_path,
            message=f"Index file encontrado: {index_path}" if index_path else "Nenhum index file encontrado para este modelo"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter index: {str(e)}"
        )


@app.get("/models/{model_path:path}/speakers", response_model=SpeakerIDsResponse, tags=["RVC"])
async def get_model_speakers(model_path: str, _: bool = Depends(verify_api_key)):
    """
    Obtém os Speaker IDs disponíveis para um modelo RVC
    
    Args:
        model_path: ID do modelo (ex: '16c19771-9ece-45fd-8ce5-53bb5263a63d') ou caminho completo (ex: logs/Lula/Lula.pth)
    
    Returns:
        Lista de Speaker IDs disponíveis
    """
    try:
        # Resolver model_path (pode ser ID ou caminho completo)
        resolved_model_path, _, _ = resolve_model_path(model_path)
        
        if not resolved_model_path:
            raise HTTPException(
                status_code=404,
                detail=f"Modelo não encontrado: {model_path}. Use /models para listar IDs e caminhos disponíveis."
            )
        
        speaker_ids = get_speakers_id(resolved_model_path)
        
        return SpeakerIDsResponse(
            success=True,
            model_path=resolved_model_path,
            speaker_ids=speaker_ids,
            total=len(speaker_ids)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter speaker IDs: {str(e)}"
        )


@app.post("/generate", response_model=TTSInferenceResponse, tags=["TTS"])
async def generate(request: GenerateRequest, _: bool = Depends(verify_api_key)):
    """
    Gera áudio TTS com ou sem modelo RVC
    
    Este endpoint permite gerar áudio de duas formas:
    1. **Apenas TTS** (sem modelo RVC): Se `model_id` não for fornecido, gera apenas o áudio TTS usando Edge TTS
    2. **TTS + RVC**: Se `model_id` for fornecido, gera TTS e aplica Voice Conversion usando o modelo RVC
    
    Parâmetros obrigatórios:
    - text: Texto para sintetizar
    - tts_voice: Voz TTS (Edge TTS) - ShortName da voz (use /voices para listar). Obrigatório se model_id não for fornecido. Se model_id for fornecido e tts_voice não for especificado, será usado o tts_voice do modelo no config
    
    Parâmetros opcionais:
    - model_id: ID do modelo (ex: '16c19771-9ece-45fd-8ce5-53bb5263a63d') ou caminho completo (ex: 'logs/Lula/Lula.pth') - se não fornecido, gera apenas TTS sem RVC (use /models para listar IDs e caminhos). O index será obtido automaticamente do config ou auto-detectado
    - tts_rate: Velocidade TTS (-100 a 100, padrão: 0)
    - output_format: Formato de saída (WAV, MP3, FLAC, OGG, M4A, padrão: WAV)
    
    Returns:
        TTSInferenceResponse com áudio em base64
    """
    try:
        # Limpar texto de caracteres de controle
        cleaned_text = clean_text(request.text)
        if not cleaned_text:
            raise HTTPException(
                status_code=400,
                detail="Texto inválido ou vazio após limpeza"
            )
        
        # Validar formato de saída
        valid_formats = ["WAV", "MP3", "FLAC", "OGG", "M4A"]
        output_format = request.output_format.upper()
        if output_format not in valid_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Formato inválido: {output_format}. Formatos válidos: {', '.join(valid_formats)}"
            )
        
        # Determinar tts_voice: usar do modelo se model_id fornecido e tts_voice não fornecido
        # Também resolver modelo antecipadamente para evitar resolver duas vezes
        tts_voice = request.tts_voice
        resolved_model_path = None
        auto_index_path = None
        model_info = None
        
        if request.model_id and request.model_id.strip():
            # Resolver modelo antecipadamente
            resolved_model_path, auto_index_path, model_info = resolve_model_path(request.model_id)
            if not resolved_model_path:
                raise HTTPException(
                    status_code=404,
                    detail=f"Modelo não encontrado: {request.model_id}. Use /models para listar IDs e caminhos disponíveis."
                )
            
            # Se tts_voice não foi fornecido, usar do modelo
            if not tts_voice:
                if model_info and model_info.get("tts_voice"):
                    tts_voice = model_info.get("tts_voice")
                    print(f"📢 Usando tts_voice do modelo: {tts_voice}")
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"tts_voice não fornecido e modelo '{request.model_id}' não possui tts_voice configurado no models_config.json. Forneça tts_voice explicitamente."
                    )
        else:
            # Se não há model_id, tts_voice é obrigatório
            if not tts_voice:
                raise HTTPException(
                    status_code=400,
                    detail="tts_voice é obrigatório quando model_id não é fornecido"
                )
        
        # Validar voz TTS
        voices_data = load_tts_voices()
        voice_names = [v.get("ShortName", "") for v in voices_data]
        if tts_voice and tts_voice not in voice_names:
            raise HTTPException(
                status_code=404,
                detail=f"Voz TTS não encontrada: {tts_voice}. Use /voices para listar vozes disponíveis."
            )
        
        # Criar arquivos temporários
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Se não há modelo, gerar apenas TTS
        if not request.model_id or request.model_id.strip() == "":
            # Gerar apenas TTS sem RVC
            output_filename = f"tts_only_{timestamp}.{output_format.lower()}"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            
            # Ajustar caminho para WAV (TTS sempre gera WAV)
            tts_output_path = output_path.replace(f".{output_format.lower()}", ".wav")
            
            print(f"\n🎤 Gerando TTS apenas (sem RVC)...")
            print(f"   Texto: {cleaned_text[:50]}...")
            print(f"   Voz TTS: {tts_voice}")
            print(f"   Formato: {output_format}")
            
            # Gerar TTS
            try:
                message, output_file = run_tts_only_script(
                    tts_file="",
                    tts_text=cleaned_text,
                    tts_voice=tts_voice,
                    tts_rate=request.tts_rate,
                    output_path=tts_output_path,
                    export_format=output_format,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro ao gerar TTS: {str(e)}"
                )
            
            # Verificar se arquivo foi criado
            if not os.path.exists(output_file):
                raise HTTPException(
                    status_code=500,
                    detail="Erro ao gerar áudio: arquivo não foi criado"
                )
            
            # Converter formato se necessário (TTS sempre gera WAV)
            final_output = output_file
            if output_format.upper() != "WAV":
                # Por enquanto, retornamos WAV mesmo se outro formato foi solicitado
                # A conversão pode ser adicionada depois se necessário
                final_output = output_file
            
            # Obter informações do arquivo
            file_size = os.path.getsize(final_output)
            size_kb = file_size / 1024
            
            # Tentar obter duração
            duration_seconds = None
            try:
                import librosa
                duration_seconds = librosa.get_duration(path=final_output)
            except:
                pass
            
            # Converter para base64
            base64_audio = None
            with open(final_output, "rb") as audio_file:
                audio_bytes = audio_file.read()
                base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Limpar arquivo
            try:
                os.remove(final_output)
            except:
                pass
            
            return TTSInferenceResponse(
                success=True,
                message=message or "✅ Áudio TTS gerado com sucesso (sem RVC)",
                text=cleaned_text,
                tts_voice=tts_voice,
                model_path=None,
                index_path=None,
                output_file=None,
                output_path=None,
                base64=base64_audio,
                format="WAV",  # TTS sempre gera WAV
                size_kb=size_kb,
                duration_seconds=duration_seconds
            )
        
        else:
            # Usar valores já resolvidos anteriormente
            # Usar index_path auto-detectado (do config ou match_index)
            index_path = auto_index_path
            
            if index_path and not os.path.exists(index_path):
                raise HTTPException(
                    status_code=404,
                    detail=f"Arquivo index não encontrado: {index_path}"
                )
            
            # Usar o caminho resolvido
            actual_model_path = resolved_model_path
            
            # Gerar TTS + RVC
            tts_output_path = os.path.join(OUTPUT_DIR, f"tts_output_{timestamp}.wav")
            rvc_output_filename = f"tts_rvc_output_{timestamp}.{output_format.lower()}"
            rvc_output_path = os.path.join(OUTPUT_DIR, rvc_output_filename)
            
            config = Config()
            device_info = f" ({config.gpu_name})" if config.gpu_name else ""
            
            print(f"\n🎤 Gerando TTS + RVC...")
            print(f"   Device: {config.device}{device_info}")
            print(f"   Texto: {cleaned_text[:50]}...")
            print(f"   Voz TTS: {tts_voice}")
            print(f"   Modelo RVC: {actual_model_path}" + (f" (ID: {request.model_id})" if model_info else ""))
            print(f"   Index: {index_path}")
            print(f"   Formato: {output_format}")
            
            # Chamar função do Applio para TTS + RVC
            try:
                message, output_file = run_tts_script(
                    tts_file="",
                    tts_text=cleaned_text,
                    tts_voice=tts_voice,
                    tts_rate=request.tts_rate,
                    pitch=0,
                    index_rate=0.75,
                    volume_envelope=1.0,
                    protect=0.5,
                    f0_method="rmvpe",
                    output_tts_path=tts_output_path,
                    output_rvc_path=rvc_output_path,
                    pth_path=actual_model_path,
                    index_path=index_path or "",
                    split_audio=False,
                    f0_autotune=False,
                    f0_autotune_strength=1.0,
                    proposed_pitch=False,
                    proposed_pitch_threshold=155.0,
                    clean_audio=False,
                    clean_strength=0.5,
                    export_format=output_format,
                    embedder_model="contentvec",
                    embedder_model_custom=None,
                    sid=0,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro ao gerar TTS + RVC: {str(e)}"
                )
            
            # Verificar se arquivo foi criado
            if not os.path.exists(output_file):
                raise HTTPException(
                    status_code=500,
                    detail="Erro ao gerar áudio: arquivo não foi criado"
                )
            
            # Obter informações do arquivo
            file_size = os.path.getsize(output_file)
            size_kb = file_size / 1024
            
            # Tentar obter duração
            duration_seconds = None
            try:
                import librosa
                duration_seconds = librosa.get_duration(path=output_file)
            except:
                pass
            
            # Converter para base64
            base64_audio = None
            with open(output_file, "rb") as audio_file:
                audio_bytes = audio_file.read()
                base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Limpar arquivos
            try:
                os.remove(output_file)
                if os.path.exists(tts_output_path):
                    os.remove(tts_output_path)
            except:
                pass
            
            return TTSInferenceResponse(
                success=True,
                message=message or "✅ Áudio TTS + RVC gerado com sucesso",
                text=cleaned_text,
                tts_voice=tts_voice,
                model_path=actual_model_path,  # Retornar caminho resolvido
                index_path=index_path,
                output_file=None,
                output_path=None,
                base64=base64_audio,
                format=output_format.upper(),
                size_kb=size_kb,
                duration_seconds=duration_seconds
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro ao gerar áudio: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar áudio: {str(e)}"
        )


@app.post("/tts/generate", response_model=TTSInferenceResponse, tags=["TTS"])
async def tts_generate_simple(request: SimpleTTSRequest, _: bool = Depends(verify_api_key)):
    """
    Gera áudio TTS de forma simplificada - similar à interface do Applio
    
    Este endpoint é uma versão simplificada que usa valores padrão para os parâmetros avançados.
    Ideal para uso rápido e direto, similar à aba TTS do Applio.
    
    Parâmetros obrigatórios:
    - text: Texto para sintetizar
    - tts_voice: Voz TTS (use /voices para listar)
    - model_id: ID do modelo (ex: '16c19771-9ece-45fd-8ce5-53bb5263a63d') ou caminho completo (ex: 'logs/Lula/Lula.pth') - use /models para listar IDs e caminhos
    
    Parâmetros opcionais:
    - index_path: Auto-detectado se não fornecido
    - tts_rate: Velocidade TTS (-100 a 100, padrão: 0)
    - return_base64: Sempre true - sempre retorna base64 (padrão: true)
    - output_format: Formato de saída (WAV, MP3, FLAC, OGG, M4A). Padrão: OGG (otimizado para R2)
    
    Nota: Este endpoint sempre retorna o áudio em base64, ideal para conversão em .ogg e upload no R2.
    
    Args:
        request: SimpleTTSRequest com texto, voz TTS, modelo e index
    
    Returns:
        TTSInferenceResponse com informações do áudio gerado
    """
    # Limpar texto de caracteres de controle
    cleaned_text = clean_text(request.text)
    if not cleaned_text:
        raise HTTPException(
            status_code=400,
            detail="Texto inválido ou vazio após limpeza"
        )
    
    # Validar formato de saída
    valid_formats = ["WAV", "MP3", "FLAC", "OGG", "M4A"]
    output_format = request.output_format.upper()
    if output_format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Formato inválido: {output_format}. Formatos válidos: {', '.join(valid_formats)}"
        )
    
    # Converter SimpleTTSRequest para TTSInferenceRequest com valores padrão
    # Quando return_base64=true, sempre usar o formato especificado (padrão OGG para R2)
    full_request = TTSInferenceRequest(
        text=cleaned_text,  # Usar texto limpo
        tts_voice=request.tts_voice,
        model_id=request.model_id,
        tts_rate=request.tts_rate,
        pitch=0,
        index_rate=0.75,
        volume_envelope=1.0,
        protect=0.5,
        f0_method="rmvpe",
        split_audio=False,
        f0_autotune=False,
        f0_autotune_strength=1.0,
        proposed_pitch=False,
        proposed_pitch_threshold=155.0,
        clean_audio=False,
        clean_strength=0.5,
        export_format=output_format,  # Usar formato especificado (OGG para R2)
        embedder_model="contentvec",
        embedder_model_custom=None,
        sid=0,
        return_base64=True,  # Sempre true para /tts/generate - sempre retorna base64
        output_filename=None
    )
    
    return await tts_inference(full_request)


@app.post("/tts/inference", response_model=TTSInferenceResponse, tags=["TTS"])
async def tts_inference(request: TTSInferenceRequest, _: bool = Depends(verify_api_key)):
    """
    Gera áudio usando TTS + RVC (Voice Conversion) - Versão completa com todas as opções
    
    Este endpoint:
    1. Gera áudio TTS usando Edge TTS com a voz especificada
    2. Aplica Voice Conversion usando o modelo RVC especificado
    3. Retorna o áudio final
    
    Args:
        request: TTSInferenceRequest com texto, voz, modelo e parâmetros
    
    Returns:
        TTSInferenceResponse com informações do áudio gerado
    """
    try:
        # Resolver model_id (pode ser ID ou caminho completo)
        resolved_model_path, auto_index_path, model_info = resolve_model_path(request.model_id)
        
        if not resolved_model_path:
            raise HTTPException(
                status_code=404,
                detail=f"Modelo não encontrado: {request.model_id}. Use /models para listar IDs e caminhos disponíveis."
            )
        
        # Usar index_path auto-detectado (do config ou match_index)
        actual_index_path = auto_index_path
        
        if actual_index_path and not os.path.exists(actual_index_path):
            raise HTTPException(
                status_code=404,
                detail=f"Arquivo index não encontrado: {actual_index_path}"
            )
        
        # Usar o caminho resolvido
        actual_model_path = resolved_model_path
        
        # Validar voz TTS
        voices_data = load_tts_voices()
        voice_names = [v.get("ShortName", "") for v in voices_data]
        if request.tts_voice not in voice_names:
            raise HTTPException(
                status_code=404,
                detail=f"Voz TTS não encontrada: {request.tts_voice}. Use /voices para listar vozes disponíveis."
            )
        
        # Validar embedder custom se necessário
        if request.embedder_model == "custom" and not request.embedder_model_custom:
            raise HTTPException(
                status_code=400,
                detail="embedder_model_custom é obrigatório quando embedder_model='custom'"
            )
        
        # Criar arquivos temporários para TTS e RVC
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Arquivo TTS intermediário
        tts_output_path = os.path.join(
            OUTPUT_DIR,
            f"tts_output_{timestamp}.wav"
        )
        
        # Arquivo RVC final
        if request.output_filename:
            rvc_output_filename = request.output_filename
            if not rvc_output_filename.endswith(('.wav', '.mp3', '.flac', '.ogg', '.m4a')):
                rvc_output_filename += f".{request.export_format.lower()}"
        else:
            rvc_output_filename = f"tts_rvc_output_{timestamp}.{request.export_format.lower()}"
        
        rvc_output_path = os.path.join(OUTPUT_DIR, rvc_output_filename)
        
        # Arquivo de texto temporário (se necessário para run_tts_script)
        tts_file = ""  # Usaremos texto direto
        
        # Verificar device (GPU/CPU) sendo usado
        config = Config()
        device_info = f" ({config.gpu_name})" if config.gpu_name else ""
        
        print(f"\n🎤 Gerando TTS Inference...")
        print(f"   Device: {config.device}{device_info}")
        print(f"   Texto: {request.text[:50]}...")
        print(f"   Voz TTS: {request.tts_voice}")
        print(f"   Modelo RVC: {actual_model_path}" + (f" (ID: {request.model_id})" if model_info else ""))
        print(f"   Index: {actual_index_path}")
        
        # Chamar função do Applio
        try:
            message, output_file = run_tts_script(
                tts_file=tts_file,
                tts_text=request.text,
                tts_voice=request.tts_voice,
                tts_rate=request.tts_rate,
                pitch=request.pitch,
                index_rate=request.index_rate,
                volume_envelope=request.volume_envelope,
                protect=request.protect,
                f0_method=request.f0_method,
                output_tts_path=tts_output_path,
                output_rvc_path=rvc_output_path,
                pth_path=actual_model_path,
                index_path=actual_index_path or "",
                split_audio=request.split_audio,
                f0_autotune=request.f0_autotune,
                f0_autotune_strength=request.f0_autotune_strength,
                proposed_pitch=request.proposed_pitch,
                proposed_pitch_threshold=request.proposed_pitch_threshold,
                clean_audio=request.clean_audio,
                clean_strength=request.clean_strength,
                export_format=request.export_format,
                embedder_model=request.embedder_model,
                embedder_model_custom=request.embedder_model_custom,
                sid=request.sid,
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao gerar TTS: {str(e)}"
            )
        
        # Verificar se arquivo foi criado
        if not os.path.exists(output_file):
            raise HTTPException(
                status_code=500,
                detail="Erro ao gerar áudio: arquivo não foi criado"
            )
        
        # Obter informações do arquivo
        file_size = os.path.getsize(output_file)
        size_kb = file_size / 1024
        
        # Tentar obter duração (opcional)
        duration_seconds = None
        try:
            import librosa
            duration_seconds = librosa.get_duration(path=output_file)
        except:
            pass
        
        # Converter para base64 se solicitado
        base64_audio = None
        if request.return_base64:
            with open(output_file, "rb") as audio_file:
                audio_bytes = audio_file.read()
                base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Limpar arquivo se foi pedido base64
            try:
                os.remove(output_file)
                output_file = None
            except:
                pass
        
        # Limpar arquivo TTS intermediário
        try:
            if os.path.exists(tts_output_path):
                os.remove(tts_output_path)
        except:
            pass
        
        return TTSInferenceResponse(
            success=True,
            message=message or "✅ Áudio gerado com sucesso",
            text=request.text,
            tts_voice=request.tts_voice,
            model_path=actual_model_path,  # Retornar caminho resolvido
            index_path=actual_index_path,
            output_file=os.path.basename(output_file) if output_file else None,
            output_path=output_file if output_file and not request.return_base64 else None,
            base64=base64_audio,
            format=request.export_format.upper() if request.return_base64 else None,  # Formato do áudio em base64
            size_kb=size_kb,
            duration_seconds=duration_seconds
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro ao gerar TTS Inference: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar áudio: {str(e)}"
        )


@app.get("/tts/download/{filename}", tags=["TTS"])
async def download_audio(filename: str, _: bool = Depends(verify_api_key)):
    """
    Download de arquivo de áudio gerado
    
    Args:
        filename: Nome do arquivo para download
    
    Returns:
        Arquivo de áudio
    """
    file_path = OUTPUT_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Arquivo não encontrado: {filename}"
        )
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="audio/wav"
    )


@app.post("/transcribe", response_model=TranscribeResponse, tags=["Transcription"])
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = "pt",
    enable_diarization: bool = True,
    word_timestamps: bool = False,
    model_size: str = "turbo",
    _: bool = Depends(verify_api_key)
):
    """
    Transcrever áudio usando Whisper V3 Turbo com diarização Pyannote
    
    Este endpoint:
    1. Transcreve o áudio usando Whisper V3 Turbo (modelo mais moderno e rápido)
    2. Identifica diferentes speakers usando Pyannote diarization
    3. Combina transcrição com identificação de speakers
    
    Args:
        file: Arquivo de áudio para transcrever
        language: Idioma do áudio (pt, en, es, etc.) ou 'auto' para detecção
        enable_diarization: Ativar diarização para identificar speakers
        word_timestamps: Incluir timestamps por palavra
        model_size: Tamanho do modelo Whisper (turbo, large-v3, large, medium, small, base, tiny)
    
    Returns:
        TranscribeResponse com texto transcrito e segmentos por speaker
    """
    try:
        # Validar tipo de arquivo
        allowed_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm', '.mp4', '.aac'}
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de arquivo não suportado: {file_ext}. Use: {allowed_extensions}"
            )
        
        # Usar modelo Whisper já carregado (pré-carregado no startup)
        # Se o modelo solicitado for diferente do carregado, carregar o novo
        if model_size != "turbo" or not _WHISPER_READY:
            whisper_model = load_whisper_model(model_size)
        else:
            whisper_model = _whisper_model
        
        if not whisper_model or not _WHISPER_READY:
            raise HTTPException(
                status_code=503,
                detail="Whisper não está pronto. Verifique os logs."
            )
        
        # Salvar arquivo temporário
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_filename = f"upload_{timestamp}{file_ext}"
        temp_filepath = UPLOAD_DIR / temp_filename
        
        # Salvar conteúdo do arquivo
        with open(temp_filepath, "wb") as f:
            content = await file.read()
            f.write(content)
        
        print(f"\n📝 Transcrevendo áudio...")
        print(f"   Arquivo: {file.filename}")
        print(f"   Idioma: {language}")
        print(f"   Modelo: {model_size}")
        print(f"   Diarização: {enable_diarization}")
        
        # Transcrever áudio com Whisper
        result = whisper_model.transcribe(
            str(temp_filepath),
            language=language if language != "auto" else None,
            word_timestamps=word_timestamps,
            task="transcribe"
        )
        
        transcribed_text = result["text"].strip()
        detected_language = result.get("language", language)
        segments = result.get("segments", [])
        
        # Calcular duração
        duration = segments[-1]["end"] if segments else 0
        
        # Processar diarização se solicitado
        speaker_segments = None
        speakers_list = None
        
        if enable_diarization:
            try:
                # Usar pipeline já carregado (pré-carregado no startup)
                diarization_pipeline = _diarization_pipeline
                if not diarization_pipeline or not _DIARIZATION_READY:
                    # Tentar carregar se não estiver carregado
                    diarization_pipeline = load_diarization_pipeline()
                
                if diarization_pipeline and _DIARIZATION_READY:
                    print(f"   🎤 Aplicando diarização...")
                    
                    # Executar diarização
                    diarization = diarization_pipeline(str(temp_filepath))
                    
                    # Extrair speakers únicos
                    speakers_set = set()
                    for turn, _, speaker in diarization.itertracks(yield_label=True):
                        speakers_set.add(speaker)
                    speakers_list = sorted(list(speakers_set))
                    
                    # Combinar transcrição com diarização
                    speaker_segments = []
                    
                    # Criar dicionário de timestamps por segmento do Whisper
                    for segment in segments:
                        seg_start = segment["start"]
                        seg_end = segment["end"]
                        seg_text = segment["text"].strip()
                        
                        # Encontrar qual speaker está falando neste segmento
                        # Usar o speaker que tem mais overlap com o segmento
                        best_speaker = None
                        max_overlap = 0
                        
                        for turn, _, speaker in diarization.itertracks(yield_label=True):
                            # Calcular overlap entre segmento e turno do speaker
                            overlap_start = max(seg_start, turn.start)
                            overlap_end = min(seg_end, turn.end)
                            overlap = max(0, overlap_end - overlap_start)
                            
                            if overlap > max_overlap:
                                max_overlap = overlap
                                best_speaker = speaker
                        
                        # Se não encontrou speaker, usar o mais próximo
                        if best_speaker is None and speakers_list:
                            best_speaker = speakers_list[0]
                        
                        speaker_segments.append(SpeakerSegment(
                            speaker=best_speaker or "SPEAKER_00",
                            start=seg_start,
                            end=seg_end,
                            text=seg_text
                        ))
                    
                    print(f"   ✅ Diarização concluída: {len(speakers_list)} speaker(s) identificado(s)")
                else:
                    print(f"   ⚠️ Diarização não disponível (token não configurado ou erro)")
            except Exception as e:
                print(f"   ⚠️ Erro na diarização: {e}")
                # Continuar sem diarização
        
        # Limpar arquivo temporário
        try:
            if temp_filepath.exists():
                temp_filepath.unlink()
        except:
            pass
        
        # Processar word timestamps se solicitado
        word_timestamps_list = None
        if word_timestamps and segments:
            word_timestamps_list = []
            for segment in segments:
                words = segment.get("words", [])
                for word_info in words:
                    word_timestamps_list.append({
                        "word": word_info.get("word", ""),
                        "start": word_info.get("start", 0),
                        "end": word_info.get("end", 0),
                        "probability": word_info.get("probability", 0)
                    })
        
        return TranscribeResponse(
            success=True,
            message="✅ Áudio transcrito com sucesso" + (" (com diarização)" if enable_diarization and speaker_segments else ""),
            text=transcribed_text,
            language=detected_language,
            duration=round(duration, 2),
            segments=speaker_segments,
            speakers=speakers_list,
            word_timestamps=word_timestamps_list
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro ao transcrever áudio: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao transcrever áudio: {str(e)}"
        )


class MergeAudioRequest(BaseModel):
    """Request model para mesclar TTS do título com áudio do usuário"""
    title_text: str = Field(..., description="Texto do título para gerar TTS (ex: 'Mateuus mandou R$ 10,00')", min_length=1, max_length=200)
    tts_voice: Optional[str] = Field(None, description="Voz TTS (Edge TTS) - ShortName da voz (ex: pt-BR-AntonioNeural). Obrigatório se model_id não for fornecido. Se model_id for fornecido e tts_voice não for especificado, será usado o tts_voice do modelo no config")
    model_id: Optional[str] = Field(None, description="ID do modelo (ex: '16c19771-9ece-45fd-8ce5-53bb5263a63d') ou caminho completo (ex: 'logs/Lula/Lula.pth'). Se fornecido, usa TTS + RVC. Se não fornecido, usa apenas TTS. Use /models para listar IDs e caminhos disponíveis")
    user_audio_base64: str = Field(..., description="Áudio do usuário em base64")
    output_format: str = Field("OGG", description="Formato de saída (WAV, MP3, FLAC, OGG, M4A). Padrão: OGG")


class MergeAudioResponse(BaseModel):
    """Response model para áudio mesclado"""
    success: bool
    message: str
    base64: str  # Áudio mesclado em base64
    format: str  # Formato do áudio (OGG, WAV, etc)
    duration_seconds: float  # Duração total do áudio mesclado em segundos
    size_kb: float  # Tamanho do áudio em KB


@app.post("/merge-audio", response_model=MergeAudioResponse, tags=["TTS"])
async def merge_audio_with_title(
    request: MergeAudioRequest,
    _: bool = Depends(verify_api_key)
):
    """
    Mescla TTS do título com áudio do usuário
    
    Este endpoint:
    1. Gera TTS do título usando Edge TTS (ou TTS + RVC se model_id fornecido)
    2. Decodifica o áudio do usuário (base64)
    3. Mescla os dois áudios (concatena)
    4. Retorna o áudio mesclado em base64 com duração
    
    Parâmetros:
    - title_text: Texto do título para gerar TTS
    - tts_voice: Voz TTS (Edge TTS) - Obrigatório se model_id não for fornecido
    - model_id: ID do modelo RVC (opcional) - Se fornecido, usa TTS + RVC ao invés de apenas TTS
    - user_audio_base64: Áudio do usuário em base64
    - output_format: Formato de saída (padrão: OGG)
    
    Args:
        request: MergeAudioRequest com título, voz TTS (opcional), model_id (opcional) e áudio do usuário
    
    Returns:
        MergeAudioResponse com áudio mesclado em base64 e duração
    """
    try:
        import librosa
        import soundfile as sf
        import numpy as np
        
        # Limpar texto do título
        cleaned_title = clean_text(request.title_text)
        if not cleaned_title:
            raise HTTPException(
                status_code=400,
                detail="Texto do título inválido ou vazio após limpeza"
            )
        
        # Validar formato de saída
        valid_formats = ["WAV", "MP3", "FLAC", "OGG", "M4A"]
        output_format = request.output_format.upper()
        if output_format not in valid_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Formato inválido: {output_format}. Formatos válidos: {', '.join(valid_formats)}"
            )
        
        # Determinar tts_voice e resolver model_id se fornecido
        tts_voice = request.tts_voice
        resolved_model_path = None
        auto_index_path = None
        model_info = None
        
        if request.model_id and request.model_id.strip():
            # Resolver modelo antecipadamente
            resolved_model_path, auto_index_path, model_info = resolve_model_path(request.model_id)
            if not resolved_model_path:
                raise HTTPException(
                    status_code=404,
                    detail=f"Modelo não encontrado: {request.model_id}. Use /models para listar IDs e caminhos disponíveis."
                )
            
            # Se tts_voice não foi fornecido, usar do modelo
            if not tts_voice:
                if model_info and model_info.get("tts_voice"):
                    tts_voice = model_info.get("tts_voice")
                    print(f"📢 Usando tts_voice do modelo: {tts_voice}")
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"tts_voice não fornecido e modelo '{request.model_id}' não possui tts_voice configurado no models_config.json. Forneça tts_voice explicitamente."
                    )
        else:
            # Se não há model_id, tts_voice é obrigatório
            if not tts_voice:
                raise HTTPException(
                    status_code=400,
                    detail="tts_voice é obrigatório quando model_id não é fornecido"
                )
        
        # Validar voz TTS
        voices_data = load_tts_voices()
        voice_names = [v.get("ShortName", "") for v in voices_data]
        if tts_voice and tts_voice not in voice_names:
            raise HTTPException(
                status_code=404,
                detail=f"Voz TTS não encontrada: {tts_voice}. Use /voices para listar vozes disponíveis."
            )
        
        print(f"\n🎤 Mesclando áudio com título...")
        print(f"   Título: {cleaned_title}")
        print(f"   Voz TTS: {tts_voice}")
        if resolved_model_path:
            print(f"   Modelo RVC: {resolved_model_path}" + (f" (ID: {request.model_id})" if model_info else ""))
        print(f"   Formato: {output_format}")
        
        # 1. Gerar TTS do título (com ou sem RVC)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tts_output_path = os.path.join(OUTPUT_DIR, f"tts_title_{timestamp}.wav")
        
        try:
            if resolved_model_path:
                # Usar TTS + RVC
                index_path = auto_index_path
                if index_path and not os.path.exists(index_path):
                    raise HTTPException(
                        status_code=404,
                        detail=f"Arquivo index não encontrado: {index_path}"
                    )
                
                rvc_output_path = os.path.join(OUTPUT_DIR, f"tts_rvc_title_{timestamp}.wav")
                
                message, tts_file = run_tts_script(
                    tts_file="",
                    tts_text=cleaned_title,
                    tts_voice=tts_voice,
                    tts_rate=0,
                    pitch=0,
                    index_rate=0.75,
                    volume_envelope=1.0,
                    protect=0.5,
                    f0_method="rmvpe",
                    output_tts_path=tts_output_path,
                    output_rvc_path=rvc_output_path,
                    pth_path=resolved_model_path,
                    index_path=index_path or "",
                    split_audio=False,
                    f0_autotune=False,
                    f0_autotune_strength=1.0,
                    proposed_pitch=False,
                    proposed_pitch_threshold=155.0,
                    clean_audio=False,
                    clean_strength=0.5,
                    export_format="WAV",
                    embedder_model="contentvec",
                    embedder_model_custom=None,
                    sid=0,
                )
                # Usar o arquivo RVC gerado
                tts_output_path = rvc_output_path
            else:
                # Usar apenas TTS (sem RVC)
                message, tts_file = run_tts_only_script(
                    tts_file="",
                    tts_text=cleaned_title,
                    tts_voice=tts_voice,
                    tts_rate=0,
                    output_path=tts_output_path,
                    export_format="WAV",
                )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao gerar TTS do título: {str(e)}"
            )
        
        if not os.path.exists(tts_output_path):
            raise HTTPException(
                status_code=500,
                detail="Erro ao gerar TTS: arquivo não foi criado"
            )
        
        # 2. Decodificar áudio do usuário (base64)
        try:
            user_audio_bytes = base64.b64decode(request.user_audio_base64)
            user_audio_temp = os.path.join(UPLOAD_DIR, f"user_audio_{timestamp}.tmp")
            with open(user_audio_temp, "wb") as f:
                f.write(user_audio_bytes)
        except Exception as e:
            # Limpar arquivo TTS se houver erro
            try:
                if os.path.exists(tts_output_path):
                    os.remove(tts_output_path)
            except:
                pass
            raise HTTPException(
                status_code=400,
                detail=f"Erro ao decodificar áudio do usuário: {str(e)}"
            )
        
        # 3. Carregar ambos os áudios usando librosa (normaliza sample rate)
        try:
            # Carregar TTS do título
            title_audio, title_sr = librosa.load(tts_output_path, sr=None)
            
            # Carregar áudio do usuário
            user_audio, user_sr = librosa.load(user_audio_temp, sr=None)
            
            # Normalizar ambos para o mesmo sample rate (usar o maior)
            target_sr = max(title_sr, user_sr)
            if title_sr != target_sr:
                title_audio = librosa.resample(title_audio, orig_sr=title_sr, target_sr=target_sr)
            if user_sr != target_sr:
                user_audio = librosa.resample(user_audio, orig_sr=user_sr, target_sr=target_sr)
            
            # 4. Mesclar (concatenar) os áudios
            merged_audio = np.concatenate([title_audio, user_audio])
            
            # 5. Salvar áudio mesclado
            merged_output_path = os.path.join(OUTPUT_DIR, f"merged_{timestamp}.{output_format.lower()}")
            
            # Converter formato se necessário (soundfile suporta WAV, FLAC, OGG)
            if output_format.upper() in ["WAV", "FLAC", "OGG"]:
                sf.write(merged_output_path, merged_audio, target_sr, format=output_format.upper())
            else:
                # Para MP3 e M4A, salvar como WAV primeiro e converter depois se necessário
                # Por enquanto, vamos usar OGG como padrão para compatibilidade
                sf.write(merged_output_path, merged_audio, target_sr, format="OGG")
                output_format = "OGG"
            
            # 6. Obter duração e tamanho
            duration_seconds = len(merged_audio) / target_sr
            file_size = os.path.getsize(merged_output_path)
            size_kb = file_size / 1024
            
            # 7. Converter para base64
            with open(merged_output_path, "rb") as f:
                merged_audio_bytes = f.read()
                merged_base64 = base64.b64encode(merged_audio_bytes).decode('utf-8')
            
            # 8. Limpar arquivos temporários
            try:
                # Remove arquivo TTS (pode ser TTS apenas ou RVC)
                if os.path.exists(tts_output_path):
                    os.remove(tts_output_path)
                # Remove arquivo TTS intermediário se foi gerado RVC
                if resolved_model_path:
                    tts_intermediate = os.path.join(OUTPUT_DIR, f"tts_title_{timestamp}.wav")
                    if os.path.exists(tts_intermediate):
                        os.remove(tts_intermediate)
                os.remove(user_audio_temp)
                os.remove(merged_output_path)
            except:
                pass
            
            print(f"   ✅ Áudio mesclado com sucesso!")
            print(f"   Duração total: {duration_seconds:.2f}s")
            
            return MergeAudioResponse(
                success=True,
                message="✅ Áudio mesclado com sucesso",
                base64=merged_base64,
                format=output_format.upper(),
                duration_seconds=round(duration_seconds, 2),
                size_kb=round(size_kb, 2)
            )
            
        except Exception as e:
            # Limpar arquivos em caso de erro
            files_to_clean = [tts_output_path, user_audio_temp]
            if resolved_model_path:
                # Adicionar arquivo TTS intermediário se foi gerado RVC
                tts_intermediate = os.path.join(OUTPUT_DIR, f"tts_title_{timestamp}.wav")
                files_to_clean.append(tts_intermediate)
            for file_path in files_to_clean:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao mesclar áudios: {str(e)}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro ao mesclar áudio: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao mesclar áudio: {str(e)}"
        )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Applio TTS Inference API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host para bind")
    parser.add_argument("--port", type=int, default=8000, help="Porta para bind")
    parser.add_argument("--reload", action="store_true", help="Ativar auto-reload")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "api.app:app",  # Corrigido: usar api.app já que o arquivo está em api/app.py
        host=args.host,
        port=args.port,
        reload=args.reload
    )

