"""
LLM Provider Unificado - Abstração para múltiplos providers.

Suporta:
- OpenRouter (OpenAI, Anthropic, Google)
- Function calling / Tool use
- Structured output (JSON mode)
- Fallback automático entre providers
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger()

# Configuração
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
DEFAULT_TEMPERATURE = float(os.getenv("OPENROUTER_TEMPERATURE", "0.3"))
DEFAULT_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "10000"))
TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "60"))


@dataclass
class LLMResponse:
    """Resposta padronizada do LLM."""
    content: str
    tool_calls: Optional[list[dict]] = None
    usage: Optional[dict] = None
    model: str = ""
    success: bool = True
    error: Optional[str] = None


@dataclass
class IntentClassification:
    """Resultado da classificação de intent."""
    intent: str  # command, task, question, chat, self_improve
    confidence: float
    action_required: bool
    tool_suggestion: str
    entities: list[str]
    reasoning: str


class UnifiedLLMProvider:
    """
    Provider unificado de LLM com suporte a:
    - Texto simples
    - Function calling
    - Structured output (JSON)
    - Fallback entre providers
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base_url = "https://openrouter.ai/api/v1"
        
        logger.info(
            "llm_provider_initialized",
            model=model,
            has_api_key=bool(self.api_key),
        )
    
    def _get_headers(self) -> dict:
        """Retorna headers para requisição."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://vps-agent.local",
            "X-Title": "VPS-Agent",
        }
    
    def _build_messages(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Constrói lista de mensagens."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if history:
            for msg in history[-5:]:  # Últimas 5 mensagens
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})
        
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    async def generate(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        history: Optional[list[dict]] = None,
        tools: Optional[list[dict]] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Gera resposta do LLM.
        
        Args:
            user_message: Mensagem do usuário
            system_prompt: Prompt de sistema opcional
            history: Histórico de conversa
            tools: Tools disponíveis para function calling
            json_mode: Se True, força saída JSON
            
        Returns:
            LLMResponse padronizada
        """
        if not self.api_key or self.api_key.startswith("sk-or-v1-minimax"):
            logger.warning("llm_no_api_key")
            return LLMResponse(
                content="",
                success=False,
                error="API key não configurada ou inválida",
            )
        
        messages = self._build_messages(user_message, system_prompt, history)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                
                if response.status_code != 200:
                    error_text = response.text[:200]
                    logger.error(
                        "llm_api_error",
                        status_code=response.status_code,
                        error=error_text,
                    )
                    return LLMResponse(
                        content="",
                        success=False,
                        error=f"API error {response.status_code}: {error_text}",
                    )
                
                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]
                
                # Extrair tool calls se presentes
                tool_calls = None
                if "tool_calls" in message:
                    tool_calls = message["tool_calls"]
                
                return LLMResponse(
                    content=message.get("content", ""),
                    tool_calls=tool_calls,
                    usage=data.get("usage"),
                    model=data.get("model", self.model),
                    success=True,
                )
                
        except httpx.TimeoutException:
            logger.error("llm_timeout")
            return LLMResponse(
                content="",
                success=False,
                error="Timeout ao chamar LLM",
            )
        except Exception as e:
            logger.error("llm_exception", error=str(e))
            return LLMResponse(
                content="",
                success=False,
                error=f"Erro: {str(e)}",
            )
    
    async def classify_intent(
        self,
        message: str,
        history: Optional[list[dict]] = None,
    ) -> IntentClassification:
        """
        Classifica a intent da mensagem usando LLM com structured output.
        
        Args:
            message: Mensagem do usuário
            history: Histórico opcional
            
        Returns:
            IntentClassification estruturada
        """
        # ============================================================
        # FORÇAR REGEX FALLBACK para perguntas que requerem ação
        # ============================================================
        # Isso evita que o LLM classifique errado perguntas como "chat"
        msg_lower = message.lower()
        
        # Padrões que DEVEM executar ação (não podem ser classificados como chat)
        force_action_patterns = [
            "tem o", "tem installed", "esta instalado", "está instalado",
            "como ver", "como verificar", "como saber", "como instalar",
            "tem docker", "tem postgres", "tem redis", "tem o claude",
            "execute ", "rode ", "pesquise ", "busque ",
        ]
        
        use_regex_fallback = any(
            pattern in msg_lower for pattern in force_action_patterns
        )
        
        if use_regex_fallback:
            logger.info(
                "intent_forced_regex_fallback",
                message=message[:50],
                reason="force_action_pattern_detected"
            )
            from ..vps_langgraph.intent_classifier_llm import infer_intent_from_message
            result = infer_intent_from_message(message)
            return IntentClassification(**result)
        
        system_prompt = """Você é um classificador de intenções para o VPS-Agent.
Analise a mensagem do usuário e retorne APENAS um JSON válido.

Intenções possíveis:
- "command": Comando direto (/comando ou instrução direta)
- "task": Tarefa a ser executada (liste, mostre, verifique, execute, pesquise, rode)
- "question": Pergunta sobre o sistema (RAM, containers, status) - MAS APENAS se for pergunta genérica
- "chat": Conversa casual
- "self_improve": Pedido para criar/melhorar algo

IMPORTANTE: Se a mensagem pede para FAZER algo (verificar, executar, rodar, checar, pesquisar),
classifique como "task" com action_required=true

Tools disponíveis:
- "get_ram": Perguntas sobre memória RAM
- "list_containers": Perguntas sobre Docker/containers
- "get_system_status": Status geral do sistema
- "check_postgres": Status do PostgreSQL
- "check_redis": Status do Redis
- "shell_exec": Para executar comandos
- "web_search": Para pesquisar na internet
- "": Nenhuma tool específica

Regras:
- "tem o docker instalado?" → task + shell_exec (precisa executar comando)
- "execute docker ps" → task + shell_exec
- "pesquise X" → task + web_search
- "quanta RAM?" → question + get_ram
- "containers docker rodando?" → question + list_containers
- "oi", "tudo bem?" → chat
- "crie um agente" → self_improve

Retorne EXATAMENTE este formato JSON:
{
    "intent": "question|command|task|chat|self_improve",
    "confidence": 0.95,
    "action_required": true|false,
    "tool_suggestion": "get_ram|list_containers|shell_exec|web_search|...",
    "entities": ["ram", "docker"],
    "reasoning": "breve explicação"
}"""
        
        response = await self.generate(
            user_message=message,
            system_prompt=system_prompt,
            history=history,
            json_mode=True,
        )
        
        if not response.success or not response.content:
            logger.warning(
                "intent_classification_failed",
                error=response.error,
                fallback="regex",
            )
            # Fallback para regex
            from ..vps_langgraph.intent_classifier_llm import infer_intent_from_message
            result = infer_intent_from_message(message)
            return IntentClassification(**result)
        
        try:
            # Parse JSON
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            data = json.loads(content)
            
            return IntentClassification(
                intent=data.get("intent", "chat"),
                confidence=float(data.get("confidence", 0.7)),
                action_required=bool(data.get("action_required", False)),
                tool_suggestion=data.get("tool_suggestion", ""),
                entities=data.get("entities", []),
                reasoning=data.get("reasoning", ""),
            )
            
        except json.JSONDecodeError as e:
            logger.error(
                "intent_json_parse_error",
                content=response.content[:200],
                error=str(e),
            )
            # Fallback para regex
            from ..vps_langgraph.intent_classifier_llm import infer_intent_from_message
            result = infer_intent_from_message(message)
            return IntentClassification(**result)
    
    async def generate_with_identity(
        self,
        user_message: str,
        conversation_history: Optional[list[dict]] = None,
        user_context: Optional[dict] = None,
    ) -> str:
        """
        Gera resposta com identidade VPS-Agent.
        
        Args:
            user_message: Mensagem do usuário
            conversation_history: Histórico de conversa
            user_context: Contexto do usuário
            
        Returns:
            Resposta em string
        """
        from .agent_identity import get_vps_agent_identity
        
        system_prompt = get_vps_agent_identity()
        
        # Adicionar contexto do usuário
        if user_context:
            context_str = "\n\n## Contexto do Usuário\n"
            for key, value in user_context.items():
                context_str += f"- {key}: {value}\n"
            system_prompt += context_str
        
        response = await self.generate(
            user_message=user_message,
            system_prompt=system_prompt,
            history=conversation_history,
        )
        
        if response.success:
            return response.content
        
        # Fallback
        return (
            "Sou o VPS-Agent! 😊\n\n"
            "Desculpe, estou com dificuldades técnicas no momento.\n\n"
            "Posso ajudar com comandos diretos como:\n"
            "• /status - Status da VPS\n"
            "• /ram - Uso de memória\n"
            "• /containers - Containers Docker\n"
            "• /health - Health check completo"
        )


# Singleton para uso global
_llm_provider: Optional[UnifiedLLMProvider] = None


def get_llm_provider() -> UnifiedLLMProvider:
    """Retorna instância singleton do provider."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = UnifiedLLMProvider()
    return _llm_provider


async def classify_intent_with_llm(
    message: str,
    history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """
    Função de conveniência para classificar intent.
    
    Args:
        message: Mensagem do usuário
        history: Histórico opcional
        
    Returns:
        Dicionário com classificação
    """
    provider = get_llm_provider()
    result = await provider.classify_intent(message, history)
    return {
        "intent": result.intent,
        "confidence": result.confidence,
        "action_required": result.action_required,
        "tool_suggestion": result.tool_suggestion,
        "entities": result.entities,
        "reasoning": result.reasoning,
    }


__all__ = [
    "UnifiedLLMProvider",
    "LLMResponse",
    "IntentClassification",
    "get_llm_provider",
    "classify_intent_with_llm",
]