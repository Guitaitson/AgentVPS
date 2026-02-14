# 🔧 Plano de Implementação Detalhado — Sprint "De Infraestrutura Para Capacidade"

> **Referências:** Ler `sprint-01-objetivo.md` para contexto e `sprint-01-roadmap.md` para visão geral antes de começar.

---

## Como Usar Este Documento

Cada job tem: **o que fazer**, **onde fazer** (paths exatos), **como fazer** (código de referência), **como testar** (comandos exatos), e **armadilhas** (erros comuns). Siga na ordem. Não pule jobs sem marcar o checkpoint anterior.

---

## S1 — SKILL REGISTRY

### S1-01: Base do Skill Registry (~8h)

#### O Que Construir

Um sistema onde cada skill é um diretório com estrutura padronizada. O registry descobre skills automaticamente no startup e os expõe para o grafo LangGraph.

#### Estrutura de Diretórios a Criar

```
core/
└── skills/
    ├── __init__.py
    ├── registry.py          # O registry central
    ├── base.py              # Classe base SkillBase
    ├── _builtin/            # Skills migrados do system_tools
    │   ├── __init__.py
    │   ├── ram/
    │   │   ├── __init__.py
    │   │   ├── handler.py   # A função que executa
    │   │   └── config.yaml  # Metadata do skill
    │   ├── containers/
    │   │   ├── __init__.py
    │   │   ├── handler.py
    │   │   └── config.yaml
    │   ├── system_status/
    │   │   ├── __init__.py
    │   │   ├── handler.py
    │   │   └── config.yaml
    │   ├── check_postgres/
    │   │   ├── __init__.py
    │   │   ├── handler.py
    │   │   └── config.yaml
    │   └── check_redis/
    │       ├── __init__.py
    │       ├── handler.py
    │       └── config.yaml
    └── README.md            # Como criar um skill novo
```

#### Arquivo: `core/skills/base.py`

```python
"""
Base class para todos os skills do AgentVPS.

Cada skill deve herdar de SkillBase e implementar execute().
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SecurityLevel(Enum):
    """Nível de segurança do skill."""
    SAFE = "safe"              # Executa sem perguntar (leitura)
    MODERATE = "moderate"      # Executa + log
    DANGEROUS = "dangerous"    # Requer approval via Telegram
    FORBIDDEN = "forbidden"    # Nunca executa


@dataclass
class SkillConfig:
    """Configuração de um skill, carregada do config.yaml."""
    name: str
    description: str
    version: str = "1.0.0"
    security_level: SecurityLevel = SecurityLevel.SAFE
    triggers: List[str] = field(default_factory=list)    # keywords que ativam o skill
    parameters: Dict[str, Any] = field(default_factory=dict)
    max_output_chars: int = 2000
    timeout_seconds: int = 30
    enabled: bool = True


class SkillBase(ABC):
    """
    Classe base para skills.
    
    Para criar um skill novo:
    1. Criar diretório em core/skills/ (ex: core/skills/meu_skill/)
    2. Criar handler.py com classe que herda SkillBase
    3. Criar config.yaml com metadata
    4. O registry descobre automaticamente no startup
    """

    def __init__(self, config: SkillConfig):
        self.config = config

    @abstractmethod
    async def execute(self, args: Dict[str, Any] = None) -> str:
        """
        Executa o skill.
        
        Args:
            args: Argumentos opcionais (ex: {"command": "ls -la"})
            
        Returns:
            String com resultado da execução
        """
        pass

    def validate_args(self, args: Dict[str, Any] = None) -> bool:
        """Valida argumentos antes de executar. Override para validação custom."""
        return True

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def security_level(self) -> SecurityLevel:
        return self.config.security_level
```

#### Arquivo: `core/skills/registry.py`

