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
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import uvicorn

# Adicionar paths necessários
# Obter diretório raiz do Applio (um nível acima de api/)
now_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Mudar para o diretório raiz para que os caminhos relativos funcionem
os.chdir(now_dir)
sys.path.insert(0, now_dir)

# Importar funções do Applio
from core import run_tts_script, load_voices_data
from tabs.inference.inference import get_files, match_index, get_speakers_id
from rvc.configs.config import Config, get_gpu_info
import torch

# Configurações
OUTPUT_DIR = Path(now_dir) / "assets" / "audios"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Variáveis globais
_voices_data = None


def load_tts_voices():
    """Carrega dados das vozes TTS"""
    global _voices_data
    if _voices_data is None:
        _voices_data = load_voices_data()
    return _voices_data


# Lifespan event handler
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Gerencia o ciclo de vida da aplicação"""
    print("\n🔄 Inicializando API do Applio...")
    load_tts_voices()
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


class SimpleTTSRequest(BaseModel):
    """Request model simplificado para TTS - similar à interface do Applio"""
    text: str = Field(..., description="Texto para sintetizar", min_length=1, max_length=5000)
    tts_voice: str = Field(..., description="Voz TTS (Edge TTS) - ShortName da voz (ex: pt-BR-FranciscaNeural)")
    model_path: str = Field(..., description="Caminho do modelo RVC (.pth) - ex: logs/Lula/Lula.pth")
    index_path: Optional[str] = Field(None, description="Caminho do arquivo index (.index). Se não fornecido, será auto-detectado")
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
    model_path: str = Field(..., description="Caminho do modelo RVC (.pth)")
    index_path: Optional[str] = Field(None, description="Caminho do arquivo index (.index). Se não fornecido, será auto-detectado")
    
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
    model_path: str
    index_path: Optional[str]
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
    path: str
    name: str
    index_path: Optional[str] = None


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
async def list_voices(language: Optional[str] = None):
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
async def list_models():
    """
    Lista todos os modelos RVC disponíveis
    
    Returns:
        Lista de modelos RVC com seus respectivos index files
    """
    try:
        models = get_files("model")
        indexes = get_files("index")
        
        models_list = []
        for model_path in models:
            # Tentar encontrar index correspondente
            index_path = match_index(model_path)
            
            models_list.append(ModelInfo(
                path=model_path,
                name=os.path.basename(model_path),
                index_path=index_path
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
async def get_model_index(model_path: str):
    """
    Obtém o arquivo index correspondente a um modelo RVC
    
    Args:
        model_path: Caminho do modelo RVC (ex: logs/Lula/Lula.pth)
    
    Returns:
        Caminho do arquivo index correspondente
    """
    try:
        if not os.path.exists(model_path):
            raise HTTPException(
                status_code=404,
                detail=f"Modelo não encontrado: {model_path}"
            )
        
        index_path = match_index(model_path)
        
        return ModelIndexResponse(
            success=True,
            model_path=model_path,
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
async def get_model_speakers(model_path: str):
    """
    Obtém os Speaker IDs disponíveis para um modelo RVC
    
    Args:
        model_path: Caminho do modelo RVC (ex: logs/Lula/Lula.pth)
    
    Returns:
        Lista de Speaker IDs disponíveis
    """
    try:
        if not os.path.exists(model_path):
            raise HTTPException(
                status_code=404,
                detail=f"Modelo não encontrado: {model_path}"
            )
        
        speaker_ids = get_speakers_id(model_path)
        
        return SpeakerIDsResponse(
            success=True,
            model_path=model_path,
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


@app.post("/tts/generate", response_model=TTSInferenceResponse, tags=["TTS"])
async def tts_generate_simple(request: SimpleTTSRequest):
    """
    Gera áudio TTS de forma simplificada - similar à interface do Applio
    
    Este endpoint é uma versão simplificada que usa valores padrão para os parâmetros avançados.
    Ideal para uso rápido e direto, similar à aba TTS do Applio.
    
    Parâmetros obrigatórios:
    - text: Texto para sintetizar
    - tts_voice: Voz TTS (use /voices para listar)
    - model_path: Caminho do modelo RVC (use /models para listar)
    
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
        model_path=request.model_path,
        index_path=request.index_path,
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
async def tts_inference(request: TTSInferenceRequest):
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
        # Validar modelo
        if not os.path.exists(request.model_path):
            raise HTTPException(
                status_code=404,
                detail=f"Modelo não encontrado: {request.model_path}"
            )
        
        # Validar ou auto-detectar index
        if not request.index_path:
            request.index_path = match_index(request.model_path)
        
        if request.index_path and not os.path.exists(request.index_path):
            raise HTTPException(
                status_code=404,
                detail=f"Arquivo index não encontrado: {request.index_path}"
            )
        
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
        print(f"   Modelo RVC: {request.model_path}")
        print(f"   Index: {request.index_path}")
        
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
                pth_path=request.model_path,
                index_path=request.index_path or "",
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
            model_path=request.model_path,
            index_path=request.index_path,
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
async def download_audio(filename: str):
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


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Applio TTS Inference API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host para bind")
    parser.add_argument("--port", type=int, default=8000, help="Porta para bind")
    parser.add_argument("--reload", action="store_true", help="Ativar auto-reload")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )

