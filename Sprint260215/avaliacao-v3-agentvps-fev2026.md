# Avaliação Técnica v3 — AgentVPS — 15 Fevereiro 2026

## Contexto

Terceira avaliação após Sprint 260214 (Skill Registry + 10 Skills + Autonomous Engine). O projeto foi reavaliado lendo todos os 77 arquivos Python (~16.930 linhas) no repositório GitHub.

---

## 1. O Que Mudou Desde a v2

### Entregas Concretas

| Item Planejado | Status | Observação |
|---|---|---|
| S1: Skill Registry (base.py + registry.py) | ✅ Entregue | 203 linhas, auto-discovery funcional |
| S1: Migrar 5 tools builtin para skills | ✅ Entregue | ram, containers, system_status, check_postgres, check_redis |
| S2-01: shell_exec | ✅ Entregue | 397 linhas com classificação SAFE/MODERATE/DANGEROUS/FORBIDDEN |
| S2-02: file_manager | ✅ Entregue | 188 linhas com path validation |
| S2-03: web_search | ✅ Entregue | 97 linhas com Brave Search API |
| S2-04: memory_query | ✅ Entregue | 124 linhas |
| S2-05: self_edit | ✅ Entregue | 95 linhas |
| S3-01: Deletar intent_classifier.py (571 linhas) | ⚠️ Parcial | Conteúdo substituído por comentário DEPRECATED (11 linhas), mas arquivo NÃO deletado |
| S3-01: Deletar semantic_memory.py (256 linhas) | ⚠️ Parcial | Conteúdo substituído por comentário DEPRECATED (9 linhas), mas arquivo NÃO deletado |
| S3-01: Remover system_tools.py TOOLS_REGISTRY | ❌ Não feito | Ainda 434 linhas, TOOLS_REGISTRY intacto |
| S3-02: Convergir Bot → Gateway | ❌ Não feito | Dois entry points coexistem |
| S4-01: Tabelas PostgreSQL (proposals, missions, policies) | ❌ Não feito | init-db.sql inalterado |
| S4-02: Autonomous Loop engine | ⚠️ Parcial | engine.py existe (372 linhas) mas diverge do plano. Sem tabelas PostgreSQL. |
| S4-03: 3 Triggers iniciais | ⚠️ Parcial | 6 triggers registrados mas não usam proposals/missions/cap gates |
| S1-03: test_skill_registry.py | ✅ Entregue | 175 linhas |
| node_execute refatorado | ✅ Entregue | Delegação ao registry funcional |

### Métricas Comparativas

| Métrica | Avaliação v2 | Avaliação v3 | Mudança |
|---|---|---|---|
| Total linhas Python | 15.347 | 16.930 | +1.583 (+10%) |
| Linhas core/ | 11.871 | 13.279 | +1.408 (+12%) |
| Linhas testes/ | 2.419 | 2.594 | +175 (+7%) |
| Arquivos Python core/ | ~40 | 77 | +37 (skills dirs) |
| Skills funcionais | 5 (hardcoded) | 10 (via registry) | +5 novas capacidades |
| Commits | 21 | 22 | +1 (squashed?) |

---

## 2. Problemas Críticos Encontrados

### 🔴 CRÍTICO: API Key Exposta no Código

```python
# core/skills/_builtin/web_search/handler.py, linha 10
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "BSA1oVa6QVwZf5E3lCRo1h19cmY9Ywo")
```

Uma API key real está hardcoded como valor default e commitada no GitHub público. Isso deve ser corrigido imediatamente — remover o default, revogar a key atual, gerar uma nova, e usar apenas variáveis de ambiente.

### 🔴 CRÍTICO: shell_exec é um Mega-Módulo Anti-Pattern (397 linhas)

O `shell_exec/handler.py` cresceu para 397 linhas — mais que o dobro do registry inteiro (203 linhas). Contém:

1. Classificação de segurança por regex (~50 linhas) — OK
2. Execução de subprocesso (~40 linhas) — OK
3. Formatação de resposta conversacional com 15 blocos if/elif hardcoded (~120 linhas) — PROBLEMA
4. Extração de nome de programa com patterns hardcoded (~30 linhas) — PROBLEMA
5. Interpretação LLM para converter linguagem natural em comando (~100 linhas) com heurísticas hardcoded (~50 linhas) — PROBLEMA FUNDAMENTAL

O skill faz 3 trabalhos distintos: interpretar a intenção, executar o comando, e formatar a resposta. Isso deveria ser responsabilidade do grafo LangGraph (interpretar) e do LLM (formatar), não de um único handler.