```python
"""
Skill Registry — Descobre, registra e gerencia skills.

Substitui o TOOLS_REGISTRY hardcoded de core/tools/system_tools.py.
"""

import importlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
import yaml

from .base import SecurityLevel, SkillBase, SkillConfig

logger = structlog.get_logger()


class SkillRegistry:
    """
    Registry central de skills.
    
    Descobre skills automaticamente em diretórios configurados.
    Cada skill é um diretório com handler.py + config.yaml.
    """

    def __init__(self, skill_dirs: List[str] = None):
        self._skills: Dict[str, SkillBase] = {}
        self._skill_dirs = skill_dirs or [
            os.path.join(os.path.dirname(__file__), "_builtin"),
        ]

    def discover_and_register(self) -> int:
        """
        Descobre skills em todos os diretórios configurados.
        
        Returns:
            Número de skills registrados
        """
        count = 0
        for skill_dir in self._skill_dirs:
            if not os.path.isdir(skill_dir):
                logger.warning("skill_dir_not_found", path=skill_dir)
                continue

            for entry in os.scandir(skill_dir):
                if not entry.is_dir() or entry.name.startswith("_"):
                    continue
                
                config_path = os.path.join(entry.path, "config.yaml")
                handler_path = os.path.join(entry.path, "handler.py")

                if not os.path.exists(config_path) or not os.path.exists(handler_path):
                    logger.debug("skill_incomplete", path=entry.path)
                    continue

                try:
                    skill = self._load_skill(entry.path, entry.name)
                    if skill and skill.config.enabled:
                        self._skills[skill.name] = skill
                        count += 1
                        logger.info("skill_registered", name=skill.name)
                except Exception as e:
                    logger.error("skill_load_error", path=entry.path, error=str(e))

        logger.info("skill_discovery_complete", total=count)
        return count

    def _load_skill(self, skill_path: str, dir_name: str) -> Optional[SkillBase]:
        """Carrega um skill a partir do diretório."""
        # Carregar config.yaml
        config_path = os.path.join(skill_path, "config.yaml")
        with open(config_path, "r") as f:
            raw_config = yaml.safe_load(f)

        # Converter security_level string para enum
        sec_level = raw_config.get("security_level", "safe")
        raw_config["security_level"] = SecurityLevel(sec_level)

        config = SkillConfig(**raw_config)

        # Importar handler.py dinamicamente
        # Calcular module path relativo ao projeto
        # Ex: core.skills._builtin.ram.handler
        rel_path = os.path.relpath(skill_path, 
                                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        module_path = rel_path.replace(os.sep, ".") + ".handler"

        module = importlib.import_module(module_path)

        # Procurar classe que herda SkillBase
        handler_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) 
                and issubclass(attr, SkillBase) 
                and attr is not SkillBase):
                handler_class = attr
                break

        if handler_class is None:
            logger.error("no_skill_class_found", path=skill_path)
            return None

        return handler_class(config)

    def get(self, name: str) -> Optional[SkillBase]:
        """Retorna skill pelo nome."""
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, Any]]:
        """Lista todos os skills registrados."""
        return [
            {
                "name": s.name,
                "description": s.config.description,
                "security_level": s.config.security_level.value,
                "triggers": s.config.triggers,
                "enabled": s.config.enabled,
            }
            for s in self._skills.values()
        ]

    def find_by_trigger(self, text: str) -> Optional[SkillBase]:
        """Encontra skill que melhor corresponde ao texto."""
        text_lower = text.lower()
        for skill in self._skills.values():
            for trigger in skill.config.triggers:
                if trigger.lower() in text_lower:
                    return skill
        return None

    async def execute_skill(self, name: str, args: Dict[str, Any] = None) -> str:
        """Executa um skill pelo nome."""
        skill = self.get(name)
        if not skill:
            return f"❌ Skill '{name}' não encontrado. Use /skills para ver disponíveis."
        
        if not skill.validate_args(args):
            return f"❌ Argumentos inválidos para skill '{name}'."

        return await skill.execute(args or {})

    @property
    def count(self) -> int:
        return len(self._skills)
```

#### Exemplo: `core/skills/_builtin/ram/config.yaml`

```yaml
name: get_ram
description: "Mostra uso atual de RAM do sistema em MB"
version: "1.0.0"
security_level: safe
triggers:
  - ram
  - memória
  - memoria
  - memory
  - /ram
parameters: {}
max_output_chars: 500
timeout_seconds: 10
enabled: true
```

#### Exemplo: `core/skills/_builtin/ram/handler.py`

```python
"""Skill: RAM Usage — Mostra uso de RAM do sistema."""

from typing import Any, Dict

from core.skills.base import SkillBase


class RamSkill(SkillBase):
    """Mostra uso atual de RAM."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()

            values = {}
            for line in meminfo.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    values[key.strip()] = int(val.strip().split()[0])

            total = values.get("MemTotal", 0) // 1024
            available = values.get("MemAvailable", 0) // 1024
            used = total - available
            pct = (used / total * 100) if total > 0 else 0

            return (
                f"🧠 RAM: {used}MB / {total}MB ({pct:.1f}%)\n"
                f"📊 Disponível: {available}MB"
            )
        except Exception as e:
            return f"❌ Erro ao ler RAM: {e}"
```

#### O Que Modificar no Grafo

Arquivo: `core/vps_langgraph/nodes.py` — Substituir todo o `node_execute` por:

```python
async def node_execute(state: AgentState) -> AgentState:
    """Executa ação usando Skill Registry."""
    from core.skills.registry import get_skill_registry
    from .error_handler import format_error_for_user, wrap_error

    if state.get("blocked_by_security"):
        return state

    registry = get_skill_registry()
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    tool_suggestion = state.get("tool_suggestion", "")

    try:
        # 1. Tentar skill pelo plano
        if plan and step < len(plan):
            action = plan[step].get("action", "")
            action_type = plan[step].get("type", "")
            
            # Mapear action para skill name
            skill = registry.get(action) or registry.find_by_trigger(action)
            if skill:
                result = await registry.execute_skill(skill.name, {"raw_input": action})
                return {**state, "execution_result": result}

        # 2. Tentar por tool_suggestion do LLM
        if tool_suggestion:
            skill = registry.get(tool_suggestion) or registry.find_by_trigger(tool_suggestion)
            if skill:
                result = await registry.execute_skill(skill.name)
                return {**state, "execution_result": result}

        # 3. Skill não encontrado — resposta inteligente
        from .smart_responses import generate_smart_unavailable_response, detect_missing_skill_keywords
        user_msg = state.get("user_message", "")
        detected = detect_missing_skill_keywords(user_msg.lower())
        response = generate_smart_unavailable_response(user_msg, detected_skills=detected)
        return {**state, "execution_result": response}

    except Exception as e:
        wrapped = wrap_error(e, metadata={"skill": tool_suggestion})
        return {
            **state,
            "error": wrapped.to_dict(),
            "execution_result": format_error_for_user(e),
        }
```

Isso substitui ~250 linhas de if/elif hardcoded por ~40 linhas que delegam ao registry.

#### Singleton Pattern Para o Registry

Adicionar ao final de `core/skills/registry.py`:

