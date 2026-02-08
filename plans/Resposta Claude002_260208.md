Li o documento. Ele complementa a Fase 0 com um ângulo diferente: o anterior era sobre bugs (coisas quebradas), este é sobre capacidade (coisas que faltam). Vou responder tudo com clareza sobre o que fazer agora vs. o que é v2.
Mas primeiro, uma observação importante: este documento descreve o problema central de forma diferente do anterior. Deixa eu ser direto sobre isso.

O problema central descrito aqui — "o agente classifica intents mas não executa ações concretas" — não é um bug da Fase 0. É a razão de existir da Fase 2 inteira (Skill Registry + Skills Core + Action Classification). A Fase 0 resolve o que está quebrado. A Fase 2 resolve o que está faltando.
Dito isso, vou responder as 6 perguntas e entregar os 5 itens pedidos:
1. Arquitetura de Memória
A v2 já tem isso planejado em F3-04 (Hierarchical Memory), mas vou ser concreto sobre como funciona:
Três camadas, três propósitos:
Camada Episódica (JSONL) — "o que aconteceu recentemente"

Transcripts das últimas conversas (7 dias)
Formato: JSONL append-only, um arquivo por dia
Consulta: grep/busca textual simples
Custo RAM: ~0 (leitura sob demanda do disco)

Camada Semântica (Qdrant) — "o que aprendi"

Fatos importantes extraídos das conversas: "API X não funcionou, usar Y", "usuário prefere respostas curtas"
Embeddings via API (Voyage AI ou OpenAI, sem modelo local = 0 RAM)
Consulta: similarity search por embedding da mensagem atual
Custo RAM: ~400MB quando Qdrant está rodando (sob demanda)

Camada Perfil (PostgreSQL) — "quem é o usuário e o que é o sistema"

Preferências, configs, credenciais (encrypted), capabilities registradas
Formato: tabelas relacionais, sempre disponível
Custo RAM: ~200MB (já rodando)

Como distinguir recente vs. longo prazo:

Todo transcript vai para JSONL (episódico)
Um job periódico (F4-08 Memory Compaction) analisa transcripts >7 dias, extrai fatos importantes, salva no Qdrant (semântico), e arquiva o JSONL
Preferências detectadas ("usuário sempre pede em português") vão direto para PostgreSQL (perfil)

Como aprender com falhas:
PostgreSQL: tabela "learnings"
| id | category | trigger | lesson | created_at |
|----|----------|---------|--------|------------|
| 1  | api_failure | github_api_rate_limit | "Usar token PAT, não basic auth" | 2026-02-08 |
| 2  | tool_choice | web_search | "Brave Search > Google Custom Search para queries técnicas" | 2026-02-09 |
Quando o agente vai executar uma ação, consulta learnings relevantes antes. Isso é simples (SQL query) e não precisa de Qdrant.
Quando implementar: Não agora. PostgreSQL para learnings pode ser adicionado na Fase 0 como extensão do F0-02 (é uma tabela simples). Qdrant e compaction ficam para F3-04.

2. Execução Autônoma de Ferramentas
Esse é o cenário-chave do documento. Vou ser bem específico:
O fluxo correto para "Liste meus projetos no GitHub":
FASE ATUAL (v1 — quebrado):
  classify("Liste meus projetos no GitHub")
  → intent: "task" ou "self_improve"
  → respond: "Não tenho ferramenta direta para GitHub"
  → FIM (inútil)

APÓS FASE 2 (v2 — funcional):
  classify("Liste meus projetos no GitHub")
  → intent: "task"
  → skill_lookup("github", "list projects")
  → skill encontrado? 
     SIM → executar skill → retornar resultado
     NÃO → registrar necessidade → informar usuário:
            "Não tenho skill de GitHub ainda. Posso instalar? [Sim/Não]"
     → se Sim:
        → classificar ação: "instalar MCP" = nível DANGEROUS
        → pedir aprovação via Telegram (botão)
        → se aprovado: instalar, configurar, executar
        → se rejeitado: sugerir alternativa manual