Pior: a função `_interpret_and_generate_command` reinventa o trabalho que o `node_classify_intent` e o `node_plan` já fazem. O grafo classifica a intenção com LLM → planeja qual skill usar → executa o skill. Mas dentro do skill, todo esse trabalho é refeito com heurísticas hardcoded + outra chamada LLM. São duas chamadas LLM por mensagem, duplicando custo e latência.

### Este é exatamente o problema que você identificou na sua mensagem — "estou criando botões pré-codificados."

Cada bloco `if "tem o" in user_input_lower` dentro do shell_exec é um botão hardcoded. Quando alguém pedir "tem o Node.js?" funciona. Quando pedir "Node.js está na máquina?" não funciona. O agente deveria entender qualquer formulação da mesma pergunta via LLM, não via string matching.

### 🟡 IMPORTANTE: Autonomous Engine Divergiu do Blueprint

O plano definia: tabelas PostgreSQL → proposals → cap gates → missões → eventos. O que foi implementado: triggers com `condition: lambda → True` que rodam em loop sem proposal/cap gate/evento. Os triggers são cron jobs simples, não o loop autônomo de 6 passos.

Exemplo do health_check trigger:
```python
Trigger(
    name="health_check",
    condition=lambda: True,   # Sempre roda
    action=health_check_action,
    interval=60,              # A cada 60 segundos
)
```

Isso é um cron, não um agente autônomo. Não cria proposals. Não passa por cap gates. Não emite eventos. Não re-trigera. Falta a arquitetura inteira que diferencia "cron job" de "autonomous loop."

O trigger `ram_high` é o mais próximo do blueprint: verifica condição (RAM > 80%), salva proposal no Redis. Mas não existe nenhum sistema que processa essa proposal, verifica cap gates, ou a transforma em missão.

### 🟡 IMPORTANTE: node_security_check Escreve Debug Log em Arquivo

```python
# nodes.py, dentro de node_security_check
with open("/tmp/security_debug.log", "a") as f:
    f.write(json.dumps(debug_info) + "\n")
```

Isso está no fluxo principal de cada mensagem. Em produção, esse arquivo cresce indefinidamente. Além disso, informações potencialmente sensíveis (comandos do usuário) são escritas em plaintext em /tmp.

### 🟡 IMPORTANTE: system_tools.py Não Foi Limpo

434 linhas de código com `TOOLS_REGISTRY` intacto. O plano dizia "DEPRECAR após S1". O registry de skills funciona, mas `node_execute` ainda importa `system_tools` como fallback:

```python
# nodes.py, linha 399
from ..tools.system_tools import get_async_tool as legacy_get_async_tool
```

Dois registries coexistem.

### 🟡 IMPORTANTE: Caractere Unicode Corrompido no self_edit

```python
# core/skills/_builtin/self_edit/handler.py, linha 52
if "/opt/vps-agent/" in abs_path:  # contém caractere 路径
```

O comentário na validação de path contém caracteres chineses (`路径` = "caminho"), provavelmente copiados de output de modelo sem revisão. Não quebra funcionalidade mas indica falta de code review.

### 🟡 IMPORTANTE: Documentação 3.5x Maior Que Deveria

12.017 linhas de markdown contra 16.930 linhas de código. Razão docs:código = 0.71. Múltiplos planos desatualizados coexistem: `plano-implantacao-vps-agente-v2.md` (2.620 linhas), `agentvps-v2-roadmap.md` (35K), `agentvps-fase0-estabilizacao.md` (32K), 12+ arquivos em `plans/`. Grande parte está obsoleta mas nunca removida.

---

## 3. O Que Funciona Bem

### ✅ Skill Registry — Bem Implementado

O `registry.py` (203 linhas) é clean code. Auto-discovery via filesystem, carregamento dinâmico com `importlib.util`, busca por trigger exato → parcial → nome, singleton com lazy init, reload para desenvolvimento. O `base.py` define SkillBase abstrata com SecurityLevel enum — extensível e clara.

Adicionar um skill novo realmente requer apenas criar diretório + `handler.py` + `config.yaml`. O requisito "1 arquivo, ~30 linhas" do plano da sprint foi atingido.

### ✅ node_execute Refatorado

De ~250 linhas de if/elif para ~80 linhas que delegam ao registry. O fluxo plan → skill lookup → execute → fallback está correto e extensível. Boa estratégia de fallback: plano → tool_suggestion → trigger na mensagem → smart_response.