```python
# Singleton
_registry: Optional[SkillRegistry] = None

def get_skill_registry() -> SkillRegistry:
    """Retorna instância global do registry (lazy init)."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _registry.discover_and_register()
    return _registry
```

#### Checkpoint S1-01
```
□ Diretório core/skills/ criado com base.py, registry.py
□ 5 skills em core/skills/_builtin/ (ram, containers, system_status, check_postgres, check_redis)
□ Cada skill tem handler.py + config.yaml
□ python -c "from core.skills.registry import SkillRegistry; r = SkillRegistry(); r.discover_and_register(); print(r.list_skills())" funciona
```

---

### S1-02: Migrar Node Execute (~6h)

#### O Que Fazer

1. Substituir o `node_execute` atual (250+ linhas) pelo novo que delega ao registry (~40 linhas)
2. Manter `core/tools/system_tools.py` temporariamente como fallback
3. Verificar que TODOS os 5 comandos Telegram continuam funcionando

#### Passo a Passo

**Passo 1:** Copiar o `node_execute` novo (seção anterior) para `core/vps_langgraph/nodes.py`, substituindo o existente.

**Passo 2:** No `telegram_bot/bot.py`, os CommandHandlers (`/ram`, `/containers`, etc.) chamam `process_message_async` que passa pelo grafo. Verificar que o fluxo `classify → plan → execute (via registry)` retorna os mesmos resultados.

**Passo 3:** Testar cada comando via Telegram:
```
/ram          → deve mostrar uso de RAM
/containers   → deve listar containers Docker
/status       → deve mostrar status geral
/health       → deve mostrar saúde dos serviços
"quanto de ram?"  → deve detectar intent e usar skill
```

**Passo 4:** Se tudo funcionar, adicionar comentário `# DEPRECATED` no `TOOLS_REGISTRY` de `system_tools.py`. Não deletar ainda — será removido em S3.

#### Armadilhas

- O `node_plan` mapeia intents para actions usando nomes como `"ram"`, `"containers"`, `"status"`. O config.yaml de cada skill precisa ter esses nomes como triggers para o `find_by_trigger` funcionar.
- O `node_plan` retorna `plan: [{"type": "command", "action": "ram"}]`. O novo `node_execute` precisa resolver `action="ram"` para o skill `get_ram`. Isso funciona via `registry.get("ram")` OU `registry.find_by_trigger("ram")`.
- Solução: no config.yaml, incluir tanto o nome do skill quanto os aliases como triggers.

#### Checkpoint S1-02
```
□ node_execute em nodes.py tem menos de 50 linhas
□ /ram no Telegram retorna uso de RAM via registry
□ /containers no Telegram retorna lista de containers via registry
□ /status no Telegram retorna status do sistema via registry
□ /health no Telegram retorna health checks via registry
□ "quanta ram tem?" (mensagem livre) retorna RAM via LLM classify + registry
□ CI/CD verde
```

---

### S1-03: Testes do Registry (~4h)

#### Arquivo: `tests/test_skill_registry.py`

```python
"""Testes para o Skill Registry."""

import pytest
from core.skills.base import SecurityLevel, SkillBase, SkillConfig
from core.skills.registry import SkillRegistry


class MockSkill(SkillBase):
    """Skill de teste."""
    async def execute(self, args=None):
        return "mock result"


@pytest.fixture
def registry(tmp_path):
    """Registry com diretório temporário."""
    return SkillRegistry(skill_dirs=[str(tmp_path)])


@pytest.fixture
def mock_skill():
    config = SkillConfig(
        name="test_skill",
        description="Skill de teste",
        triggers=["teste", "test"],
        security_level=SecurityLevel.SAFE,
    )
    return MockSkill(config)


class TestSkillRegistry:
    def test_empty_registry(self, registry):
        assert registry.count == 0
        assert registry.list_skills() == []

    def test_get_nonexistent_skill(self, registry):
        assert registry.get("nonexistent") is None

    def test_find_by_trigger(self, registry, mock_skill):
        registry._skills["test_skill"] = mock_skill
        found = registry.find_by_trigger("quero fazer um teste")
        assert found is not None
        assert found.name == "test_skill"

    def test_find_by_trigger_no_match(self, registry, mock_skill):
        registry._skills["test_skill"] = mock_skill
        found = registry.find_by_trigger("completamente irrelevante")
        assert found is None

    @pytest.mark.asyncio
    async def test_execute_skill(self, registry, mock_skill):
        registry._skills["test_skill"] = mock_skill
        result = await registry.execute_skill("test_skill")
        assert result == "mock result"

    @pytest.mark.asyncio
    async def test_execute_nonexistent(self, registry):
        result = await registry.execute_skill("ghost")
        assert "não encontrado" in result

    def test_list_skills(self, registry, mock_skill):
        registry._skills["test_skill"] = mock_skill
        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "test_skill"
        assert skills[0]["security_level"] == "safe"

    def test_discover_builtin(self):
        """Testa discovery dos skills builtin reais."""
        registry = SkillRegistry()
        count = registry.discover_and_register()
        assert count >= 5  # ram, containers, status, postgres, redis
```

#### Checkpoint S1-03
```
□ pytest tests/test_skill_registry.py passa (8+ testes)
□ CI/CD verde com os novos testes
```

---

## S2 — 5 SKILLS CORE

### S2-01: Shell Exec (~6h)

#### Estrutura

```
core/skills/shell_exec/
├── __init__.py
├── handler.py
└── config.yaml
```