A pergunta real é: isso deveria ser Fase 0 ou Fase 2?
Resposta: Fase 2. E por uma razão técnica concreta — para fazer isso funcionar, você precisa de:

Skill Registry (F2-01) — para o agente saber quais ferramentas tem
Action Classification (F2-03) — para classificar "instalar MCP" como dangerous
Approval Workflow (F2-03) — para pedir confirmação via Telegram

Sem esses três componentes, qualquer implementação de "execução autônoma" seria frágil e insegura. A Fase 0 garante que o fluxo básico funciona (classify → respond sem crash). A Fase 2 dá ao agente mãos para agir.
O que PODE ser feito na Fase 0 como melhoria mínima:
Fazer o node_generate_response ser mais inteligente quando detecta que o usuário quer algo que o agente não pode fazer:
python# Em vez de "não tenho ferramenta direta"
# Responder com plano de ação:
response = (
    "Ainda não tenho a ferramenta de GitHub instalada. "
    "Para implementar isso, vou precisar:\n"
    "1. Instalar o MCP de GitHub\n"
    "2. Configurar seu token PAT\n"
    "3. Testar a conexão\n"
    "Quer que eu registre isso como próxima melhoria?"
)
```

Isso é cosmético (muda a resposta, não a capacidade), mas já é melhor UX.

---

### 3. Hierarquia de Ferramentas

A hierarquia proposta no documento está boa. Vou refinar com base no que já temos no roadmap:
```
NÍVEL 0 — SAFE (automático, sem confirmação)
├── Ler arquivos
├── Consultar PostgreSQL/Redis
├── Checar status de containers
├── Listar processos
└── Consultar memória/learnings

NÍVEL 1 — MODERATE (executa, mas loga tudo)
├── Criar/editar arquivos em diretórios permitidos
├── Instalar pacotes pip/apt (de whitelist)
├── Chamadas a APIs externas (GitHub, web search)
├── Enviar mensagens por outros canais
└── Criar containers Docker (com resource limits)

NÍVEL 2 — DANGEROUS (requer aprovação via Telegram)
├── Deletar arquivos/containers
├── Executar scripts arbitrários
├── Modificar configurações do sistema
├── Instalar novos MCPs
├── Modificar código do próprio agente
└── Operações de git (commit, push, merge)

NÍVEL 3 — FORBIDDEN (nunca, nem com aprovação)
├── rm -rf /
├── Desabilitar firewall
├── Expor portas sem autenticação
├── Modificar credenciais de root
└── Desabilitar o próprio agente
Implementação: Isso é o job F2-03 (Action Classification & Approval). Cada skill declara seu nível no config.yaml:
yaml# skills/github-api/config.yaml
name: github-api
level: moderate  # executa sem perguntar, mas loga
actions:
  list_repos: safe
  create_repo: moderate
  delete_repo: dangerous  # override por ação específica
O approval flow via Telegram:
python# Quando ação é DANGEROUS:
await telegram.send_message(
    admin_chat_id,
    f"🔴 Ação DANGEROUS solicitada:\n"
    f"Skill: {skill_name}\n"
    f"Ação: {action}\n"
    f"Contexto: {user_message}\n",
    reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Aprovar", callback_data=f"approve_{action_id}")],
        [InlineKeyboardButton("❌ Rejeitar", callback_data=f"reject_{action_id}")],
    ])
)
# Timeout de 5 minutos — se não aprovar, rejeita automaticamente
```

---

### 4. Integração MCP

Preciso ser cético aqui porque MCP é uma área onde há muito hype e pouca maturidade.

**Estado atual:** Você tem `mcp_server.py` (FastAPI-MCP), mas isso faz do AgentVPS um **MCP server** (expõe ferramentas para outros). O que você quer é o contrário: o AgentVPS como **MCP client** (consome ferramentas de outros servidores MCP).

**Realidade sobre MCPs em fevereiro 2026:**
- MCPs de GitHub, Brave Search, filesystem existem e funcionam
- A maioria roda como processos separados (cada um consome RAM)
- Com 2.4GB, **não dá para ter muitos MCPs rodando simultaneamente**

**Abordagem recomendada (pragmática):**

Em vez de MCPs para tudo, usar uma hierarquia de complexidade:
```
PRIORIDADE 1 — Implementar como skills nativos (sem MCP overhead):
├── shell-exec (subprocess.run — 0 RAM extra)
├── file-manager (os/pathlib — 0 RAM extra)
├── web-search (httpx → Brave Search API — 0 RAM extra)
├── github-api (httpx → GitHub REST API — 0 RAM extra)
└── memory-query (asyncpg → PostgreSQL — 0 RAM extra)