### ✅ Classificação de Segurança do Shell Exec

Os regex patterns para FORBIDDEN/DANGEROUS/SAFE são bem pensados. Fork bomb, pipe-to-shell, dd, mkfs estão bloqueados. Docker management requer approval. Leitura é SAFE. Default é MODERATE. O `classify_command()` é o melhor código do projeto.

### ✅ File Manager com Path Validation

`is_path_allowed()` resolve symlinks via `os.path.realpath()` (previne path traversal), verifica forbidden paths, e tem listas separadas para leitura e escrita. Correto e seguro.

### ✅ Estrutura de Skills Padronizada

Todos os 10 skills seguem o mesmo pattern: `config.yaml` com metadata + `handler.py` com classe que herda `SkillBase`. Os configs são consistentes (name, description, version, security_level, triggers, parameters, max_output_chars, timeout_seconds, enabled).

---

## 4. OpenClaw vs AgentVPS — Comparação Atualizada

### OpenClaw em Fevereiro 2026: Status

O OpenClaw está agora em 180.000+ stars mas sua situação de segurança continua grave:

- **CVE-2026-25253** (CVSS 8.8): 1-click RCE via token exfiltration — corrigido em v2026.1.29 mas expôs que safety features são bypassáveis via API
- **CVE-2026-21636**: Permission model bypass — segundo CVE em semanas
- **386 skills maliciosos** no ClawHub (de ~3.286 totais = 11.7% maliciosos)
- **42.000+ instâncias expostas** (subiu de 30k para 42k)
- **v2026.2.12**: 40+ patches de segurança em uma release — indicativo de dívida técnica massiva
- **Simon Willison** (criador do termo "prompt injection") identificou a "tríade letal": acesso a dados privados + exposição a conteúdo não confiável + capacidade de comunicação externa
- **Palo Alto Networks** classificou como "a maior insider threat potencial de 2026"

### Comparação Funcional Atualizada

| Capacidade | OpenClaw | AgentVPS | Delta |
|---|---|---|---|
| Skills disponíveis | 3.286 (11.7% maliciosos) | 10 (100% auditados) | OpenClaw 328x mais, mas com supply chain attack |
| Canais de chat | WhatsApp, Telegram, Discord, Signal, Slack, iMessage | Telegram | OpenClaw 6x mais |
| Execução de shell | ✅ Irrestrita (configurável) | ✅ Com classificação de segurança 4 níveis | AgentVPS mais seguro |
| Busca web | ✅ Browser control | ✅ Brave Search API | OpenClaw mais capaz |
| Self-improvement | ✅ Funcional — escreve e instala seus próprios skills | ❌ Placeholder | OpenClaw funcional |
| Memória persistente | ✅ Across conversations | ⚠️ PostgreSQL mas sem semantic search | Empate parcial |
| Comunidade | 180k stars, 500+ contributors | Solo project | Incomparável |
| Segurança auditada | ❌ 3 CVEs em 3 semanas, sem security team dedicado | ✅ Zero CVEs, 3-level allowlist | AgentVPS mais seguro |
| RAM | 2-4GB mínimo (Node.js) | Desenhado para 2.4GB | AgentVPS mais eficiente |
| Stack | Node.js/TypeScript | Python/LangGraph | Preferência pessoal |

### A Questão Central: Migrar ou Continuar?

**Análise fria dos fatos:**

O OpenClaw faz coisas que o AgentVPS levaria meses para igualar. Self-improvement real, integração com 50+ plataformas, browser control, persistência cross-conversation com semantic search. Sua comunidade resolve bugs em horas e cria integrações diariamente.

Mas o OpenClaw foi descrito por pesquisadores de segurança como "o maior insider threat potencial de 2026". A arquitetura fundamental permite que o agente desative suas próprias proteções via API. 11.7% das skills na sua marketplace distribuem malware. E o Palo Alto Networks — uma das maiores empresas de cybersecurity do mundo — emitiu alerta formal.

**Recomendação: AINDA continuar com AgentVPS, mas mudar a estratégia de desenvolvimento radicalmente.**

Razões:
1. Seu caso de uso é gerenciar uma VPS de produção com dados de clientes (fleet leasing). O risco de um CVE no OpenClaw expondo dados corporativos é inaceitável.
2. O OpenClaw roda Node.js e requer 2-4GB mínimo. Sua VPS tem 2.4GB. Ficaria no limite antes de adicionar PostgreSQL + Redis.
3. O problema do AgentVPS não é falta de features — é falta de inteligência. Adicionar mais skills hardcoded não resolve. O que resolve é fazer o agente pensar, e isso é o tema da seção seguinte.