#### `config.yaml`

```yaml
name: shell_exec
description: "Executa comandos shell na VPS com classificação de segurança"
version: "1.0.0"
security_level: moderate  # Nível base; comandos perigosos são elevados internamente
triggers:
  - execute
  - executar
  - rodar
  - run
  - shell
  - comando
  - terminal
parameters:
  command:
    type: string
    required: true
    description: "Comando shell a executar"
max_output_chars: 2000
timeout_seconds: 30
enabled: true
```

#### `handler.py` — Lógica Principal

```python
"""
Skill: Shell Exec — Executa comandos na VPS com segurança.

Classificação de comandos:
  SAFE:       ls, cat, df, uptime, whoami, pwd, free, ps, docker ps
  MODERATE:   apt list, pip list, git status, find
  DANGEROUS:  rm, kill, systemctl, docker stop/rm, apt install, pip install
  FORBIDDEN:  rm -rf /, chmod 777, dd if=, mkfs, iptables -F
"""

import asyncio
import re
from typing import Any, Dict, List

from core.skills.base import SecurityLevel, SkillBase

# Padrões de classificação (ordem importa: FORBIDDEN primeiro)
FORBIDDEN_PATTERNS = [
    r"rm\s+-rf\s+/\s*$",
    r"rm\s+-rf\s+/\*",
    r"chmod\s+777\s+/",
    r"dd\s+if=",
    r"mkfs\.",
    r"iptables\s+-F",
    r":(){ :|:& };:",          # Fork bomb
    r"> /dev/sd",
    r"wget.*\|\s*sh",          # Pipe download to shell
    r"curl.*\|\s*sh",
]

DANGEROUS_PATTERNS = [
    r"^rm\s",
    r"^kill\s",
    r"^killall\s",
    r"^systemctl\s+(stop|restart|disable|mask)",
    r"^docker\s+(stop|rm|rmi|prune)",
    r"^apt\s+(install|remove|purge)",
    r"^pip\s+install",
    r"^reboot",
    r"^shutdown",
    r"^passwd",
    r"^chown\s",
    r"^chmod\s",
    r"^mv\s+/",
]

SAFE_PATTERNS = [
    r"^ls\b",
    r"^cat\b",
    r"^head\b",
    r"^tail\b",
    r"^df\b",
    r"^uptime",
    r"^whoami",
    r"^pwd",
    r"^free\b",
    r"^ps\b",
    r"^docker\s+(ps|stats|logs|inspect|images)",
    r"^uname\b",
    r"^date\b",
    r"^hostname",
    r"^wc\b",
    r"^grep\b",
    r"^find\b.*-name",
    r"^echo\b",
    r"^id\b",
]


def classify_command(command: str) -> SecurityLevel:
    """Classifica nível de segurança de um comando."""
    cmd = command.strip()

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, cmd):
            return SecurityLevel.FORBIDDEN

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            return SecurityLevel.DANGEROUS

    for pattern in SAFE_PATTERNS:
        if re.search(pattern, cmd):
            return SecurityLevel.SAFE

    # Default: MODERATE (desconhecido mas não proibido)
    return SecurityLevel.MODERATE


class ShellExecSkill(SkillBase):
    """Executa comandos shell com classificação de segurança."""

    async def execute(self, args: Dict[str, Any] = None) -> str:
        command = (args or {}).get("command") or (args or {}).get("raw_input", "")

        if not command:
            return "❌ Nenhum comando fornecido. Exemplo: 'execute ls -la'"

        # Limpar prefixos comuns
        for prefix in ["execute ", "executar ", "rodar ", "run "]:
            if command.lower().startswith(prefix):
                command = command[len(prefix):].strip()
                break

        # Classificar segurança
        level = classify_command(command)

        if level == SecurityLevel.FORBIDDEN:
            return f"🚫 Comando PROIBIDO por segurança: `{command}`\nEste comando pode causar danos irreversíveis."

        if level == SecurityLevel.DANGEROUS:
            # Aqui, no futuro, pedimos approval via Telegram.
            # Por enquanto: executar com WARNING.
            # TODO S2-01: Integrar com approval workflow quando implementado
            pass

        # Executar
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout_seconds,
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            # Truncar output longo
            max_chars = self.config.max_output_chars
            if len(output) > max_chars:
                output = output[:max_chars] + f"\n... [truncado, {len(output)} chars total]"

            # Montar resposta
            level_emoji = {
                SecurityLevel.SAFE: "✅",
                SecurityLevel.MODERATE: "⚠️",
                SecurityLevel.DANGEROUS: "🔴",
            }
            emoji = level_emoji.get(level, "⚙️")

            result = f"{emoji} `{command}`\n"
            if output.strip():
                result += f"```\n{output.strip()}\n```"
            if errors.strip():
                result += f"\n⚠️ stderr:\n```\n{errors.strip()}\n```"
            if process.returncode != 0:
                result += f"\n❌ Exit code: {process.returncode}"

            return result

        except asyncio.TimeoutError:
            return f"⏱️ Comando excedeu timeout de {self.config.timeout_seconds}s: `{command}`"
        except Exception as e:
            return f"❌ Erro ao executar: {e}"
```

#### Integração com node_plan

No `core/vps_langgraph/nodes.py`, modificar `node_plan` para rotear intents de comando shell:

```python
# Em node_plan, dentro de intent == "command" ou "task":
# Se o LLM sugere shell_exec como tool, incluir o comando raw no plano
if intent in ["command", "task"]:
    return {
        **state,
        "plan": [{"type": "skill", "action": "shell_exec", "args": {"command": user_message}}],
        "current_step": 0,
        "tools_needed": ["shell_exec"],
    }
```

E no `node_execute` (já refatorado em S1-02), adicionar passagem de args:

```python
# Quando o plano tem args, passar para o skill
plan_args = plan[step].get("args", {})
result = await registry.execute_skill(skill.name, plan_args)
```

#### Checkpoint S2-01
```
□ Telegram: "execute ls -la /opt/vps-agent" → lista de arquivos (SAFE, sem approval)
□ Telegram: "execute docker ps -a" → lista containers (SAFE)
□ Telegram: "execute rm -rf /" → BLOQUEADO (FORBIDDEN)
□ Telegram: "execute systemctl stop postgres" → WARNING de DANGEROUS
□ Teste: classify_command("ls -la") == SecurityLevel.SAFE
□ Teste: classify_command("rm -rf /") == SecurityLevel.FORBIDDEN
```

---

### S2-02: File Manager (~4h)

#### Estrutura Idêntica

```
core/skills/file_manager/
├── __init__.py
├── handler.py
└── config.yaml
```

#### Lógica Principal (handler.py)

Operações: `read`, `write`, `append`, `list_dir`, `exists`.

Segurança:
- Paths PERMITIDOS: `/opt/vps-agent/`, `/tmp/`, `/home/`, `/var/log/` (somente leitura)
- Paths PROIBIDOS: `/etc/shadow`, `/etc/passwd`, `/root/.ssh/`, qualquer path com `..`
- Write/append em paths de sistema: DANGEROUS (requer approval futuro)
- Read: sempre SAFE

```python
# Validação de path (parte crítica)
ALLOWED_READ_PATHS = ["/opt/vps-agent/", "/tmp/", "/home/", "/var/log/", "/proc/"]
ALLOWED_WRITE_PATHS = ["/opt/vps-agent/", "/tmp/", "/home/"]
FORBIDDEN_PATHS = ["/etc/shadow", "/etc/passwd", "/root/.ssh/", "/etc/sudoers"]

def is_path_allowed(path: str, operation: str = "read") -> tuple[bool, str]:
    """Verifica se path é permitido para a operação."""
    import os
    resolved = os.path.realpath(path)  # Resolve symlinks e ..
    
    # Proibidos absolutos
    for forbidden in FORBIDDEN_PATHS:
        if resolved.startswith(forbidden):
            return False, f"Path proibido: {forbidden}"
    
    # Verificar contra lista de permitidos
    allowed = ALLOWED_WRITE_PATHS if operation in ["write", "append"] else ALLOWED_READ_PATHS
    for allowed_path in allowed:
        if resolved.startswith(allowed_path):
            return True, "OK"
    
    return False, f"Path fora dos diretórios permitidos: {resolved}"
```

#### Checkpoint S2-02
```
□ Telegram: "leia /opt/vps-agent/README.md" → conteúdo do arquivo
□ Telegram: "crie /tmp/teste.txt com conteúdo hello" → arquivo criado
□ Telegram: "liste /opt/vps-agent/configs/" → lista de arquivos
□ Telegram: "leia /etc/shadow" → BLOQUEADO
□ Telegram: "leia /opt/vps-agent/../../../etc/passwd" → BLOQUEADO (path traversal)
```

---

### S2-03: Web Search (~4h)

#### API: Brave Search

Free tier: 2.000 queries/mês (suficiente para uso pessoal).

```yaml
# config.yaml
name: web_search
description: "Busca informações na internet via Brave Search API"
security_level: safe
triggers:
  - buscar
  - busque
  - pesquisar
  - pesquise
  - search
  - procurar
  - internet
  - web
```

```python
# handler.py — parte principal
import httpx

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

class WebSearchSkill(SkillBase):
    async def execute(self, args=None):
        query = (args or {}).get("query") or (args or {}).get("raw_input", "")
        
        # Limpar prefixos
        for prefix in ["busque ", "pesquise ", "search ", "procure "]:
            if query.lower().startswith(prefix):
                query = query[len(prefix):].strip()
                break

        if not BRAVE_API_KEY:
            return "❌ BRAVE_SEARCH_API_KEY não configurada. Adicione ao .env"

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                BRAVE_URL,
                headers={"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"},
                params={"q": query, "count": 5},
            )
            data = response.json()

        results = data.get("web", {}).get("results", [])
        if not results:
            return f"🔍 Nenhum resultado para: {query}"

        output = f"🔍 Resultados para: **{query}**\n\n"
        for i, r in enumerate(results[:5], 1):
            output += f"{i}. **{r.get('title', 'Sem título')}**\n"
            output += f"   {r.get('description', '')[:150]}\n"
            output += f"   🔗 {r.get('url', '')}\n\n"

        return output
```

#### Configuração Necessária

Adicionar ao `.env`:
```
BRAVE_SEARCH_API_KEY=BSA...  # Obter em https://api.search.brave.com/
```

#### Checkpoint S2-03
```
□ Telegram: "busque como instalar Node.js 22 Ubuntu" → 5 resultados com links
□ Telegram: "pesquise preço do dólar hoje" → resultados
□ Sem API key configurada → mensagem clara de erro
□ Teste: mock httpx, verificar parsing de resultados
```

---

### S2-04: Memory Query (~3h)

Queries predefinidas seguras para consultar o PostgreSQL sem risco de SQL injection.