PRIORIDADE 2 — Usar MCPs apenas quando a alternativa nativa é ruim:
├── Kilocode/Claude Code (MCP faz sentido — CLI complexo)
└── n8n (já roda via Docker, API REST é suficiente)

PRIORIDADE 3 — Avaliar caso a caso:
└── Qualquer ferramenta nova: primeiro tentar skill nativo,
    só usar MCP se o skill nativo for muito complexo
Por que skills nativos > MCPs?

0 RAM extra (roda no processo do agente)
Sem overhead de comunicação JSON-RPC
Mais fácil de debugar
Mais fácil de testar

MCPs fazem sentido quando o serviço é complexo o suficiente para justificar um processo separado.
Descoberta de MCPs disponíveis:
python# No Skill Registry (F2-01), cada skill pode ser:
# - native: função Python no processo
# - mcp: servidor MCP externo
# - docker: container sob demanda

# skills/registry.py
class SkillType(Enum):
    NATIVE = "native"      # Função Python, 0 RAM extra
    MCP = "mcp"            # Servidor MCP externo
    DOCKER = "docker"      # Container sob demanda
```

---

### 5. Resource Management (RAM)

Budget atualizado com cenários:
```
CENÁRIO A — Modo Normal (sem Qdrant, sem n8n)
  OS + sistema:     ~200 MB
  PostgreSQL:       ~200 MB
  Redis:            ~50 MB
  Python (agente):  ~300 MB
  ─────────────────────────
  Total:            ~750 MB
  Livre:            ~1650 MB
  
CENÁRIO B — Com Qdrant (busca semântica ativa)
  Cenário A:        ~750 MB
  Qdrant:           ~400 MB
  ─────────────────────────
  Total:            ~1150 MB
  Livre:            ~1250 MB

CENÁRIO C — Qdrant + n8n (automação ativa)
  Cenário B:        ~1150 MB
  n8n:              ~300 MB
  ─────────────────────────
  Total:            ~1450 MB
  Livre:            ~950 MB

CENÁRIO D — MÁXIMO (tudo ligado)
  Cenário C:        ~1450 MB
  Kilocode/outro:   ~500 MB
  ─────────────────────────
  Total:            ~1950 MB
  Livre:            ~450 MB ⚠️ ZONA DE RISCO
Regras de gestão:

Mínimo livre: 500 MB. Se livre < 500MB, recusar novas ferramentas e desligar a menos crítica
Qdrant: sob demanda. Subir quando precisa de busca semântica, manter por 5min, descer se inativo
n8n: sob demanda. Só subir quando uma automação precisa rodar
Nunca cenário D sem intervenção manual

Quando recusar request por falta de recursos:
pythonasync def check_resources_before_skill(skill: Skill) -> bool:
    free_ram = get_free_ram_mb()
    skill_needs = skill.config.ram_estimate_mb
    
    if free_ram - skill_needs < 500:  # margem mínima
        await telegram.send(
            f"⚠️ RAM insuficiente para {skill.name}.\n"
            f"Livre: {free_ram}MB, Precisa: {skill_needs}MB\n"
            f"Desligar algo primeiro? [Qdrant/n8n/Cancelar]"
        )
        return False
    return True
