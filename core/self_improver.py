"""
Self-Improvement Agent - Sprint 4

Sistema de auto-melhoria que permite ao agente:
1. Detectar capacidades faltantes
2. Planejar implementação
3. Executar e testar novas funcionalidades
4. Aprender com resultados
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# ============================================
# Data Models
# ============================================


@dataclass
class CapabilityGap:
    """Representa uma capacidade que o agente não possui."""

    name: str
    description: str
    user_request: str
    priority: int = 1  # 1-5
    status: str = "pending"  # pending, analyzing, implementing, tested, deployed, failed


@dataclass
class Improvement:
    """Uma melhoria implementada."""

    id: str
    capability: str
    description: str
    implementation: str
    test_result: str
    timestamp: str
    status: str  # success, failed, rolled_back


@dataclass
class SelfImprovementConfig:
    """Configuração do sistema de auto-melhoria."""

    enabled: bool = True
    max_attempts: int = 3
    require_approval: bool = True
    auto_deploy: bool = False
    sandbox_mode: bool = True


# ============================================
# Self-Improvement Engine
# ============================================


class SelfImprovementEngine:
    """
    Motor de auto-melhoria do agente.

    Fluxo:
    1. Analisa request do usuário
    2. Detecta capability gap
    3. Gera plano de implementação
    4. Executa em sandbox (se habilitado)
    5. Testa a implementação
    6. Faz deploy ou rollback
    """

    def __init__(self, config: Optional[SelfImprovementConfig] = None):
        self.config = config or SelfImprovementConfig()
        self.pending_gaps: List[CapabilityGap] = []
        self.completed_improvements: List[Improvement] = []
        self._load_history()

    def _load_history(self):
        """Carrega histórico de melhorias do banco."""
        # Por enquanto, mantém em memória
        # Futuro: carregar de PostgreSQL
        pass

    def _save_history(self):
        """Salva histórico de melhorias."""
        # Por enquanto, mantém em memória
        # Futuro: salvar em PostgreSQL
        pass

    async def analyze_request(self, user_message: str) -> Optional[CapabilityGap]:
        """
        Analisa uma mensagem do usuário para detectar capability gaps.

        Args:
            user_message: Mensagem do usuário

        Returns:
            CapabilityGap se detectada, None caso contrário
        """
        # Patterns que indicam necessidade de nova capability
        patterns = {
            "github": "integração com GitHub",
            "api": "acesso a API externa",
            "database": "consulta a banco de dados específico",
            "file": "manipulação de arquivos",
            "web": "busca na web",
            "email": "envio de email",
            "schedule": "tarefa agendada",
            "backup": "backup automático",
            "monitor": "monitoramento específico",
        }

        message_lower = user_message.lower()

        for pattern, capability_name in patterns.items():
            if pattern in message_lower:
                gap = CapabilityGap(
                    name=f"capability_{pattern}",
                    description=f"Nova capability: {capability_name}",
                    user_request=user_message,
                    priority=3,
                )
                self.pending_gaps.append(gap)
                return gap

        return None

    async def generate_implementation_plan(self, gap: CapabilityGap) -> str:
        """
        Gera um plano de implementação para o capability gap.

        Args:
            gap: CapabilityGap a ser implementado

        Returns:
            Plano de implementação em markdown
        """
        # Template de plano
        plan = f"""# Plano de Implementação: {gap.name}

## Descrição
{gap.description}

## Request Original
{gap.user_request}

## Steps de Implementação

### 1. Definir Interface
- Criar função/tool com interface clara
- Definir inputs e outputs
- Documentar comportamento esperado

### 2. Implementar Funcionalidade
- Escrever código Python
- Usar bibliotecas existentes se possível
- Seguir padrões do projeto

### 3. Testes
- Teste unitário básico
- Teste de integração se aplicável

### 4. Documentação
- Adicionar ao README
- Documentar no código

## arquivos a Criar/Modificar
- `core/tools/` - Adicionar nova tool
- `tests/` - Adicionar testes
- `README.md` - Atualizar documentação

