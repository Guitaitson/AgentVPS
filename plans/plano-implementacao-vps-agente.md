# Plano de Implementação — VPS-Agente v2

## Visão Geral do Projeto

**Objetivo:** Criar uma VPS autônoma de 2.4GB RAM que funciona como agente inteligente com interface Telegram.

**Stack:**
- Ubuntu 24.04
- PostgreSQL 16 + Redis 7 (sempre ligados)
- LangGraph (Python) para orquestração
- Telegram Bot como interface
- Ferramentas sob demanda: n8n, Flowise, Qdrant, Evolution API

**Observação:** Moltbot NÃO faz parte deste projeto.

---

## FASE 0 — Preparação Local

### Tarefas:
1. [x] Ler e analisar `plano-implantacao-vps-agente-v2.md`
2. [x] Criar Memory Bank do Kilocode
   - [x] `context.md` — contexto do projeto
   - [x] `brief.md` — estado atual
   - [x] `history.md` — histórico de decisões
3. [ ] Criar `.kilocode/rules/vps-agent-rules.md`
4. [ ] Gerar chaves SSH e configurar acesso

---

## FASE 1 — Fundação (Dias 1-3)

### 1.1 Hardening do Servidor
- [ ] Atualizar sistema e instalar ferramentas
- [ ] Configurar UFW (firewall)
- [ ] Configurar Fail2ban
- [ ] Criar usuário `deploy`

### 1.2 Docker + Docker Compose
- [ ] Instalar Docker (via repositório oficial)
- [ ] Configurar permissões
- [ ] Configurar limits de memória

### 1.3 Estrutura de Diretórios
- [ ] Criar `/opt/vps-agent/` com subpastas
- [ ] Configurar ownership

### 1.4 PostgreSQL + Redis
- [ ] Criar `docker-compose.core.yml`
- [ ] Criar `.env` com credenciais
- [ ] Criar `init-db.sql`
- [ ] Subir containers e validar

---

## FASE 2 — CLI + Telegram Bot (Dias 4-7)

### 2.1 Python + Dependências
- [ ] Instalar Python 3.12+
- [ ] Criar venv e instalar pacotes

### 2.2 Telegram Bot
- [ ] Configurar token e user ID no .env
- [ ] Criar `bot.py` básico
- [ ] Implementar handlers (/status, /ram, /containers, /health)

---

## FASE 3 — LangGraph + Memória (Dias 8-12)

### 3.1 LangGraph Setup
- [ ] Configurar grafo de estados
- [ ] Implementar nódulos de decisão

### 3.2 Integração com PostgreSQL
- [ ] Operações CRUD para `agent_memory`
- [ ] Operações para `conversation_log`

### 3.3 Integração com Redis
- [ ] Cache de estados
- [ ] Pub/Sub para comunicação

---

## FASE 4 — Ferramentas Sob Demanda (Dias 13-15)

### 4.1 Resource Manager
- [ ] Criar script de gerenciamento
- [ ] Limitar RAM por container
- [ ] Regra: máx 2 ferramentas simultâneas

### 4.2 Docker Compose para Ferramentas
- [ ] `docker-compose.n8n.yml`
- [ ] `docker-compose.flowise.yml`
- [ ] `docker-compose.qdrant.yml`
- [ ] `docker-compose.evolution-api.yml`

---

## FASE 5 — Monitoramento + Hardening (Dias 16-18)

### 5.1 Monitoramento
- [ ] Health checks automatizados
- [ ] Alertas de RAM
- [ ] Logs centralizados

### 5.2 Hardening Final
- [ ] Revisar firewall
- [ ] Rotação de logs
- [ ] Backup automatizado

---

## Credenciais Coletadas

| Item | Valor |
|------|-------|
| IP VPS | 107.175.1.42 |
| Porta SSH | 22 |
| Usuário | root |
| Telegram Bot Token | `8152703152:AAE9vT-O8CMGjrmNYp_WHjOYj3eZB3WKfSA` |
| Telegram User ID | 504326069 |

---

## Comandos SSH Pré-Configurados

```bash
# Conexão com senha (até criar chaves)
ssh root@107.175.1.42 -p 22

# Depois de configurar chaves
ssh -i ~/.ssh/vps_agent_ed25519 root@107.175.1.42 -p 22
```

---

## Diagrama de Arquitetura

```
┌─────────────────────────────────────────────┐
│                 VPS 2.4 GB                  │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │     SEMPRE LIGADOS (~750 MB)       │    │
│  │  PostgreSQL + Redis + LangGraph    │    │
│  │  + Telegram Bot                    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │     SOB DEMANDA (~1650 MB livre)   │    │
│  │  CLI + n8n, Flowise, Qdrant, etc  │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  Interface: Telegram Bot                    │
└─────────────────────────────────────────────┘
```