```

---

### 6. Self-Improvement Autônomo

**Na Fase 0:** O self_improve apenas **identifica e informa**. Não executa nada.

**Na v2 (F4-04):** O pipeline completo:
```
ETAPA 1 — DETECTAR (automático)
  ├── Analisar logs de "não tenho ferramenta para X"
  ├── Contar frequência de pedidos não atendidos
  └── Rankear por impacto (quantas vezes pedido × complexidade)

ETAPA 2 — PLANEJAR (automático)
  ├── Pesquisar como implementar (web search + learnings)
  ├── Gerar plano de implementação
  ├── Estimar tempo e recursos
  └── Enviar plano para aprovação: "Detectei que você pede GitHub 5x/semana. 
       Posso implementar skill GitHub em ~2h. Aprovar?"

ETAPA 3 — IMPLEMENTAR (após aprovação humana)
  ├── Criar branch: self-improve/add-github-skill
  ├── Gerar código do skill (em sandbox Docker)
  ├── Rodar testes automatizados
  └── Se testes passam: commit + enviar para review

ETAPA 4 — VALIDAR (após aprovação humana)
  ├── Merge para main
  ├── Recarregar Skill Registry
  ├── Testar end-to-end com mensagem real
  └── Registrar learning: "GitHub skill implementado, funcional"

ETAPA 5 — DOCUMENTAR (automático)
  ├── Atualizar TOOLS.md
  ├── Adicionar ao CLI: agent-cli skills list
  └── Logar no audit trail
```

**Diferença crucial com a v1:** Na v1, `self_improve` tenta fazer tudo de uma vez e falha silenciosamente. Na v2, cada etapa tem checkpoint e validação. Se falhar em qualquer ponto, loga, notifica, e para.

---

## Os 5 Entregáveis Pedidos

### Entregável 1 — Diagrama Atual vs. Proposta
```
═══ ATUAL (v1 — quebrado) ═══

Telegram → Bot → classify → [intent?]
                               ├── chat → LLM → resposta genérica
                               ├── question → LLM → resposta genérica  
                               ├── command → execute (shell) → resposta
                               ├── task → execute (limitado) → resposta
                               └── self_improve → ??? → NULL ← BUG

Problemas: sem tools, sem approval, sem fallback, self_improve quebrado


═══ PROPOSTA (v1.5 = Fase 0 estabilizada) ═══

Telegram → Bot → classify → load_context → plan → [intent?]
                                                     ├── chat → LLM → respond → save_memory
                                                     ├── question → LLM → respond → save_memory
                                                     ├── command → execute → respond → save_memory
                                                     ├── task → execute → respond → save_memory
                                                     └── self_improve → check_capabilities 
                                                                         → respond (informa plano)
                                                                         → save_memory

Diferença: fluxo funcional, sem NULL, sem crash. Mas ainda sem tools reais.


═══ PROPOSTA (v2 — Fases 1-4) ═══

Gateway (FastAPI)
  ├── Telegram Adapter
  ├── WhatsApp Adapter (Evolution API)
  └── Webhook/API Adapter
       ↓
Session Router → Context Window Guard → LLM Provider (multi-model)
       ↓
Brain (LangGraph)
  ├── Prompt Composer (dinâmico)
  ├── Reasoning Validator (step-level)
  └── Skill Registry → [skill encontrado?]
       ├── SIM → classificar nível → [safe/moderate/dangerous]
       │          ├── safe → executar → respond
       │          ├── moderate → executar + log → respond
       │          └── dangerous → approval Telegram → executar/rejeitar → respond
       └── NÃO → [self-improve pipeline]
                   → detectar necessidade
                   → planejar implementação
                   → pedir aprovação
                   → implementar em sandbox
                   → validar + deploy
```

### Entregável 2 — Fluxo "Usuário Pede Algo Novo"
```
Mensagem: "Liste meus projetos no GitHub"