**Exceção: vale monitorar e estudar os patterns do OpenClaw**, especialmente:
- Como implementam self-improvement real (skill writing loop)
- Como fazem context window management (memória cross-session)
- A arquitetura de SOUL.md (system prompt persistente)

---

## 5. O Problema Fundamental: "Botões Pré-Codificados"

Você identificou o problema central com precisão cirúrgica. Vou diagnosticar em profundidade.

### Sintoma

Quando alguém diz "tem o Node.js instalado?", o agente:
1. Classifica intent via LLM (gasta tokens) → "task"
2. Planeja via node_plan → skill="shell_exec"
3. Dentro do shell_exec, roda `_interpret_and_generate_command` que:
   - Testa 20+ padrões hardcoded com string matching
   - Se match: gera comando (ex: "which nodejs")
   - Se não match: chama o LLM NOVAMENTE para interpretar (gasta mais tokens)
4. Executa o comando
5. Dentro do shell_exec, roda 15 blocos if/elif hardcoded para formatar resposta conversacional

São 2 chamadas LLM + 35 blocos if/elif para responder uma pergunta simples.

Quando alguém diz "o Node está na máquina?" — nenhum dos 20 patterns hardcoded reconhece "na máquina". O agente cai no fallback LLM. Funciona, mas com latência dobrada e custo dobrado.

### Causa Raiz

O agente não pensa. Ele faz matching de strings e delega para funções hardcoded. A "inteligência" é simulada via if/elif, não via raciocínio. Cada novo caso de uso requer editar código.

Isso é fundamentalmente diferente de um sistema inteligente onde:
1. O LLM entende a intenção em QUALQUER formulação
2. O LLM decide qual ferramenta usar e com quais parâmetros
3. O LLM interpreta o resultado e responde naturalmente

### O Que o AgentVPS Deveria Fazer (Modo Inteligente)

```
Usuário: "tem o Node.js na máquina?"

LLM (1 chamada só, com function calling):
  thought: "O usuário quer saber se Node.js está instalado"
  tool_call: shell_exec(command="which node || node --version")

[Executa comando, retorna output]

LLM (1 chamada para responder):
  "Sim, Node.js v22.3.0 está instalado em /usr/local/bin/node"
```

2 chamadas LLM, 0 heurísticas hardcoded, funciona para QUALQUER formulação.

### Como Implementar (ReAct Pattern com Function Calling)

O LangGraph já suporta isso nativamente. O grafo deveria:

1. Receber mensagem
2. Enviar ao LLM COM a lista de tools disponíveis (via function calling / tool use)
3. O LLM decide: responder diretamente OU chamar uma tool
4. Se chamou tool: executar → retornar resultado ao LLM → LLM gera resposta final
5. Se não chamou tool: LLM responde diretamente

Isso elimina `node_plan`, `node_classify_intent` como blocos separados, e as heurísticas do shell_exec. O LLM faz toda a interpretação.

O Gemini 2.5 Flash (já configurado no OpenRouter) suporta function calling nativamente. O custo é similar porque já estamos fazendo 2 chamadas LLM por mensagem com o sistema atual.

---

## 6. Autonomous Blueprint: Diagnóstico Real

### O Que o Blueprint Define (6 Passos)

```
1. DETECT  → Trigger identifica condição
2. PROPOSE → Cria proposal com ação sugerida
3. FILTER  → Cap Gates verificam recursos/segurança/custo
4. EXECUTE → Worker dedicado executa via Skill
5. COMPLETE → Emite evento com resultado
6. RE-TRIGGER → Evento gera novas proposals
```

### O Que Foi Implementado

```
1. DETECT  → ⚠️ 6 triggers existem mas 4 de 6 têm condition=lambda: True (sempre disparam)
2. PROPOSE → ⚠️ ram_high salva proposal no Redis mas ninguém a processa
3. FILTER  → ❌ Não existe (sem cap gates)
4. EXECUTE → ⚠️ Trigger executa ação diretamente (sem worker, sem fila)
5. COMPLETE → ❌ Não emite eventos
6. RE-TRIGGER → ❌ Não existe
```

### Gap Real

O engine.py implementa um sistema de cron jobs com nome diferente. A arquitetura de proposals/missions/policies que diferenciaria um agente autônomo de um scheduler ainda não existe. As tabelas PostgreSQL planejadas (agent_proposals, agent_missions, agent_policies) não foram criadas.

