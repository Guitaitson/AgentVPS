# Capabilities Registry - Sistema de gerenciamento de capacidades do agente

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timezone
import structlog

logger = structlog.get_logger()


class Capability:
    """Representa uma capacidade do agente."""
    
    def __init__(
        self,
        name: str,
        description: str,
        implemented: bool = False,
        dependencies: Optional[List[str]] = None,
        implementation_path: Optional[str] = None,
        category: str = "general"
    ):
        self.name = name
        self.description = description
        self.implemented = implemented
        self.dependencies = dependencies or []
        self.implementation_path = implementation_path
        self.category = category
        self.created_at = datetime.now(timezone.utc)
        self.implemented_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "name": self.name,
            "description": self.description,
            "implemented": self.implemented,
            "dependencies": self.dependencies,
            "implementation_path": self.implementation_path,
            "category": self.category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "implemented_at": self.implemented_at.isoformat() if self.implemented_at else None
        }
    
    def mark_implemented(self, implementation_path: str):
        """Marca a capacidade como implementada."""
        self.implemented = True
        self.implementation_path = implementation_path
        self.implemented_at = datetime.now(timezone.utc)
        logger.info("capacidade_implementada", capability=self.name)


class CapabilitiesRegistry:
    """Gerencia capacidades disponíveis e detecta faltantes."""
    
    def __init__(self):
        self.capabilities: Dict[str, Capability] = {}
        self._initialize_core_capabilities()
    
    def _initialize_core_capabilities(self):
        """Inicializa capacidades core que sempre existem."""
        core_caps = [
            Capability(
                name="vps_ram",
                description="Consultar status de RAM da VPS",
                implemented=True,
                implementation_path="core/mcp_server.py:/ram",
                category="vps_management"
            ),
            Capability(
                name="vps_containers",
                description="Listar e gerenciar containers Docker",
                implemented=True,
                implementation_path="core/mcp_server.py:/containers",
                category="vps_management"
            ),
            Capability(
                name="vps_services",
                description="Listar serviços core (PostgreSQL, Redis, etc)",
                implemented=True,
                implementation_path="core/mcp_server.py:/services",
                category="vps_management"
            ),
            Capability(
                name="vps_system",
                description="Obter informações do sistema (CPU, RAM, Disk)",
                implemented=True,
                implementation_path="core/mcp_server.py:/system",
                category="vps_management"
            ),
            Capability(
                name="memory_structured",
                description="Memória estruturada em PostgreSQL",
                implemented=True,
                implementation_path="core/langgraph/memory.py",
                category="memory"
            ),
            Capability(
                name="memory_semantic",
                description="Memória semântica em Qdrant (busca vetorial)",
                implemented=True,
                implementation_path="core/vps_agent/semantic_memory.py",
                category="memory"
            ),
            Capability(
                name="telegram_bot",
                description="Interface via Telegram Bot",
                implemented=True,
                implementation_path="telegram-bot/bot.py",
                category="communication"
            ),
            Capability(
                name="langgraph_agent",
                description="Orquestrador LangGraph para processamento de mensagens",
                implemented=True,
                implementation_path="core/langgraph/graph.py",
                category="orchestration"
            ),
            Capability(
                name="mcp_server",
                description="Servidor MCP para expor ferramentas",
                implemented=True,
                implementation_path="core/mcp_server.py",
                category="infrastructure"
            ),
        ]
        
        for cap in core_caps:
            self.register(cap)
    
    def register(self, capability: Capability):
        """Registra uma nova capacidade."""
        self.capabilities[capability.name] = capability
        logger.info("capacidade_registrada", name=capability.name, implemented=capability.implemented)
    
    def check_capability(self, name: str) -> bool:
        """Verifica se uma capacidade existe e está implementada."""
        cap = self.capabilities.get(name)
        if not cap:
            return False
        return cap.implemented
    
    def get_capability(self, name: str) -> Optional[Capability]:
        """Retorna uma capacidade específica."""
        return self.capabilities.get(name)
    
    def get_all_capabilities(self) -> Dict[str, Capability]:
        """Retorna todas as capacidades."""
        return self.capabilities.copy()
    
    def get_implemented_capabilities(self) -> List[Capability]:
        """Retorna capacidades implementadas."""
        return [cap for cap in self.capabilities.values() if cap.implemented]
    
    def get_missing_capabilities(self) -> List[Capability]:
        """Retorna capacidades não implementadas."""
        return [cap for cap in self.capabilities.values() if not cap.implemented]
    
    def detect_missing(self, task: str) -> List[Capability]:
        """Detecta capacidades faltantes baseado em uma tarefa."""
        task_lower = task.lower()
        missing = []
        
        # Padrões de detecção
        patterns = {
            "github": ["github", "repositório", "repo", "pr", "pull request"],
            "file": ["arquivo", "file", "criar arquivo", "ler arquivo", "editar arquivo", "deletar arquivo"],
            "web": ["site", "web", "scraping", "http", "url", "api externa"],
            "database": ["banco de dados", "database", "sql", "query"],
        }
        
        for category, keywords in patterns.items():
            if any(keyword in task_lower for keyword in keywords):
                # Verificar se já existe capacidade dessa categoria
                category_caps = [cap for cap in self.capabilities.values() if cap.category == category]
                if not category_caps:
                    # Criar capacidade placeholder
                    missing.append(Capability(
                        name=f"{category}_api",
                        description=f"API para {category}",
                        implemented=False,
                        category=category
                    ))
        
        return missing
    
    def get_implementation_plan(self, capability: Capability) -> str:
        """Gera um plano de implementação para uma capacidade."""
        if capability.implemented:
            return f"Capacidade {capability.name} já está implementada em {capability.implementation_path}"
        
        plan = f"""# Plano de Implementação: {capability.name}

## Descrição
{capability.description}

## Dependências
{chr(10).join(f"- {dep}" for dep in capability.dependencies) if capability.dependencies else "Nenhuma"}

## Passos de Implementação

1. **Análise de Requisitos**
   - Revisar dependências necessárias
   - Verificar integração com sistemas existentes

2. **Desenvolvimento**
   - Criar módulo principal
   - Implementar funcionalidades core
   - Adicionar testes

3. **Integração**
   - Conectar com LangGraph
   - Adicionar ao CapabilitiesRegistry
   - Atualizar documentação

4. **Testes**
   - Testes unitários
   - Testes de integração
   - Testes de cenários reais

5. **Deploy**
   - Commit no GitHub
   - Deploy na VPS
   - Verificar funcionamento

## Arquivos a Criar
- core/{capability.category}/{capability.name}.py
- core/{capability.category}/__init__.py
- Atualizar core/capabilities/registry.py

## Integração com CLI
O CLI/Kilocode será usado para gerar o código de implementação.
"""
        return plan
    
    def mark_capability_implemented(self, name: str, implementation_path: str):
        """Marca uma capacidade como implementada."""
        cap = self.capabilities.get(name)
        if cap:
            cap.mark_implemented(implementation_path)
            logger.info("capacidade_implementada", name=name, path=implementation_path)
        else:
            logger.warning("capacidade_nao_encontrada", name=name)
    
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo do registry."""
        total = len(self.capabilities)
        implemented = len(self.get_implemented_capabilities())
        missing = len(self.get_missing_capabilities())
        
        return {
            "total_capabilities": total,
            "implemented": implemented,
            "missing": missing,
            "implementation_rate": f"{(implemented/total*100):.1f}%" if total > 0 else "0%",
            "categories": self._get_category_summary()
        }
    
    def _get_category_summary(self) -> Dict[str, int]:
        """Retorna resumo por categoria."""
        summary = {}
        for cap in self.capabilities.values():
            summary[cap.category] = summary.get(cap.category, 0) + 1
        return summary


# Instância global do registry
capabilities_registry = CapabilitiesRegistry()