## Tempo Estimado
1-2 horas
"""
        return plan

    async def implement_capability(
        self, gap: CapabilityGap, implementation_code: str
    ) -> Improvement:
        """
        Implementa uma nova capability.

        Args:
            gap: CapabilityGap a implementar
            implementation_code: Código a ser implementado

        Returns:
            Improvement com resultado
        """
        improvement_id = f"imp_{gap.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Atualiza status
        gap.status = "implementing"

        try:
            # Em modo sandbox, não modifica arquivos reais
            if self.config.sandbox_mode:
                test_result = "Sandbox mode: implementação não executada"
                status = "success" if not self.config.require_approval else "pending_approval"
            else:
                # Executa implementação
                # Por segurança, não permite execução direta de códigoarbitrário
                test_result = "Execução em produção não habilitada"
                status = "failed"

            improvement = Improvement(
                id=improvement_id,
                capability=gap.name,
                description=gap.description,
                implementation=implementation_code,
                test_result=test_result,
                timestamp=datetime.now().isoformat(),
                status=status,
            )

            self.completed_improvements.append(improvement)
            gap.status = "deployed" if status == "success" else "failed"

            return improvement

        except Exception as e:
            gap.status = "failed"
            return Improvement(
                id=improvement_id,
                capability=gap.name,
                description=gap.description,
                implementation=implementation_code,
                test_result=f"Erro: {str(e)}",
                timestamp=datetime.now().isoformat(),
                status="failed",
            )

    async def rollback_improvement(self, improvement_id: str) -> bool:
        """
        Faz rollback de uma melhoria.

        Args:
            improvement_id: ID da melhoria

        Returns:
            True se sucesso
        """
        for imp in self.completed_improvements:
            if imp.id == improvement_id:
                imp.status = "rolled_back"
                return True
        return False

    def get_status(self) -> Dict[str, Any]:
        """Retorna status do motor de auto-melhoria."""
        return {
            "enabled": self.config.enabled,
            "pending_gaps": len(self.pending_gaps),
            "completed_improvements": len(self.completed_improvements),
            "recent_improvements": [
                {
                    "id": imp.id,
                    "capability": imp.capability,
                    "status": imp.status,
                    "timestamp": imp.timestamp,
                }
                for imp in self.completed_improvements[-5:]
            ],
        }


# ============================================
# Integração com LangGraph
# ============================================


class SelfImprovementNode:
    """
    Node do LangGraph para self-improvement.
    Usado no grafo de processamento de mensagens.
    """

    def __init__(self):
        self.engine = SelfImprovementEngine()

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa o state para verificar necessidade de self-improvement.

        Args:
            state: State do LangGraph

        Returns:
            State atualizado
        """
        user_message = state.get("user_message", "")

        # Detecta capability gap
        gap = await self.engine.analyze_request(user_message)

        if gap:
            # Gera plano
            plan = await self.engine.generate_implementation_plan(gap)

            state["needs_self_improvement"] = True
            state["capability_gap"] = {
                "name": gap.name,
                "description": gap.description,
                "plan": plan,
            }
        else:
            state["needs_self_improvement"] = False

        return state


# ============================================
# CLI Commands
# ============================================


def status_command():
    """Mostra status do self-improvement engine."""
    from core.self_improver import SelfImprovementEngine

    engine = SelfImprovementEngine()
    status = engine.get_status()

    print("=" * 50)
    print("Self-Improvement Engine Status")
    print("=" * 50)
    print(f"Enabled: {status['enabled']}")
    print(f"Pending Gaps: {status['pending_gaps']}")
    print(f"Completed Improvements: {status['completed_improvements']}")
    print()
    print("Recent Improvements:")
    for imp in status["recent_improvements"]:
        print(f"  - {imp['capability']}: {imp['status']} ({imp['timestamp']})")
    print("=" * 50)


def enable_command():
    """Habilita self-improvement."""
    print("Self-improvement enabled")


def disable_command():
    """Desabilita self-improvement."""
    print("Self-improvement disabled")


# ============================================
# Main
# ============================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m core.self_improver <command>")
        print("Commands: status, enable, disable")
        sys.exit(1)

    command = sys.argv[1]

    if command == "status":
        status_command()
    elif command == "enable":
        enable_command()
    elif command == "disable":
        disable_command()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


__all__ = [
    "CapabilityGap",
    "Improvement",
    "SelfImprovementConfig",
    "SelfImprovementEngine",
    "SelfImprovementNode",
]