---

## 7. Scores Atualizados

| Dimensão | v2 | v3 | Tendência | Justificativa |
|---|---|---|---|---|
| Arquitetura | 8/10 | 7/10 | ⬇️ | Skill Registry bom, mas shell_exec virou mega-módulo que reimplementa o grafo. Dual registry persiste. |
| Segurança | 7/10 | 5/10 | ⬇️ | API key exposta no GitHub público. Debug log em /tmp. Classificação de segurança do shell_exec é boa. |
| Funcionalidade | 3/10 | 5/10 | ⬆️ | 10 skills vs 5 anteriores. Shell exec e file manager são úteis. Web search funcional. |
| Testes | 6/10 | 6/10 | ➡️ | +175 linhas (test_skill_registry) mas cobertura dos novos skills é zero. |
| Qualidade de Código | 5/10 | 4/10 | ⬇️ | shell_exec com 397 linhas fazendo 3 trabalhos. Caractere Unicode corrompido. system_tools não limpo. |
| Documentação | 7/10 | 5/10 | ⬇️ | 12k linhas de docs com planos obsoletos. Razão docs:código alta demais sem curadoria. |
| DevOps | 8/10 | 8/10 | ➡️ | Inalterado. CI/CD, Docker, pyproject.toml, ruff. |
| Autonomia | 2/10 | 3/10 | ⬆️ | Engine existe com 6 triggers, mas sem proposals/missions/cap gates = cron, não autonomia. |
| Inteligência | N/A | 2/10 | 🆕 | Novo critério. 35 blocos if/elif no shell_exec. Sem function calling. LLM usado como tradutor, não como raciocinador. |
| **OVERALL** | **5.5/10** | **5.0/10** | ⬇️ | Funcionalidade subiu mas qualidade desceu. API key exposta é grave. Shell_exec virou anti-pattern. |

### Diagnóstico v3

**"Motor instalado, mas com carburador em vez de injeção eletrônica."**

A sprint entregou funcionalidade real — o agente agora faz 10 coisas em vez de 5. Mas o padrão de desenvolvimento replicou o problema antigo em escala maior. Cada skill resolve um caso específico com heurísticas hardcoded, em vez de usar o LLM como motor de raciocínio.

O shell_exec é o sintoma mais claro: 397 linhas de if/elif para mapear linguagem natural → comando. Isso deveria ser 1 chamada de function calling ao LLM. Os 15 formatadores de resposta (RAM, containers, disco, hostname, uptime, etc.) deveriam ser 1 prompt ao LLM: "dado este output de terminal, responda a pergunta do usuário."

A nota global caiu de 5.5 para 5.0 não porque houve regressão funcional (houve progresso), mas porque novos problemas surgiram (API key exposta, mega-módulo, engine sem blueprint) e problemas antigos não foram resolvidos (cleanup não feito, dual entry point, docs obsoletas).

---

## 8. Top 5 Ações de Maior Impacto

### Ação 1: Implementar ReAct com Function Calling (TRANSFORMACIONAL)

**O que:** Substituir o fluxo `classify → plan → execute(heurísticas)` por `LLM tool_use → execute → LLM response`.

**Por que:** Elimina 100% das heurísticas hardcoded. O agente entende QUALQUER formulação. Novas capacidades são adicionadas apenas registrando funções como tools — sem editar código de roteamento.

**Como:** O Gemini 2.5 Flash via OpenRouter suporta function calling. Cada skill do registry vira uma tool function com name, description e parameters definidos. O LLM decide quando e como chamar cada tool.

**Impacto:** Transforma o agente de "botões pré-codificados" para "raciocínio real". A nota de Inteligência iria de 2/10 para 7/10.

**Esforço:** ~20h

### Ação 2: Corrigir Exposição de API Key AGORA

**O que:** Remover default value do BRAVE_API_KEY. Revogar key atual. Gerar nova. Auditar todo o código por outros segredos.

**Esforço:** 1h. Sem desculpa para não fazer imediatamente.

### Ação 3: Decompor shell_exec em responsabilidades separadas

**O que:** Mover interpretação para o grafo (ou function calling). Mover formatação para o LLM. Handler fica com ~60 linhas: classificar segurança + executar subprocess + retornar output raw.

**Impacto:** -337 linhas em shell_exec. Elimina duplicação de trabalho com o grafo.

**Esforço:** 8h (se combinado com Ação 1, fica implícito)

