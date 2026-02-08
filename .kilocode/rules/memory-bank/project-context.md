# Contexto Centralizado do Projeto — VPS-Agent

## 🎯 OBJETIVO PRINCIPAL

Criar um **agente autônomo** que:
- Responde mensagens naturalmente via Telegram
- Entende demandas do usuário
- Direciona para ferramentas corretas
- Aprende e cria memórias automaticamente
- Executa tarefas na VPS (CLI, GitHub, APIs, etc)
- Evolui sozinho (self-improvement)

---

## ✅ O QUE FAZEMOS

1. **Interface Telegram**
   - Responde "oi" naturalmente
   - Classifica intenções: command, task, question, chat, self_improve

2. **Gerenciamento de Serviços**
   - Status de containers Docker
   - RAM/Sistema
   - PostgreSQL, Redis

3. **Memória**
   - PostgreSQL: fatos, configs, estado
   - Redis: cache, filas
   - Qdrant: memória semântica (sob demanda)

4. **Agente LangGraph**
   - Orquestração de workflows
   - Decisões baseadas em estado

---

## ❌ O QUE NÃO FAZEMOS (AINDA)

1. **Busca na Internet** — Sem MCP de busca integrada
2. **GitHub API** — Sem integração direta
3. **CLI Execução** — Não executa comandos na VPS
4. **Memória de Longo Prazo** — Não persiste aprendizados
5. **Ferramentas Dinâmicas** — Não descobre/instala novas skills

---

## 🔄 JORNADA DO USUÁRIO ESPERADA

```
1. Usuário: "oi"
   → Bot: Responde naturalmente, guarda contexto

2. Usuário: "liste meus projetos no github"
   → Bot: Verifica capacidades
   → Se não tem GitHub MCP: analisa, planeja, cria/instala
   → Executa: conecta API GitHub
   → Responde: lista projetos

3. Usuário: "crie um subagente com o kilocode"
   → Bot: Executa comando CLI na VPS
   → Cria novo agente
   → Reporta status
```

---

## 🧠 MEMÓRIAS NECESSÁRIAS

| Tipo | Conteúdo | Armazenamento |
|------|----------|---------------|
| Fatos | Preferências do usuário | PostgreSQL |
| Aprendizados | O que funcionou/não funcionou | Qdrant |
| Estado | Conversa atual, contexto | Redis |
| Skills | Ferramentas disponíveis | PostgreSQL |

---

## 🔧 FERRAMENTAS DISPONÍVEIS (STATUS)

| Ferramenta | Status | Observação |
|------------|--------|------------|
| RAM/System | ✅ Funcionando | Via docker/docker-py |
| Containers | ✅ Funcionando | docker-py |
| PostgreSQL | ✅ Funcionando | psycopg2 |
| Redis | ✅ Funcionando | redis-py |
| Qdrant | ⚠️ Sob demanda | Não iniciado |
| GitHub API | ❌ Falta | Precisa MCP |
| Busca Web | ❌ Falta | Precisa MCP |
| CLI Execution | ❌ Falta | Precisa tool |

---

## 🚨 PROBLEMAS CRÍTICOS

1. **Sem integração GitHub** — Usuário não consegue listar projetos
2. **Sem busca web** — Não pode buscar informações
3. **Sem execução CLI** — Não pode criar agentes via kilocode
4. **Memória frágil** — Não aprende com interações
5. **Intent classification limitada** — Não descobre novas capacidades

---

## 📋 PRÓXIMOS PASSOS PÓS-FASE 0

### Prioridade Alta
1. Adicionar MCP de GitHub (ou HTTP tool)
2. Adicionar MCP de busca web (Brave Search MCP)
3. Implementar CLI Execution tool
4. Melhorar memória de longo prazo

### Prioridade Média
5. Self-improvement mais autônomo
6. Allowlist de segurança
7. Structured logging

---

## 🔗 REFERÊNCIAS

- GitHub: https://github.com/Guitaitson/AgentVPS
- VPS: 107.175.1.22 (esperando confirmação do IP)
- Telegram: @Molttaitbot
