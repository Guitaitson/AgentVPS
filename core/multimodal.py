"""
Multi-modal Capabilities - Sprint 4

Capacidades de visão e áudio para o agente.
Permite processar imagens e áudio enviados pelo Telegram.
"""

import base64
import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import httpx
from PIL import Image


@dataclass
class ImageAnalysis:
    """Resultado da análise de imagem."""
    description: str
    format: str
    size: tuple[int, int]
    mode: str
    has_transparency: bool


class VisionCapabilities:
    """
    Capacidades de visão para processar imagens.
    Usa modelos locais ou APIs para análise visual.
    """

    def __init__(self):
        self.supported_formats = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

    def is_supported_image(self, file_path: str) -> bool:
        """Verifica se o formato é suportado."""
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_formats

    def analyze_image(self, image_data: bytes) -> ImageAnalysis:
        """
        Analisa uma imagem e retorna informações.
        
        Args:
            image_data: Bytes da imagem
            
        Returns:
            ImageAnalysis com detalhes da imagem
        """
        image = Image.open(io.BytesIO(image_data))

        return ImageAnalysis(
            description=self._generate_description(image),
            format=image.format or "UNKNOWN",
            size=image.size,
            mode=image.mode,
            has_transparency=image.mode in ("RGBA", "LA") or (
                image.mode == "P" and "transparency" in image.info
            )
        )

    def _generate_description(self, image: Image.Image) -> str:
        """Gera uma descrição básica da imagem."""
        width, height = image.size
        total_pixels = width * height

        # Classificação por resolução
        if total_pixels > 4000 * 3000:
            resolution = "muito alta"
        elif total_pixels > 2000 * 1500:
            resolution = "alta"
        elif total_pixels > 1000 * 750:
            resolution = "média"
        else:
            resolution = "baixa"

        return (
            f"Imagem {resolution} ({width}x{height} pixels), "
            f"modo {image.mode}, formato {image.format or 'desconhecido'}"
        )

    async def describe_with_vision_api(
        self,
        image_data: bytes,
        prompt: str = "Descreva esta imagem em detalhes"
    ) -> str:
        """
        Usa API de visão (GPT-4V, Claude Vision, etc) para descrever imagem.
        
        Args:
            image_data: Bytes da imagem
            prompt: Prompt para a API de visão
            
        Returns:
            Descrição gerada pela API
        """
        # Codifica imagem em base64
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        # Aqui você pode integrar com:
        # - OpenAI GPT-4 Vision
        # - Anthropic Claude Vision
        # - Google Gemini Vision
        # - Modelo local (LLaVA, etc)

        # Por enquanto, retorna análise local
        analysis = self.analyze_image(image_data)
        return f"Análise local: {analysis.description}"

    def extract_text_from_image(self, image_data: bytes) -> str:
        """
        Extrai texto de imagem (OCR).
        Requer pytesseract ou API de OCR.
        """
        # Implementação básica - pode ser extendida com:
        # - pytesseract (OCR local)
        # - Google Cloud Vision API
        # - AWS Textract
        # - Azure Computer Vision

        try:
            image = Image.open(io.BytesIO(image_data))

            # Verifica se tem pytesseract
            try:
                import pytesseract
                text = pytesseract.image_to_string(image, lang="por+eng")
                return text.strip() if text.strip() else "Nenhum texto encontrado"
            except ImportError:
                return "OCR não disponível (pytesseract não instalado)"
        except Exception as e:
            return f"Erro ao extrair texto: {str(e)}"

    def save_uploaded_file(self, file_data: bytes, filename: str) -> str:
        """
        Salva arquivo de upload temporariamente.
        
        Args:
            file_data: Bytes do arquivo
            filename: Nome original do arquivo
            
        Returns:
            Caminho do arquivo salvo
        """
        temp_dir = tempfile.gettempdir()
        save_path = os.path.join(temp_dir, f"vps_agent_{filename}")

        with open(save_path, "wb") as f:
            f.write(file_data)

        return save_path