1. Gateway recebe mensagem via Telegram
2. Session Router identifica sessão do usuário
3. Context Window Guard carrega contexto relevante (últimas msgs + learnings)
4. Brain classifica: intent = "task", tool_needed = "github"
5. Skill Registry busca: skills.search("github") → NÃO ENCONTRADO
6. Brain gera resposta intermediária:
   "Não tenho skill de GitHub ainda. Posso instalar?"
   [Botão: Sim] [Botão: Não, faça manualmente]

SE USUÁRIO CLICA "SIM":
7. Action Classification: instalar_skill = DANGEROUS
8. Approval: já aprovado pelo "Sim" do passo 6
9. Self-Improve Pipeline:
   a. Pesquisa: "como acessar GitHub API via Python"
   b. Gera skill: skills/github-api/handler.py
   c. Testa em sandbox Docker
   d. Se teste OK: registra no Skill Registry
   e. Executa skill com a mensagem original
10. Resposta: "Seus projetos: [lista]"
11. Learning salvo: "GitHub skill funcional, usar httpx + REST API"

SE USUÁRIO CLICA "NÃO":
7. Brain sugere alternativa:
   "OK. Você pode rodar manualmente: gh repo list --json name"
8. FIM
Entregável 3 — Hierarquia de Approvals
NívelClassificaçãoAçãoExemploControle0SAFELeitura, consultaLer arquivo, query DB, checar statusAutomático1MODERATEEscrita limitadaCriar arquivo, chamar API, pip installAuto + log2DANGEROUSEscrita destrutiva / auto-modificaçãoDeletar, instalar MCP, modificar código, git pushAprovação Telegram com timeout 5min3FORBIDDENDestruição irreversívelrm -rf, desabilitar firewall, expor portasBloqueado sempre
Implementação do approval:

Timeout: 5 minutos (configurável)
Default se timeout: REJEITAR
Log: toda decisão (aprovada/rejeitada/timeout) vai para audit trail
Override: comando /mode admin permite moderate sem perguntar (dangerous continua pedindo)

Entregável 4 — Priorização de Ferramentas
Em ordem de implementação:
PrioridadeSkillTipoRAM ExtraFase1shell-execNative0F2-022file-managerNative0F2-023memory-queryNative0F2-024web-search (Brave API)Native0F2-025self-edit (código próprio)Native0F2-026github-apiNative0Após F2-027qdrant-searchNative400MB (Qdrant)F3-048n8n-triggerDocker300MB (n8n)F3-10
Por que shell-exec primeiro? Porque com shell-exec + file-manager o agente pode fazer quase tudo — é o "canivete suíço". gh repo list é um shell command. curl é um shell command. A maioria das tarefas no VPS se resolve com shell.
Por que web-search antes de github-api? Porque web-search é útil para mais cenários (pesquisa geral, troubleshooting, self-improvement research).
Entregável 5 — Métricas de Sucesso
Fase 0 (Estabilização):

✅ 5/5 intents retornam resposta (não None)
✅ 0 crashes em 24h de operação
✅ CI/CD verde
✅ Tempo médio de resposta < 5s para chat/question

Fase 2 (Skills funcionais):

✅ 5 skills core operacionais
✅ Novo skill criável em < 30 minutos (por humano)
✅ 0 ações DANGEROUS executadas sem aprovação
✅ WhatsApp funcional como segundo canal

Fase 3 (Inteligência):

✅ Custo médio < $0.05/conversa
✅ 0 downtime percebido de LLM (failover funcionando)
✅ RAG query < 5s
✅ Cache hit rate > 30% em perguntas repetitivas

Fase 4 (Autonomia):

✅ 0 self-improvements sem aprovação humana
✅ Multi-agent delegation funcional
✅ Skill auto-gerado passa em testes automatizados


A mensagem principal é: seu documento descreve exatamente o que as Fases 2-4 resolvem. A Fase 0 é "parar de crashar". As Fases 2-4 são "começar a ser útil de verdade". A ordem importa — construir skills em cima de um grafo que retorna None é construir em areia.