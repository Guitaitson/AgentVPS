"""
Skill: Memory Query - Consulta memória do agente.

Retorna histórico de conversas, fatos conhecidos e estado do sistema.
"""

import json
from typing import Any, Dict

from core.skills.base import SkillBase
from core.vps_langgraph.memory import AgentMemory


class MemoryQuerySkill(SkillBase):
    """Consulta a memória do agente."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        args = args or {}
        
        raw_input = args.get("raw_input", "")
        query = args.get("query", "").lower()
        
        # Detectar tipo de consulta
        query_type = self._detect_query_type(raw_input, query)
        
        try:
            memory = AgentMemory()
            user_id = args.get("user_id", "default")
            
            if query_type == "history":
                return await self._get_history(memory, user_id, query)
            elif query_type == "facts":
                return await self._get_facts(memory, user_id, query)
            elif query_type == "system":
                return await self._get_system_state(memory)
            else:
                # Retornar resumo geral
                return await self._get_summary(memory, user_id)
                
        except Exception as e:
            return f"❌ Erro ao consultar memória: {e}"

    def _detect_query_type(self, raw_input: str, query: str) -> str:
        """Detecta tipo de consulta."""
        text = (raw_input + " " + query).lower()
        
        if any(k in text for k in ["historico", "history", "conversa", "ultimas"]):
            return "history"
        elif any(k in text for k in ["fato", "fact", "sobre", "sobre mim"]):
            return "facts"
        elif any(k in text for k in ["sistema", "system", "estado"]):
            return "system"
        else:
            return "summary"

    async def _get_history(self, memory: AgentMemory, user_id: str, query: str) -> str:
        """Retorna histórico de conversas."""
        limit = 10
        if "5" in query:
            limit = 5
        elif "3" in query:
            limit = 3
        
        history = memory.get_conversation_history(user_id, limit=limit)
        
        if not history:
            return "📜 Não há histórico de conversas ainda."
        
        lines = ["📜 **Histórico de Conversas**\n"]
        for msg in history[-5:]:  # últimas 5
            role = "👤" if msg.get("role") == "user" else "🤖"
            content = msg.get("content", "")[:100]
            lines.append(f"{role} {content}...")
        
        return "\n".join(lines)

    async def _get_facts(self, memory: AgentMemory, user_id: str, query: str) -> str:
        """Retorna fatos conhecidos sobre o usuário."""
        facts = memory.get_user_facts(user_id)
        
        if not facts:
            return "🧠 Não há fatos conhecidos sobre você ainda."
        
        lines = ["🧠 **Fatos Conhecidos**\n"]
        for key, value in list(facts.items())[:10]:
            if isinstance(value, dict):
                value = str(value)[:50]
            lines.append(f"• **{key}**: {value}")
        
        return "\n".join(lines)

    async def _get_system_state(self, memory: AgentMemory) -> str:
        """Retorna estado do sistema."""
        state = memory.get_system_state()
        
        if not state:
            return "⚙️ Não há estado do sistema registrado."
        
        lines = ["⚙️ **Estado do Sistema**\n"]
        for key, value in list(state.items())[:10]:
            if isinstance(value, dict):
                value = str(value)[:50]
            lines.append(f"• **{key}**: {value}")
        
        return "\n".join(lines)

    async def _get_summary(self, memory: AgentMemory, user_id: str) -> str:
        """Retorna resumo geral da memória."""
        facts = memory.get_user_facts(user_id)
        history = memory.get_conversation_history(user_id, limit=5)
        system = memory.get_system_state()
        
        lines = [
            "🧠 **Resumo da Memória**",
            f"\n📜 Conversas: {len(history)} mensagens",
            f"🗂️ Fatos: {len(facts)} registrados",
            f"⚙️ Estado: {len(system)} chaves",
            "\nPara mais detalhes, pergunte:",
            "• 'meu histórico' - para ver conversas",
            "• 'meus fatos' - para ver fatos conhecidos",
            "• 'estado do sistema' - para ver configurações",
        ]
        
        return "\n".join(lines)