class AudioCapabilities:
    """
    Capacidades de áudio para processar mensagens de voz e áudio.
    """

    def __init__(self):
        self.supported_formats = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}

    def is_supported_audio(self, file_path: str) -> bool:
        """Verifica se o formato é suportado."""
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_formats

    async def transcribe_audio(
        self,
        audio_data: bytes,
        language: str = "pt-BR"
    ) -> str:
        """
        Transcreve áudio para texto.
        
        Args:
            audio_data: Bytes do áudio
            language: Código do idioma (padrão: pt-BR)
            
        Returns:
            Transcrição do áudio
        """
        # Aqui você pode integrar com:
        # - Whisper (OpenAI)
        # - Whisper local
        # - Google Cloud Speech-to-Text
        # - AssemblyAI

        # Por enquanto, retorna mensagem informativa
        return (
            "Transcrição de áudio não disponível. "
            "Configure uma API de speech-to-text (Whisper, Google Cloud, etc) "
            "para habilitar esta funcionalidade."
        )

    def get_audio_info(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Retorna informações sobre o áudio.
        
        Args:
            audio_data: Bytes do áudio
            
        Returns:
            Dicionário com informações do áudio
        """
        # Implementação básica
        return {
            "size_bytes": len(audio_data),
            "size_kb": round(len(audio_data) / 1024, 2),
            "supported": True,
            "message": "Informações básicas disponíveis. "
                      "Para metadados detalhados, configure pydub ou librosa."
        }


class DocumentCapabilities:
    """
    Capacidades para processar documentos (PDF, DOCX, etc).
    """

    def __init__(self):
        self.supported_formats = {".pdf", ".docx", ".doc", ".txt", ".md"}

    def is_supported_document(self, file_path: str) -> bool:
        """Verifica se o formato é suportado."""
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_formats

    def extract_text_from_pdf(self, pdf_data: bytes) -> str:
        """
        Extrai texto de PDF.
        
        Args:
            pdf_data: Bytes do PDF
            
        Returns:
            Texto extraído
        """
        try:
            # Tenta usar PyPDF2
            try:
                from io import BytesIO

                import PyPDF2

                reader = PyPDF2.PdfReader(BytesIO(pdf_data))
                text = ""

                for page in reader.pages:
                    text += page.extract_text() + "\n"

                return text.strip() if text.strip() else "Nenhum texto encontrado"
            except ImportError:
                return "Extração de PDF não disponível (PyPDF2 não instalado)"
        except Exception as e:
            return f"Erro ao extrair texto do PDF: {str(e)}"

    def extract_text_from_docx(self, docx_data: bytes) -> str:
        """
        Extrai texto de DOCX.
        
        Args:
            docx_data: Bytes do DOCX
            
        Returns:
            Texto extraído
        """
        try:
            try:
                from io import BytesIO

                import docx

                doc = docx.Document(BytesIO(docx_data))
                text = "\n".join([para.text for para in doc.paragraphs])

                return text.strip() if text.strip() else "Nenhum texto encontrado"
            except ImportError:
                return "Extração de DOCX não disponível (python-docx não instalado)"
        except Exception as e:
            return f"Erro ao extrair texto do DOCX: {str(e)}"

    def read_plain_text(self, text_data: bytes) -> str:
        """
        Lê texto plano.
        
        Args:
            text_data: Bytes do texto
            
        Returns:
            Conteúdo do texto
        """
        try:
            return text_data.decode("utf-8")
        except UnicodeDecodeError:
            return text_data.decode("latin-1")


# Instâncias globais
vision = VisionCapabilities()
audio = AudioCapabilities()
document = DocumentCapabilities()


# ============================================
# Integração com Telegram Bot
# ============================================

async def handle_photo(update, bot) -> str:
    """
    Processa foto enviada pelo usuário.
    
    Args:
        update: Update do Telegram
        bot: Instância do bot
        
    Returns:
        Resposta para o usuário
    """
    photo = update.message.photo[-1]  # Maior resolução
    file = await bot.get_file(photo.file_id)

    # Baixa a foto
    async with httpx.AsyncClient() as client:
        response = await client.get(file.file_path)
        image_data = response.content

    # Analisa a imagem
    analysis = vision.analyze_image(image_data)

    return (
        f"📷 **Foto Recebida**\n\n"
        f"{analysis.description}\n\n"
        f"Para análise com IA avançada, configure uma API de visão."
    )


async def handle_voice(update, bot) -> str:
    """
    Processa mensagem de voz enviada pelo usuário.
    
    Args:
        update: Update do Telegram
        bot: Instância do bot
        
    Returns:
        Resposta para o usuário
    """
    voice = update.message.voice
    file = await bot.get_file(voice.file_id)

    # Baixa o áudio
    async with httpx.AsyncClient() as client:
        response = await client.get(file.file_path)
        audio_data = response.content

    # Transcreve
    transcription = await audio.transcribe_audio(audio_data)

    return (
        f"🎤 **Mensagem de Voz**\n\n"
        f"{transcription}"
    )


async def handle_document(update, bot) -> str:
    """
    Processa documento enviado pelo usuário.
    
    Args:
        update: Update do Telegram
        bot: Instância do bot
        
    Returns:
        Resposta para o usuário
    """
    document_msg = update.message.document
    file = await bot.get_file(document_msg.file_id)

    # Baixa o documento
    async with httpx.AsyncClient() as client:
        response = await client.get(file.file_path)
        file_data = response.content

    filename = document_msg.file_name or "documento"
    ext = Path(filename).suffix.lower()

    # Extrai texto baseado no tipo
    if ext == ".pdf":
        text = document.extract_text_from_pdf(file_data)
    elif ext in {".docx", ".doc"}:
        text = document.extract_text_from_docx(file_data)
    elif ext in {".txt", ".md"}:
        text = document.read_plain_text(file_data)
    else:
        text = "Formato de documento não suportado para extração de texto."

    # Limita tamanho da resposta
    if len(text) > 1000:
        text = text[:1000] + "..."

    return (
        f"📄 **Documento: {filename}**\n\n"
        f"{text}"
    )


__all__ = [
    "VisionCapabilities",
    "AudioCapabilities",
    "DocumentCapabilities",
    "vision",
    "audio",
    "document",
    "handle_photo",
    "handle_voice",
    "handle_document",
]