```python
# Queries predefinidas (NUNCA usar input do usuário em SQL direto)
PREDEFINED_QUERIES = {
    "learnings": "SELECT category, trigger, lesson, created_at FROM learnings ORDER BY created_at DESC LIMIT 10",
    "recent_conversations": "SELECT role, content, created_at FROM conversation_log ORDER BY created_at DESC LIMIT 20",
    "capabilities": "SELECT capability_name, description, implemented FROM agent_capabilities ORDER BY category",
    "skills": "SELECT skill_name, description, success_count, failure_count FROM agent_skills ORDER BY success_count DESC",
    "memory": "SELECT key, value, memory_type FROM agent_memory WHERE user_id = $1 ORDER BY updated_at DESC LIMIT 20",
}
```

#### Checkpoint S2-04
```
□ Telegram: "o que você aprendeu?" → lista de learnings
□ Telegram: "qual meu histórico?" → últimas conversas
□ Telegram: "quais suas capacidades?" → lista de capabilities
```

---

### S2-05: Self Edit (~3h)

Lê/modifica arquivos do projeto AgentVPS. Sempre faz backup. Requer approval.

```python
# Segurança: APENAS arquivos dentro de /opt/vps-agent/
# Sempre cria backup em /opt/vps-agent/backups/
# Sempre commita com mensagem [self-edit]
# SecurityLevel: DANGEROUS (requer approval)
```

#### Checkpoint S2-05
```
□ Telegram: "leia core/config.py" → conteúdo do arquivo
□ Telegram: "adicione um comentário no topo de core/config.py" → backup criado + arquivo editado + commit
□ Qualquer edição pede confirmação antes de executar
```

---

## S3 — CLEANUP

### S3-01: Eliminar Duplicações (~4h)

#### Ações Exatas

| Ação | Arquivo | Linhas Removidas | Justificativa |
|---|---|---|---|
| DELETAR | `core/vps_langgraph/intent_classifier.py` | 571 | Substituído por `intent_classifier_llm.py` (294 linhas). Verificar que nenhum import referencia o antigo. |
| DELETAR | `core/vps_agent/semantic_memory.py` | 256 | Substituído por `learnings.py` (446 linhas). Verificar que `agent.py` não importa dele. |
| REMOVER | `core/vps_langgraph/state.py` — classe `AgentStateModern` | ~30 | Não é usada em nenhum lugar. `AgentState` é o typedef real. |
| REMOVER | `core/vps_langgraph/nodes.py` — bloco duplicado em node_execute | ~120 | Já resolvido em S1-02 quando o node_execute é reescrito. |
| DEPRECAR | `core/tools/system_tools.py` — TOOLS_REGISTRY | 0 (manter com comentário) | Manter como fallback até S2 completo, depois deletar. |

#### Passo a Passo

```bash
# 1. Verificar que ninguém importa intent_classifier (o antigo regex)
grep -rn "from.*intent_classifier import\|import intent_classifier" core/ telegram_bot/ tests/
# Se retornar algo, corrigir para intent_classifier_llm primeiro

# 2. Verificar que ninguém importa semantic_memory
grep -rn "from.*semantic_memory import\|import semantic_memory" core/ telegram_bot/ tests/
# Se retornar algo, corrigir para learnings primeiro

# 3. Deletar
rm core/vps_langgraph/intent_classifier.py
rm core/vps_agent/semantic_memory.py

# 4. Rodar testes
pytest tests/ -v

# 5. Rodar linter
ruff check .

# 6. Contar linhas
find core/ -name "*.py" -exec cat {} + | wc -l
# Alvo: < 11.000 (atual: 11.871)
```

#### Checkpoint S3-01
```
□ intent_classifier.py deletado
□ semantic_memory.py deletado
□ AgentStateModern removido de state.py
□ grep -r "intent_classifier\b" core/ retorna 0 (exceto LLM version)
□ pytest passa
□ ruff check . sem erros
□ Total de linhas < 11.000
```

---

### S3-02: Convergir Bot → Gateway (~2h)

#### Situação Atual

```
AGORA (2 entry points paralelos):

Telegram polling → bot.py → process_message_async → graph
                                    ↑
Gateway FastAPI webhook → adapters.py → process_message_async → graph
```

#### Alvo

```
DEPOIS (1 entry point):

Telegram webhook → Gateway FastAPI → process_message_async → graph
```

#### Como Fazer

1. No `telegram_bot/bot.py`, substituir polling por webhook que aponta para o Gateway
2. O Gateway (`core/gateway/main.py`) já tem endpoint `/webhook/telegram`
3. Configurar o bot do Telegram para enviar updates para `https://SEU_IP:8000/webhook/telegram`

#### Armadilha

O Gateway precisa de HTTPS para receber webhooks do Telegram. Se a VPS não tem certificado SSL, usar Telegram `setWebhook` com IP + self-signed ou manter polling mas via Gateway interno.

**Alternativa pragmática:** Manter bot.py com polling MAS internamente fazer chamadas ao Gateway em vez de chamar `process_message_async` direto. Isso unifica o ponto de processamento sem exigir HTTPS.

#### Checkpoint S3-02
```
□ Bot funciona via um único caminho de processamento
□ Telegram responde normalmente
```

---

## S4 — AUTONOMOUS LOOP

### S4-01: Schema + Tabelas (~4h)

#### Arquivo: `configs/migration-v2.sql`

