# Guia de Contribuição

Obrigado pelo interesse em contribuir para o VPS-Agente v2! Este documento fornece diretrizes e instruções para contribuir.

## 📋 Índice

- [Código de Conduta](#código-de-conduta)
- [Como Contribuir](#como-contribuir)
- [Processo de Desenvolvimento](#processo-de-desenvolvimento)
- [Padrões de Código](#padrões-de-código)
- [Comandos Úteis](#comandos-úteis)
- [Perguntas Frequentes](#perguntas-frequentes)

---

## 📜 Código de Conduta

Este projeto segue o [Contributor Covenant](https://www.contributor-covenant.org/pt-br/version/2/1/code_of_conduct/). Ao participar, você concorda em manter um ambiente acolhedor e inclusivo.

## 🤝 Como Contribuir

### Reportando Bugs

1. Verifique se o bug já foi reportado em [Issues](../../issues)
2. Se não, abra uma nova issue com:
   - Título claro e descritivo
   - Passos para reproduzir
   - Comportamento esperado vs. atual
   - Screenshots (se aplicável)
   - Logs de erro

### Sugerindo Melhorias

1. Verifique se a sugestão já existe em [Issues](../../issues)
2. Abra uma nova issue com:
   - Descrição clara da melhoria
   - Caso de uso
   - Solução proposta (opcional)
   - Benefícios esperados

### Pull Requests

1. Fork o repositório
2. Crie uma branch para sua feature: `git checkout -b feature/minha-feature`
3. Commit suas mudanças: `git commit -m 'feat: adiciona nova feature'`
4. Push para a branch: `git push origin feature/minha-feature`
5. Abra um Pull Request

---

## 🔄 Processo de Desenvolvimento

### 1. Configuração do Ambiente

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/vps-agente-v2.git
cd vps-agente-v2

# Configure ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt
```

### 2. Workflow de Desenvolvimento

```
┌─────────────────────────────────────────────────────┐
│  1. Criar/selecionar issue                          │
│           ↓                                         │
│  2. Criar branch: feature/fix/minha-feature        │
│           ↓                                         │
│  3. Desenvolver e testar localmente                │
│           ↓                                         │
│  4. Commit com Conventional Commits                │
│           ↓                                         │
│  5. Push e abrir Pull Request                      │
│           ↓                                         │
│  6. Code Review                                    │
│           ↓                                         │
│  7. Merge e deploy                                  │
└─────────────────────────────────────────────────────┘
```

### 3. Convenções de Commit

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>(<escopo>): <descrição>

[corpo opcional]

[footer opcional]
```

**Tipos:**
- `feat`: Nova funcionalidade
- `fix`: Correção de bug
- `docs`: Mudanças na documentação
- `style`: Formatação, ponto-e-vírgula, etc.
- `refactor`: Refatoração de código
- `test`: Adição de testes
- `chore`: Tarefas de manutenção

**Exemplos:**
```
feat(bot): adiciona comando /status
fix(memory): corrige conexão com PostgreSQL
docs(readme): atualiza Quick Start
refactor(agent): simplifica workflow do LangGraph
```

---

## 📝 Padrões de Código

### Python

```python
"""
Módulo de exemplo.

Descrição do que o módulo faz.
"""

from typing import TypedDict, Optional
from datetime import datetime


class AgentState(TypedDict):
    """Estado do agente."""
    message: str
    context: dict
    timestamp: datetime


def process_message(message: str) -> str:
    """
    Processa uma mensagem e retorna resposta.
    
    Args:
        message: Mensagem de entrada
        
    Returns:
        Resposta processada
    """
    # Implementação aqui
    return response
```

**Regras:**
- Python 3.11+
- Type hints obrigatórios
- Docstrings para todas as funções públicas
- Máximo 100 linhas por função
- Limite de 120 caracteres por linha

### Docker

```yaml
# Sempre use versões fixas de imagem
services:
  postgres:
    image: postgres:16  # ✅ Correto
    # image: postgres:latest  # ❌ Errado
```

### Configurações

```yaml
# Prefira YAML para arquivos de configuração
# Use .env para variáveis sensíveis
# Nunca hardcode credenciais
```

### Commits

```bash
# Mensagens em português ou inglês (escolha uma e mantenha)
feat(bot): add new command     # ✅ Inglês
feat(bot): adiciona comando    # ✅ Português
fix(bot): add new command      # ❌ Misturado
```

---

## 🛠️ Comandos Úteis

### Docker

```bash
# Ver status dos containers
docker ps

# Ver logs
docker logs -f <container>

# Reiniciar serviço
docker compose -f configs/docker-compose.core.yml restart

# Ver uso de memória
docker stats
```

### PostgreSQL

```bash
# Conectar ao banco
psql -h localhost -U postgres -d vps_agent

# Ver tabelas
\dt

# Ver estrutura da tabela
\d agent_memory
```

### Redis

```bash
# Conectar ao Redis
redis-cli

# Ver chaves
KEYS *

# Ver valor
GET <key>
```

### Claude/Kilocode CLI

```bash
# Status do CLI
agent-cli status

# Executar tarefa
agent-cli run 'Analise o código e sugira melhorias'

# Alternar entre CLIs
agent-cli use claude
agent-cli use kilocode
```

---

## ❓ Perguntas Frequentes

### Posso usar este projeto em produção?

Este é um projeto experimental/em desenvolvimento. Use por sua própria conta e risco.

### Como reportar vulnerabilidades de segurança?

Não abra issues públicas. Envie um email direto ao mantenedor.

### Posso usar este código em outros projetos?

Sim, sob licença MIT. Consulte [LICENSE](../LICENSE).

### Como posso ajudar com a documentação?

Basta abrir um Pull Request com as melhorias. Documentação é muito bem-vinda!

---

## 📞 Suporte

- **Issues:** [GitHub Issues](../../issues)
- **Discussões:** [GitHub Discussions](../../discussions)
- **Email:** contato@exemplo.com

---

## 🙏 Agradecimentos

Obrigado por considerar contribuir para o VPS-Agente v2! Cada contribuição ajuda a tornar este projeto melhor.

**Feito com 💻 por contribuidores como você.**