### Ação 4: Implementar Autonomous Blueprint Real (com PostgreSQL)

**O que:** Criar as tabelas de proposals/missions/policies. Refatorar engine.py para criar proposals → verificar cap gates → executar → emitir eventos.

**Impacto:** Autonomia sobe de 3/10 para 6/10. Agente propõe ações e pede confirmação.

**Esforço:** 16h

### Ação 5: Cleanup técnico pendente

**O que:** Deletar intent_classifier.py, semantic_memory.py (arquivos fantasma com comentário DEPRECATED), remover system_tools.py TOOLS_REGISTRY, remover debug log de /tmp, limpar docs obsoletas.

**Esforço:** 4h

---

## 9. Prompt Para Validação Cross-Model

```
Você é um avaliador técnico sênior de software. Preciso de uma avaliação extremamente detalhada, criteriosa e realista de um projeto no GitHub.

INSTRUÇÕES:
1. Clone e leia TODOS os arquivos Python do repositório. NÃO confie no README.
2. Para CADA arquivo, verifique se o código realmente funciona ou é placeholder/stub.
3. Conte linhas reais de código funcional vs comentários/docstrings/imports.
4. Identifique padrões (ou anti-padrões) recorrentes.

REPOSITÓRIO: https://github.com/Guitaitson/AgentVPS

AVALIE ESTAS DIMENSÕES (0-10 cada):

1. **QUALIDADE DE CÓDIGO** — Duplicações? Mega-módulos? Dead code? Consistência de estilo?
   - Verificar especificamente: core/skills/_builtin/shell_exec/handler.py (397 linhas — é um mega-módulo?)
   - Verificar: core/tools/system_tools.py (ainda existe? é usado? deveria existir?)
   - Verificar: core/vps_langgraph/intent_classifier.py (deletado ou ainda existe?)

2. **ARQUITETURA** — O grafo LangGraph faz sentido? Os nós têm responsabilidades claras ou há sobreposição?
   - Verificar: node_classify_intent classifica com LLM, mas shell_exec reclassifica internamente — isso é correto?
   - Verificar: node_plan roteia por intent, mas shell_exec tem 20+ heurísticas internas de roteamento — duplicação?

3. **FUNCIONALIDADE REAL** — O que realmente funciona quando você envia uma mensagem?
   - Testar mentalmente: "execute ls -la" → passa pelo grafo → chega ao shell_exec → funciona?
   - Testar mentalmente: "tem o docker instalado?" → passa pelo grafo → shell_exec reconhece? ou cai no fallback LLM?
   - Quantos dos 10 skills realmente executam ações vs retornam strings hardcoded?

4. **SEGURANÇA** — Alguma API key exposta? Secrets em código? Logs com dados sensíveis? Paths sem validação?
   - Verificar: web_search/handler.py tem API key hardcoded?
   - Verificar: nodes.py escreve debug log em /tmp?

5. **INTELIGÊNCIA vs BOTÕES** — O agente PENSA ou apenas faz string matching?
   - Contar quantos blocos if/elif existem no shell_exec para mapear linguagem natural
   - O agente usa function calling / tool use do LLM ou traduz manualmente?
   - Se eu perguntar a mesma coisa de 5 formas diferentes, quantas funcionam vs falham?

6. **AUTONOMOUS LOOP** — O core/autonomous/engine.py implementa o blueprint de 6 passos?
   - Existe tabela de proposals? Existe cap gates? Existe emissão de eventos?
   - Os triggers usam condições reais ou condition=lambda: True?

7. **COMPARAÇÃO COM OPENCLAW** — Dado que OpenClaw tem 180k stars, 3000+ skills, self-improvement funcional, MAS 3 CVEs em 3 semanas e foi chamado de "maior insider threat de 2026" pelo Palo Alto Networks:
   - Faz sentido migrar para OpenClaw para uso em VPS de produção com dados corporativos?
   - Que padrões do OpenClaw valem a pena adaptar SEM herdar os problemas?

8. **TOP 5 AÇÕES** — Liste as 5 coisas que teriam maior impacto no projeto, com estimativa de esforço.

FORMATO DE SAÍDA:
- Para cada dimensão: nota 0-10, 3-5 parágrafos de análise com file paths específicos
- Nota overall com média ponderada (Inteligência e Funcionalidade pesam 2x)
- Diagnóstico em uma frase
- Comparação explícita: "Antes desta sprint era X, agora é Y, mas deveria ser Z"
```