```sql
-- Migration v2: Autonomous Loop Tables
-- Executar após init-db.sql

-- ============================================
-- PROPOSTAS DE AÇÃO
-- ============================================
CREATE TABLE IF NOT EXISTS agent_proposals (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,             -- 'user', 'cron', 'event', 'trigger_ram', 'trigger_error', 'trigger_schedule'
    trigger_type TEXT NOT NULL,       -- 'ram_high', 'error_repeated', 'schedule_due', 'manual'
    trigger_description TEXT NOT NULL,
    proposed_action TEXT NOT NULL,    -- Nome do skill a executar
    proposed_args JSONB DEFAULT '{}', -- Argumentos para o skill
    priority INT DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending', 'approved', 'rejected', 'executing', 'completed', 'failed', 'expired'
    )),
    cap_gate_result JSONB,           -- {ram_ok, security_ok, cost_ok, details}
    requires_approval BOOLEAN DEFAULT FALSE,
    approved_by TEXT,                 -- user_id que aprovou (se requer approval)
    result TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '1 hour')
);

-- ============================================
-- MISSÕES (propostas aprovadas em execução)
-- ============================================
CREATE TABLE IF NOT EXISTS agent_missions (
    id SERIAL PRIMARY KEY,
    proposal_id INT REFERENCES agent_proposals(id),
    mission_type TEXT NOT NULL,      -- 'tool_exec', 'monitoring', 'maintenance', 'self_improve'
    skill_name TEXT NOT NULL,        -- Skill do registry a executar
    skill_args JSONB DEFAULT '{}',
    steps JSONB DEFAULT '[]',        -- Lista de sub-passos
    current_step INT DEFAULT 0,
    status TEXT DEFAULT 'running' CHECK (status IN (
        'running', 'completed', 'failed', 'cancelled'
    )),
    result TEXT,
    events_emitted JSONB DEFAULT '[]',  -- Eventos gerados ao completar
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ============================================
-- POLÍTICAS DO AGENTE
-- ============================================
CREATE TABLE IF NOT EXISTS agent_policies (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'resource', 'security', 'cost', 'schedule', 'behavior'
    )),
    rule JSONB NOT NULL,
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger para updated_at
CREATE TRIGGER trg_policies_updated
    BEFORE UPDATE ON agent_policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- ÍNDICES
-- ============================================
CREATE INDEX IF NOT EXISTS idx_proposals_status ON agent_proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_created ON agent_proposals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_proposals_source ON agent_proposals(source);
CREATE INDEX IF NOT EXISTS idx_missions_status ON agent_missions(status);
CREATE INDEX IF NOT EXISTS idx_missions_proposal ON agent_missions(proposal_id);
CREATE INDEX IF NOT EXISTS idx_policies_category ON agent_policies(category);

-- ============================================
-- POLÍTICAS INICIAIS
-- ============================================
INSERT INTO agent_policies (name, category, rule, description) VALUES
    ('max_proposals_per_hour', 'resource', '{"max": 10}', 'Máximo de propostas por hora para evitar loops'),
    ('ram_threshold_warning', 'resource', '{"threshold_percent": 80}', 'Alertar quando RAM > 80%'),
    ('ram_threshold_critical', 'resource', '{"threshold_percent": 90}', 'Ação urgente quando RAM > 90%'),
    ('require_approval_dangerous', 'security', '{"levels": ["dangerous"]}', 'Comandos dangerous precisam de approval'),
    ('heartbeat_interval_minutes', 'schedule', '{"minutes": 30}', 'Intervalo do heartbeat em minutos'),
    ('max_daily_llm_cost', 'cost', '{"max_usd": 0.50}', 'Custo máximo diário com LLM')
ON CONFLICT (name) DO NOTHING;
```

#### Como Aplicar

```bash
psql -U postgres -d vps_agent -f configs/migration-v2.sql
```

#### Checkpoint S4-01
```
□ Tabelas agent_proposals, agent_missions, agent_policies criadas
□ 6 políticas iniciais inseridas
□ psql -c "SELECT * FROM agent_policies" retorna 6 rows
```

---

### S4-02: Autonomous Loop Engine (~8h)

#### Estrutura

```
core/autonomous/
├── __init__.py
├── loop.py          # O heartbeat principal
├── triggers.py      # Detectores de condições
└── cap_gates.py     # Verificações antes de aprovar
```

#### `core/autonomous/loop.py` — Estrutura Principal

