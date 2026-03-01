# PLANO DE IMPLANTAÇÃO — FASE 0: ESTABILIZAÇÃO v1

## Objetivo
Corrigir bugs críticos que impedem o funcionamento básico do Self-Improvement Agent.
**Princípio:** "Consertar, não construir" — mínimo necessário para funcionar.

---

## 📋 Jobs da FASE 0

### F0-01: Cleanup de Código (4h, P0)
**Objetivo:** Eliminar duplicação, consolidar em `vps_langgraph/`

**Arquivos para deletar:**
```
core/graph.py              ← versão antiga
core/nodes.py              ← versão antiga
core/state.py              ← versão antiga
core/memory.py             ← versão antiga
core/semantic_memory.py    ← versão antiga
core/vps_agent/graph.py    ← versão antiga
core/vps_agent/nodes.py    ← versão antiga
core/vps_agent/semantic_memory.py
```

**Ações:**
1. Verificar diffs antes de deletar
2. Deletar arquivos duplicados
3. Limpar todos os `__pycache__`
4. Adicionar `__pycache__/` e `*.pyc` ao `.gitignore`
5. Atualizar imports em `telegram-bot/bot.py`

**Teste:**
```bash
find /opt/vps-agent/core -name "*.py" | grep -E "(graph|nodes|state|memory)" | sort
# Deve mostrar apenas arquivos em vps_langgraph/
```

---

### F0-02: Fix Graph Flow self_improve (6h, P0)
**Objetivo:** Corrigir roteamento para que `self_improve` passe por `check_capabilities` → `respond`

**Correção 1 — graph.py:**
```python
# Mudar de:
"self_improve": "respond"

# Para:
"self_improve": "check_capabilities"
```

**Correção 2 — nodes.py (`node_generate_response`):**
```python
# Adicionar "self_improve" na condição:
elif intent in ["chat", "question", "self_improve"]:
    response = generate_response_sync(...)
```

**Fluxo correto:**
```
classify → load_context → plan → check_capabilities → self_improve → respond → save_memory
```

**Teste:**
```bash
# Enviar mensagem "você consegue melhorar você mesmo?" via Telegram
# Verificar se retorna resposta (não None)
```

---

### F0-03: Fix timezone + Validação (1h, P0)
**Objetivo:** Confirmar import `timezone` em `capabilities/registry.py`

**Correção:**
```python
# Em core/capabilities/registry.py:
from datetime import datetime, timezone

self.created_at = datetime.now(timezone.utc)
```

**Teste:**
```bash
cd /opt/vps-agent
source core/venv/bin/activate
python3 -c "from core.capabilities.registry import Capability; print('OK')"
```

---

### F0-04: Fix CI/CD (4h, P0)
**Objetivo:** Corrigir imports no GitHub Actions

**Ações:**
1. Garantir `PYTHONPATH` inclui apenas `core/vps_langgraph/`
2. Verificar `requirements.txt` completo
3. Adicionar `.env.example` se necessário

**Teste:**
```bash
# Rodar locally
python3 -m pytest tests/ -v
# Deve passar sem import errors
```

---

### F0-05: Testes Básicos end-to-end (6h, P1)
**Objetivo:** Escrever 5 testes cobrindo os 5 intents

**Testes necessários:**
```python
# tests/test_intents.py
@pytest.mark.asyncio
async def test_intent_command():
    result = await process_message_async("user1", "/status")
    assert result.get("response") is not None

@pytest.mark.asyncio
async def test_intent_task():
    result = await process_message_async("user1", "me mostre os containers")
    assert result.get("response") is not None

@pytest.mark.asyncio
async def test_intent_question():
    result = await process_message_async("user1", "qual a RAM disponível?")
    assert result.get("response") is not None

@pytest.mark.asyncio
async def test_intent_chat():
    result = await process_message_async("user1", "oi, tudo bem?")
    assert result.get("response") is not None

@pytest.mark.asyncio
async def test_intent_self_improve():
    result = await process_message_async("user1", "você consegue criar uma nova ferramenta?")
    assert result.get("response") is not None
```

---

### F0-06: Telegram Log Handler (3h, P1)
**Objetivo:** Enviar erros CRITICAL/ERROR para Telegram do admin

**Implementação:**
```python
# core/telegram_log_handler.py
import logging
from telegram import Bot

class TelegramLogHandler(logging.Handler):
    def __init__(self, token, chat_id):
        super().__init__()
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.rate_limit = 60  # segundos
        
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.send_telegram(record.getMessage())
```

---

### F0-07: Documentação Mínima (2h, P2)
**Objetivo:** Atualizar README com estrutura real pós-cleanup

---

## ✅ Critérios de Saída FASE 0

- [ ] Todos os 5 intents retornam response via Telegram
- [ ] Zero NameError: timezone nos logs
- [ ] Apenas 1 cópia de cada arquivo (sem duplicatas)
- [ ] pytest verde com 5+ testes
- [ ] `__pycache__/` no .gitignore
- [ ] Erros CRITICAL notificados via Telegram

---

## 📅 Próximas Fases (v2 Roadmap)

Após FASE 0 completa:

| Fase | Nome | Jobs | Entrega |
|------|------|------|---------|
| F1 | Fundação | 12 | Gateway + Sessões + Proteções |
| F2 | Skills & Segurança | 10 | Skills modulares + WhatsApp |
| F3 | Inteligência | 11 | Failover + RAG + Cache |
| F4 | Autonomia | 11 | Multi-agent + Self-improvement |

**Total v2:** 44 jobs | ~508h | 13-17 semanas
