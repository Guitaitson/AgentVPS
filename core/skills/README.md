# Skill Registry — Sistema de Skills Dinâmicos

O Skill Registry é o sistema que permite ao AgentVPS executar ações reais na VPS de forma modular e extensível.

## Estrutura

```
core/skills/
├── __init__.py          # Exports públicos
├── base.py              # SkillBase class
├── registry.py          # SkillRegistry (descoberta automática)
├── _builtin/            # Skills do sistema (migrados de system_tools)
│   ├── ram/
│   ├── containers/
│   ├── system_status/
│   ├── check_postgres/
│   └── check_redis/
└── README.md           # Este arquivo
```

## Como Criar um Novo Skill

1. **Crie um diretório** em `core/skills/` (ex: `core/skills/meu_skill/`)

2. **Crie o arquivo `handler.py`** com uma classe que herda `SkillBase`:

```python
from core.skills.base import SkillBase, SkillConfig

class MeuSkill(SkillBase):
    async def execute(self, args=None) -> str:
        # Sua lógica aqui
        return "Resultado"
```

3. **Crie o arquivo `config.yaml`** com a metadata:

```yaml
name: meu_skill
description: "O que este skill faz"
version: "1.0.0"
security_level: safe  # safe, moderate, dangerous, forbidden
triggers:
  - palavra-chave que ativa este skill
  - outra palavra
parameters: {}
max_output_chars: 2000
timeout_seconds: 30
enabled: true
```

4. **O registry descobre automaticamente** no startup. Não precisa editar nenhum outro arquivo.

## Níveis de Segurança

| Level | Descrição | Requer Approval |
|-------|-----------|----------------|
| `safe` | Leitura apenas, sem efeitos colaterais | Não |
| `moderate` | Executa + log | Não |
| `dangerous` | Modifica o sistema | Sim |
| `forbidden` | Bloqueado | Nunca |

## Usando o Registry

```python
from core.skills import get_skill_registry

# Obter instância
registry = get_skill_registry()

# Listar skills
skills = registry.list_skills()
print(f"Total: {len(skills)} skills")

# Encontrar skill por trigger
skill = registry.find_by_trigger("quanta ram?")
print(skill.name)  # "get_ram"

# Executar skill
result = await registry.execute_skill("get_ram")
print(result)
```

## API

### SkillRegistry

- `discover_and_register()`: Descobre skills em todos os diretórios configurados
- `get(name)`: Retorna skill pelo nome
- `list_skills()`: Lista todos os skills registrados
- `find_by_trigger(text)`: Encontra skill que corresponde ao texto
- `execute_skill(name, args)`: Executa um skill

### SkillBase

- `execute(args)`: Método abstrato que executa o skill
- `validate_args(args)`: Valida argumentos antes de executar
- `name`: Propriedade com o nome do skill
- `security_level`: Propriedade com o nível de segurança