```python
"""
Autonomous Loop — Heartbeat que transforma o agente de reativo para proativo.

Roda como background task no startup do bot.
A cada N minutos (configurável via policy):
  1. Verifica triggers (RAM, erros, schedules)
  2. Cria proposals para ações detectadas
  3. Passa proposals por Cap Gates (recursos, segurança, custo)
  4. Executa proposals aprovadas via Skill Registry
  5. Emite eventos que podem gerar novas proposals
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional

import structlog

from core.skills.registry import get_skill_registry

logger = structlog.get_logger()


class AutonomousLoop:
    def __init__(self, db_pool, telegram_notifier=None):
        self.db = db_pool
        self.notifier = telegram_notifier
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Inicia o loop como background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("autonomous_loop_started")

    async def stop(self):
        """Para o loop gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("autonomous_loop_stopped")

    async def _loop(self):
        """Loop principal — roda indefinidamente."""
        while self._running:
            try:
                interval = await self._get_heartbeat_interval()
                await self._heartbeat()
                await asyncio.sleep(interval * 60)  # interval em minutos
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("heartbeat_error", error=str(e))
                await asyncio.sleep(300)  # 5min de backoff em caso de erro

    async def _heartbeat(self):
        """Um ciclo do heartbeat."""
        logger.info("heartbeat_tick")
        
        # 1. Verificar triggers
        from .triggers import check_all_triggers
        triggers = await check_all_triggers()

        # 2. Criar proposals para cada trigger
        for trigger in triggers:
            proposal_id = await self._create_proposal(trigger)
            
            # 3. Cap Gate check
            from .cap_gates import check_cap_gates
            gate_result = await check_cap_gates(trigger, self.db)

            if gate_result["approved"]:
                # 4. Executar
                await self._execute_proposal(proposal_id, trigger)
            else:
                # Notificar que proposta foi rejeitada pelo cap gate
                await self._update_proposal_status(proposal_id, "rejected", gate_result)
                if gate_result.get("notify"):
                    await self._notify(
                        f"🔔 Proposta rejeitada: {trigger['description']}\n"
                        f"Motivo: {gate_result['reason']}"
                    )

    async def _get_heartbeat_interval(self) -> int:
        """Busca intervalo do heartbeat na tabela de policies."""
        # Default: 30 minutos
        # Ler de agent_policies se disponível
        return 30

    async def _create_proposal(self, trigger: dict) -> int:
        """Persiste proposta no PostgreSQL."""
        # INSERT INTO agent_proposals ...
        # Retorna proposal_id
        pass

    async def _execute_proposal(self, proposal_id: int, trigger: dict):
        """Executa proposta aprovada via Skill Registry."""
        registry = get_skill_registry()
        skill_name = trigger.get("skill")
        skill_args = trigger.get("args", {})

        result = await registry.execute_skill(skill_name, skill_args)

        # Atualizar status
        await self._update_proposal_status(proposal_id, "completed", {"result": result})

        # Notificar
        await self._notify(
            f"✅ Ação executada automaticamente:\n"
            f"📋 {trigger['description']}\n"
            f"📊 {result[:500]}"
        )

    async def _notify(self, message: str):
        """Envia notificação via Telegram."""
        if self.notifier:
            await self.notifier.send(message)
```

#### Checkpoint S4-02
```
□ Heartbeat roda sem erro por 5 minutos
□ Logs mostram "heartbeat_tick" a cada intervalo
□ Propostas são criadas na tabela agent_proposals
□ Notificações chegam no Telegram
```

---

### S4-03: 3 Triggers Iniciais (~4h)

#### `core/autonomous/triggers.py`

```python
"""Detectores de condições que disparam propostas."""

async def check_all_triggers() -> list:
    triggers = []
    triggers.extend(await check_ram_trigger())
    triggers.extend(await check_error_trigger())
    triggers.extend(await check_schedule_trigger())
    return triggers

async def check_ram_trigger() -> list:
    """RAM > 80% → propor limpeza."""
    with open("/proc/meminfo") as f:
        # Parse MemTotal e MemAvailable
        pass
    # Se uso > 80%: retornar trigger com skill="shell_exec", args={"command": "docker system prune -f"}
    return []

async def check_error_trigger() -> list:
    """Mesmo erro > 3x na última hora → propor investigação."""
    # SELECT trigger, COUNT(*) FROM learnings
    # WHERE category = 'execution_error' AND created_at > NOW() - INTERVAL '1 hour'
    # GROUP BY trigger HAVING COUNT(*) > 3
    return []

async def check_schedule_trigger() -> list:
    """Tarefa agendada vencida → propor execução."""
    # SELECT * FROM scheduled_tasks
    # WHERE status = 'pending' AND next_run <= NOW()
    return []
```

#### Checkpoint S4-03
```
□ RAM > 80% gera proposta no banco + mensagem no Telegram
□ Erro repetido gera proposta de investigação
□ Tarefa agendada vencida gera proposta de execução
```

---

## Checklist Final da Sprint

```
SEMANA 1 — SKILL REGISTRY
□ S1-01: core/skills/ com base.py, registry.py, 5 skills builtin
□ S1-02: node_execute delegando ao registry (<50 linhas)
□ S1-03: tests/test_skill_registry.py passando

SEMANA 2 — SKILLS + CLEANUP
□ S2-01: shell_exec funcional com classificação de segurança
□ S2-02: file_manager funcional com path validation
□ S2-03: web_search funcional com Brave API
□ S2-04: memory_query funcional com queries predefinidas
□ S2-05: self_edit funcional com backup + approval
□ S3-01: -800+ linhas de código morto eliminadas
□ S3-02: Bot convergido para gateway (ou alternativa pragmática)

SEMANA 3 — AUTONOMOUS LOOP
□ S4-01: Tabelas criadas, políticas inseridas
□ S4-02: Loop engine rodando como background task
□ S4-03: 3 triggers detectando condições reais

VALIDAÇÃO FINAL
□ Todos os 5 comandos Telegram antigos continuam funcionando
□ 5 skills novos respondem via Telegram
□ CI/CD verde
□ Total de linhas Python core/ < 12.000 (incluindo código novo)
□ Heartbeat roda sem crash por 24h
```

---

## Como Pedir Ajuda

Se travar em qualquer passo, forneça ao modelo assistente:

1. O arquivo `sprint-01-objetivo.md` (contexto geral)
2. Este arquivo (plano de implementação)
3. O **checkpoint específico** que falhou
4. O **erro exato** (log, traceback, ou comportamento inesperado)

Isso dá contexto suficiente para qualquer modelo retomar de onde parou.
