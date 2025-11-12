#!/usr/bin/env python3
"""
Configurações da API Applio TTS Inference
Carrega variáveis de ambiente e configurações
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da API usando Pydantic Settings"""
    
    # ============================================
    # API Settings
    # ============================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_TITLE: str = "🎤 Applio TTS Inference API"
    API_VERSION: str = "1.0.0"
    API_KEY: Optional[str] = None  # API key para autenticação (Bearer token)
    
    # ============================================
    # Whisper (Transcription)
    # ============================================
    WHISPER_MODEL_SIZE: str = "turbo"  # turbo, large-v3, large, medium, small, base, tiny
    WHISPER_PRELOAD: bool = True  # Pré-carregar Whisper no startup
    
    # ============================================
    # Pyannote (Diarization)
    # ============================================
    # Token do Hugging Face para acessar modelos Pyannote
    # Obtenha em: https://huggingface.co/settings/tokens
    # Aceite os termos em: https://huggingface.co/pyannote/speaker-diarization-3.1
    PYANNOTE_TOKEN: Optional[str] = None
    PYANNOTE_PRELOAD: bool = True  # Pré-carregar diarização no startup (só se token configurado)
    PYANNOTE_MODEL: str = "pyannote/speaker-diarization-3.1"
    
    # ============================================
    # Outros Tokens (Opcional)
    # ============================================
    # Adicione aqui outros tokens conforme necessário
    # Exemplo:
    # OPENAI_API_KEY: Optional[str] = None
    # ELEVENLABS_API_KEY: Optional[str] = None
    
    # ============================================
    # Paths
    # ============================================
    OUTPUT_DIR: Optional[str] = None  # Diretório para salvar áudios gerados
    UPLOAD_DIR: Optional[str] = None  # Diretório para uploads temporários
    
    # ============================================
    # GPU Settings
    # ============================================
    CUDA_VISIBLE_DEVICES: Optional[str] = None  # Controlar quais GPUs usar
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignorar variáveis extras no .env
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Resolver paths relativos ao diretório raiz do Applio
        if self.OUTPUT_DIR is None:
            # Um nível acima de api/ (diretório raiz do Applio)
            root_dir = Path(__file__).parent.parent
            self.OUTPUT_DIR = str(root_dir / "assets" / "audios")
        if self.UPLOAD_DIR is None:
            root_dir = Path(__file__).parent.parent
            self.UPLOAD_DIR = str(root_dir / "assets" / "uploads")
    
    @property
    def has_pyannote_token(self) -> bool:
        """Verifica se o token do Pyannote está configurado"""
        return self.PYANNOTE_TOKEN is not None and self.PYANNOTE_TOKEN.strip() != ""
    
    @property
    def should_preload_diarization(self) -> bool:
        """Verifica se deve pré-carregar diarização"""
        return self.PYANNOTE_PRELOAD and self.has_pyannote_token
    
    @property
    def has_api_key(self) -> bool:
        """Verifica se a API key está configurada"""
        return self.API_KEY is not None and self.API_KEY.strip() != ""


# Instância global de configurações
settings = Settings()


def print_config_summary():
    """Imprime resumo das configurações (sem tokens sensíveis)"""
    print("\n📋 Configurações da API:")
    print(f"   Host: {settings.API_HOST}")
    print(f"   Port: {settings.API_PORT}")
    print(f"   Whisper Model: {settings.WHISPER_MODEL_SIZE}")
    print(f"   Whisper Preload: {settings.WHISPER_PRELOAD}")
    print(f"   Pyannote Token: {'✅ Configurado' if settings.has_pyannote_token else '❌ Não configurado (configure PYANNOTE_TOKEN no .env)'}")
    print(f"   Pyannote Preload: {settings.should_preload_diarization}")
    print(f"   API Key: {'✅ Configurado' if settings.has_api_key else '❌ Não configurado (API pública)'}")
    print(f"   Output Dir: {settings.OUTPUT_DIR}")
    print(f"   Upload Dir: {settings.UPLOAD_DIR}")
    print()
    if not settings.has_pyannote_token:
        print("💡 Dica: Para usar diarização, configure PYANNOTE_TOKEN no arquivo .env")
        print("   Veja api/.env.example para mais detalhes\n")

