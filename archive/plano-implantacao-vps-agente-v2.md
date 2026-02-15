# PLANO DE IMPLANTAÇÃO — VPS-AGENTE v2

## Documento de Instruções para Kilocode

**Versão:** 1.0 — 06/02/2026
**Executor:** Kilocode (MiniMax M2.1 / GLM-4.7 / modelo econômico)
**Revisor:** Guilherme (com suporte de modelo robusto quando indicado)
**VPS:** 2.4 GB RAM — Ubuntu 24.04

---

## ÍNDICE

1. [Visão Geral da Arquitetura](#1-visao-geral)
2. [Setup Inicial do Kilocode](#2-setup-kilocode)
3. [FASE 1 — Fundação (Dias 1-3)](#fase-1)
4. [FASE 2 — CLI + Telegram (Dias 4-7)](#fase-2)
5. [FASE 3 — LangGraph + Memória (Dias 8-12)](#fase-3)
6. [FASE 4 — Ferramentas Sob Demanda (Dias 13-15)](#fase-4)
7. [FASE 5 — Moltbot Isolado (Dias 16-17)](#fase-5)
8. [FASE 6 — Monitoramento + Hardening (Dias 18-20)](#fase-6)
9. [Mapa de Custos de Modelo por Tarefa](#custos)
10. [Troubleshooting](#troubleshooting)

---

## CONVENÇÕES DESTE DOCUMENTO

```
🟢 MODELO ECONÔMICO OK — MiniMax M2.1, GLM-4.7 ou similar
🟡 MODELO MÉDIO RECOMENDADO — Sonnet 4.5 ou equivalente
🔴 MODELO ROBUSTO NECESSÁRIO — Opus ou equivalente (decisão arquitetural)
⛳ CHECKPOINT — Pare, valide, e só avance se tudo estiver OK
📋 COPIAR E COLAR — Bloco pronto para executar no terminal
🧪 TESTE — Comando de validação obrigatório
❌ ARMADILHA — Erro comum que modelos baratos cometem aqui
```

---

## 1. VISÃO GERAL DA ARQUITETURA {#1-visao-geral}

### O que estamos construindo

A VPS **É** o agente. Não é "infra com agentes ao lado".

```
┌─────────────────────────────────────────────┐
│                 VPS 2.4 GB                  │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │     SEMPRE LIGADOS (~750 MB)       │    │
│  │  PostgreSQL + Redis + LangGraph    │    │
│  │  + Resource Manager                │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │     SOB DEMANDA (~1650 MB livre)   │    │
│  │  CLI (Claude Code / Kilocode)      │    │
│  │  n8n, Flowise, Qdrant, etc.       │    │
│  │  (sobem e descem conforme uso)    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │     ISOLADO (namespace separado)   │    │
│  │  Moltbot (sandbox de testes)      │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  Interface: Telegram Bot                    │
└─────────────────────────────────────────────┘
```

### Componentes e suas funções

| Componente | Função | Sempre ligado? | RAM estimada |
|---|---|---|---|
| PostgreSQL | Memória estruturada (fatos, configs, estado) | Sim | ~200 MB |
| Redis | Cache, filas, pub/sub | Sim | ~50 MB |
| LangGraph (Python) | Orquestração de agentes, grafos de decisão | Sim | ~300 MB |
| Resource Manager | Sobe/desce containers sob demanda | Sim | ~50 MB |
| Telegram Bot | Interface com o usuário | Sim | ~50 MB |
| Qdrant | Busca vetorial (memória semântica) | Sob demanda | ~400 MB |
| n8n | Automações no-code | Sob demanda | ~300 MB |
| Flowise | Fluxos de LLM visuais | Sob demanda | ~350 MB |
| Evolution API | WhatsApp integration | Sob demanda | ~250 MB |
| Moltbot | Sandbox de testes | Isolado | ~500 MB |

### Regra de ouro da RAM

**Nunca rodar mais de 2 ferramentas sob demanda ao mesmo tempo.**
O Resource Manager garante isso automaticamente.

---

## 2. SETUP INICIAL DO KILOCODE {#2-setup-kilocode}

### 2.1 Criar Memory Bank do projeto

🟢 MODELO ECONÔMICO OK

Antes de qualquer coisa, crie a estrutura de Memory Bank do Kilocode para que o contexto persista entre sessões.

No VS Code, na raiz do projeto (pasta local que espelha a VPS):

📋 COPIAR E COLAR — Estrutura de pastas:

```
mkdir -p .kilocode/rules/memory-bank
```

Crie os 3 arquivos obrigatórios:

**Arquivo 1: `.kilocode/rules/memory-bank/context.md`**

```markdown
# Contexto do Projeto — VPS-Agente v2

## Visão
VPS de 2.4 GB RAM rodando Ubuntu 24.04 que funciona como um agente autônomo supervisionado.

## Stack Principal
- Orquestração: LangGraph (Python 3.11+)
- Banco: PostgreSQL 16 (memória estruturada)
- Cache/Filas: Redis 7
- Busca vetorial: Qdrant (sob demanda)
- Interface: Telegram Bot (python-telegram-bot)
- Containers: Docker + Docker Compose
- Ferramentas sob demanda: n8n, Flowise, Evolution API

## Restrições Críticas
- RAM total: 2.4 GB — NUNCA ultrapassar
- Serviços "sempre ligados" devem caber em 750 MB
- Máximo 2 ferramentas sob demanda simultâneas
- Todo código novo deve ter teste básico
- Toda operação Docker deve verificar RAM antes de executar

## Credenciais
- Não hardcodar nenhuma credencial
- Usar arquivo .env com permissão 600
- .env NUNCA vai pro git

## Acesso VPS
- IP: [PREENCHER]
- Porta SSH: [PREENCHER — idealmente não 22]
- Usuário: deploy (sem root direto)
```

**Arquivo 2: `.kilocode/rules/memory-bank/brief.md`**

```markdown
# Estado Atual — VPS-Agente v2

## Fase Atual: PREPARAÇÃO
## Última ação: Nenhuma ainda
## Próxima ação: Fase 1 — Fundação

## Checklist de Fases
- [ ] Fase 1: Fundação (Docker, PostgreSQL, Redis, estrutura)
- [ ] Fase 2: CLI + Telegram Bot
- [ ] Fase 3: LangGraph + Memória
- [ ] Fase 4: Ferramentas Sob Demanda (Resource Manager)
- [ ] Fase 5: Moltbot Isolado
- [ ] Fase 6: Monitoramento + Hardening

## Problemas Conhecidos
- Nenhum ainda

## Decisões Tomadas
- Arquitetura v2: VPS é o agente, CLI é o cérebro
- Resource Manager controla RAM
- Moltbot fica isolado em namespace separado
```

**Arquivo 3: `.kilocode/rules/memory-bank/history.md`**

```markdown
# Histórico de Decisões

## 2026-02-06 — Arquitetura v2 definida
- VPS é o agente, não apenas infra
- CLI-agnóstico: inteligência vive no LangGraph + memória
- Resource Manager para gerenciar 2.4 GB de RAM
- Moltbot isolado em sandbox
- PostgreSQL + Redis sempre ligados (~750 MB)
- Ferramentas sob demanda (máx 2 simultâneas)

## Modelos de execução
- Preferência: MiniMax M2.1, GLM-4.7 (custo baixo)
- Quando necessário: Sonnet 4.5 ou superior
- Decisões arquiteturais: revisar com modelo robusto
```

### 2.2 Criar arquivo de regras do projeto

📋 COPIAR E COLAR — `.kilocode/rules/vps-agent-rules.md`

```markdown
# Regras para o Agente Kilocode neste projeto

## REGRAS OBRIGATÓRIAS (nunca violar)

1. **NUNCA executar comandos destrutivos sem confirmação**
   - rm -rf, DROP TABLE, docker system prune — SEMPRE pedir confirmação
   
2. **SEMPRE verificar RAM antes de subir container**
   - Rodar: free -m | grep Mem
   - Se memória disponível < 300 MB, NÃO subir nada novo
   
3. **NUNCA hardcodar credenciais**
   - Tudo via .env ou Docker secrets
   
4. **SEMPRE testar após cada alteração**
   - Rodar o teste indicado no checkpoint da fase
   
5. **Uma tarefa por vez**
   - Completar a subtarefa atual antes de começar outra
   - Atualizar brief.md após cada subtarefa completada
   
6. **Não inventar soluções complexas**
   - Se a instrução diz "copiar e colar", copiar e colar
   - Se não sabe, PARAR e pedir ajuda ao usuário

## PADRÕES DE CÓDIGO
- Python: 3.11+, type hints, docstrings
- Docker: sempre usar versões fixas de imagem (ex: postgres:16, não postgres:latest)
- Arquivos de config: YAML quando possível
- Logs: formato JSON estruturado
```

### ⛳ CHECKPOINT 0 — Setup Kilocode

**Validação (faça manualmente):**
- [ ] Pasta `.kilocode/rules/memory-bank/` existe com 3 arquivos
- [ ] Arquivo `vps-agent-rules.md` existe em `.kilocode/rules/`
- [ ] Você tem acesso SSH à VPS (testar: `ssh deploy@SEU_IP`)
- [ ] VPS está rodando Ubuntu 24.04 (`lsb_release -a`)

**Se algum item falhar:** resolva antes de avançar.

---

## FASE 1 — FUNDAÇÃO (Dias 1-3) {#fase-1}

### Objetivo
Preparar a VPS com Docker, PostgreSQL, Redis e estrutura básica de diretórios.

### Pré-requisitos
- Acesso SSH à VPS
- Ubuntu 24.04 instalado e atualizado

---

### 1.1 Hardening básico do servidor

🟢 MODELO ECONÔMICO OK

**Instrução para o Kilocode:**
> Conecte via SSH na VPS e execute os comandos abaixo um por um. Após cada bloco, rode o teste indicado.

📋 BLOCO 1 — Atualizar sistema:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git htop ufw fail2ban unzip jq
```

🧪 TESTE: `htop --version && jq --version`
(deve retornar versões sem erro)

📋 BLOCO 2 — Configurar firewall:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 443/tcp
sudo ufw allow 8443/tcp comment 'Telegram webhook'
sudo ufw --force enable
sudo ufw status verbose
```

🧪 TESTE: `sudo ufw status` deve mostrar as regras acima

📋 BLOCO 3 — Configurar fail2ban:

```bash
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
```

Editar `/etc/fail2ban/jail.local`, localizar a seção `[sshd]` e alterar:

```ini
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
```

```bash
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
```

🧪 TESTE: `sudo fail2ban-client status sshd`
(deve mostrar "Currently banned: 0" e status ativo)

📋 BLOCO 4 — Criar usuário deploy (se não existir):

```bash
# Verificar se já existe
id deploy 2>/dev/null && echo "Usuário deploy já existe" || sudo adduser --disabled-password --gecos "" deploy

# Adicionar ao grupo sudo e docker (docker será criado depois)
sudo usermod -aG sudo deploy
```

❌ ARMADILHA: Modelos baratos às vezes tentam criar o usuário mesmo quando já existe. O comando acima já trata isso.

### ⛳ CHECKPOINT 1.1 — Hardening

```bash
# Rodar este bloco inteiro e verificar saídas:
echo "=== CHECKPOINT 1.1 ==="
echo "1. UFW:" && sudo ufw status | grep -c "ALLOW" 
echo "2. Fail2ban:" && sudo fail2ban-client status sshd | grep "Currently"
echo "3. Usuário deploy:" && id deploy
echo "=== FIM ==="
```

**Esperado:**
- UFW: 3 (três regras ALLOW)
- Fail2ban: "Currently banned: 0" (ativo)
- Usuário deploy: mostra uid/gid

**Se falhar:** NÃO avançar. Resolver item por item.

---

### 1.2 Instalar Docker e Docker Compose

🟢 MODELO ECONÔMICO OK

**Instrução para o Kilocode:**
> Execute os comandos abaixo na ordem. NÃO use snap para instalar Docker.

📋 BLOCO 1 — Instalar Docker (via repositório oficial):

```bash
# Remover versões antigas se existirem
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Adicionar repositório oficial do Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

📋 BLOCO 2 — Configurar permissões:

```bash
sudo usermod -aG docker deploy
# Aplicar grupo sem sair da sessão:
newgrp docker
```

🧪 TESTE:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

❌ ARMADILHA: Se o teste `hello-world` falhar com "permission denied", rode:
```bash
sudo chmod 666 /var/run/docker.sock
```
(Isso é temporário. O `newgrp` ou re-login resolve permanentemente.)

📋 BLOCO 3 — Configurar limites de memória padrão do Docker:

```bash
# Criar daemon.json para limitar uso de memória
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  }
}
EOF

sudo systemctl restart docker
```

🧪 TESTE: `docker info | grep "Logging Driver"` → deve mostrar `json-file`

### ⛳ CHECKPOINT 1.2 — Docker

```bash
echo "=== CHECKPOINT 1.2 ==="
echo "1. Docker:" && docker --version
echo "2. Compose:" && docker compose version  
echo "3. Hello World:" && docker run --rm hello-world 2>&1 | head -2
echo "4. Logging:" && docker info 2>/dev/null | grep "Logging Driver"
echo "=== FIM ==="
```

---

### 1.3 Criar estrutura de diretórios

🟢 MODELO ECONÔMICO OK

📋 COPIAR E COLAR:

```bash
# Estrutura principal
sudo mkdir -p /opt/vps-agent/{core,tools,sandbox,scripts,configs,data,logs,backups}

# Subdiretórios do core
sudo mkdir -p /opt/vps-agent/core/{langgraph,telegram-bot,resource-manager}

# Subdiretórios das ferramentas sob demanda
sudo mkdir -p /opt/vps-agent/tools/{n8n,flowise,qdrant,evolution-api}

# Subdiretórios de dados persistentes
sudo mkdir -p /opt/vps-agent/data/{postgres,redis,qdrant-storage}

# Dar ownership ao deploy
sudo chown -R deploy:deploy /opt/vps-agent

# Permissões
chmod 750 /opt/vps-agent
chmod 700 /opt/vps-agent/configs
```

🧪 TESTE: `tree /opt/vps-agent -L 2 -d`

Saída esperada (aproximada):
```
/opt/vps-agent
├── backups
├── configs
├── core
│   ├── langgraph
│   ├── resource-manager
│   └── telegram-bot
├── data
│   ├── postgres
│   ├── qdrant-storage
│   └── redis
├── logs
├── sandbox
├── scripts
└── tools
    ├── evolution-api
    ├── flowise
    ├── n8n
    └── qdrant
```

---

### 1.4 PostgreSQL + Redis (Docker Compose)

🟢 MODELO ECONÔMICO OK

📋 COPIAR E COLAR — `/opt/vps-agent/core/docker-compose.core.yml`:

```yaml
# /opt/vps-agent/core/docker-compose.core.yml
# SERVIÇOS SEMPRE LIGADOS — ~350 MB total
# NÃO alterar limites de memória sem aprovação

version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    container_name: vps-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: vps_agent
    volumes:
      - /opt/vps-agent/data/postgres:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    ports:
      - "127.0.0.1:5432:5432"
    deploy:
      resources:
        limits:
          memory: 200M
        reservations:
          memory: 100M
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - core-network

  redis:
    image: redis:7-alpine
    container_name: vps-redis
    restart: unless-stopped
    command: redis-server --maxmemory 40mb --maxmemory-policy allkeys-lru --appendonly yes
    volumes:
      - /opt/vps-agent/data/redis:/data
    ports:
      - "127.0.0.1:6379:6379"
    deploy:
      resources:
        limits:
          memory: 60M
        reservations:
          memory: 30M
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - core-network

networks:
  core-network:
    name: vps-core-network
    driver: bridge
```

📋 COPIAR E COLAR — `/opt/vps-agent/core/.env`:

```bash
# /opt/vps-agent/core/.env
# MUDAR ESTAS SENHAS ANTES DE RODAR!
POSTGRES_USER=vps_agent
POSTGRES_PASSWORD=TROCAR_PARA_SENHA_FORTE_AQUI
```

```bash
# Proteger o .env
chmod 600 /opt/vps-agent/core/.env
```

❌ ARMADILHA: Modelos baratos às vezes esquecem de trocar a senha. TROQUE A SENHA antes de continuar.

📋 COPIAR E COLAR — `/opt/vps-agent/core/init-db.sql`:

```sql
-- /opt/vps-agent/core/init-db.sql
-- Schema inicial para memória do agente

-- Memória estruturada por usuário
CREATE TABLE IF NOT EXISTS agent_memory (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    memory_type VARCHAR(50) NOT NULL,  -- 'fact', 'preference', 'context'
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, memory_type, key)
);

-- Memória global do sistema
CREATE TABLE IF NOT EXISTS system_state (
    id SERIAL PRIMARY KEY,
    component VARCHAR(100) NOT NULL UNIQUE,
    state JSONB NOT NULL,
    last_health_check TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Histórico de conversas (para contexto)
CREATE TABLE IF NOT EXISTS conversation_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tarefas agendadas
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(255) NOT NULL,
    task_type VARCHAR(50) NOT NULL,  -- 'cron', 'once', 'recurring'
    schedule VARCHAR(100),  -- cron expression ou timestamp
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'running', 'done', 'failed'
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Skills aprendidas pelo agente
CREATE TABLE IF NOT EXISTS agent_skills (
    id SERIAL PRIMARY KEY,
    skill_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    trigger_pattern VARCHAR(500),  -- regex ou keywords
    execution_steps JSONB NOT NULL,
    success_count INT DEFAULT 0,
    failure_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX idx_memory_user ON agent_memory(user_id, memory_type);
CREATE INDEX idx_memory_key ON agent_memory(key);
CREATE INDEX idx_conversation_user ON conversation_log(user_id, created_at DESC);
CREATE INDEX idx_tasks_status ON scheduled_tasks(status, next_run);
CREATE INDEX idx_skills_trigger ON agent_skills(trigger_pattern);

-- Função para auto-update do updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_memory_updated
    BEFORE UPDATE ON agent_memory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_state_updated
    BEFORE UPDATE ON system_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_skills_updated
    BEFORE UPDATE ON agent_skills
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

📋 Subir os serviços:

```bash
cd /opt/vps-agent/core
docker compose -f docker-compose.core.yml up -d
```

🧪 TESTES (rodar todos):

```bash
echo "=== TESTES FASE 1.4 ==="

# Teste 1: Containers rodando
echo "1. Containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "postgres|redis"

# Teste 2: PostgreSQL acessível
echo "2. PostgreSQL:"
docker exec vps-postgres pg_isready -U vps_agent

# Teste 3: Tabelas criadas
echo "3. Tabelas:"
docker exec vps-postgres psql -U vps_agent -d vps_agent -c "\dt" 2>/dev/null

# Teste 4: Redis acessível  
echo "4. Redis:"
docker exec vps-redis redis-cli ping

# Teste 5: Redis aceita dados
echo "5. Redis write/read:"
docker exec vps-redis redis-cli SET test_key "ok" && docker exec vps-redis redis-cli GET test_key

# Teste 6: Memória usada
echo "6. RAM usada por containers:"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | grep -E "postgres|redis"

echo "=== FIM ==="
```

**Esperado:**
1. Ambos containers "Up" e "healthy"
2. PostgreSQL "accepting connections"
3. 5 tabelas criadas (agent_memory, system_state, conversation_log, scheduled_tasks, agent_skills)
4. Redis "PONG"
5. "ok"
6. PostgreSQL < 200MB, Redis < 60MB

### ⛳ CHECKPOINT FASE 1 COMPLETA

```bash
echo "========================================="
echo "    CHECKPOINT FINAL — FASE 1"
echo "========================================="
echo ""
echo "1. Sistema:" && lsb_release -d
echo "2. Docker:" && docker --version | cut -d' ' -f3
echo "3. Compose:" && docker compose version --short
echo "4. UFW ativo:" && sudo ufw status | head -1
echo "5. Fail2ban:" && sudo fail2ban-client status sshd 2>/dev/null | grep "Currently" || echo "FALHOU"
echo "6. Diretórios:" && ls /opt/vps-agent/ | tr '\n' ' '
echo ""
echo "7. PostgreSQL:" && docker exec vps-postgres pg_isready -U vps_agent 2>/dev/null || echo "FALHOU"
echo "8. Redis:" && docker exec vps-redis redis-cli ping 2>/dev/null || echo "FALHOU"
echo ""
echo "9. RAM total containers:"
docker stats --no-stream --format "{{.Name}}: {{.MemUsage}}" 2>/dev/null
echo ""
FREE_MEM=$(free -m | awk '/Mem:/ {print $7}')
echo "10. RAM disponível: ${FREE_MEM} MB"
if [ "$FREE_MEM" -gt 1500 ]; then
    echo "    ✅ RAM OK (>1500 MB livres)"
else
    echo "    ⚠️ RAM BAIXA — investigar antes de avançar"
fi
echo ""
echo "========================================="
```

**Critérios para avançar para Fase 2:**
- [ ] Todos os 10 itens OK (sem "FALHOU")
- [ ] RAM disponível > 1500 MB
- [ ] Senha do PostgreSQL foi trocada (não é a default)

🔴 **REVISÃO ESTRATÉGICA:** Antes de avançar, tire um print do checkpoint e revise com modelo robusto se necessário. Pergunte: "A fundação está sólida? Algum ajuste antes da Fase 2?"

**Atualizar brief.md:**
```markdown
## Fase Atual: FASE 2
## Última ação: Fase 1 completa — Fundação OK
## Próxima ação: Fase 2.1 — Python + dependências
```

---

## FASE 2 — CLI + TELEGRAM BOT (Dias 4-7) {#fase-2}

### Objetivo
Instalar Python, criar o Telegram Bot e conectar ao PostgreSQL/Redis.

---

### 2.1 Instalar Python e dependências

🟢 MODELO ECONÔMICO OK

📋 COPIAR E COLAR:

```bash
# Python 3.11+ (Ubuntu 24.04 já vem com 3.12)
python3 --version

# Se for < 3.11, instalar:
# sudo apt install -y python3.12 python3.12-venv python3.12-dev

# Criar ambiente virtual do projeto
cd /opt/vps-agent/core
python3 -m venv venv
source venv/bin/activate

# Instalar dependências base
pip install --upgrade pip

pip install \
    python-telegram-bot==21.* \
    psycopg2-binary==2.9.* \
    redis==5.* \
    langgraph==0.3.* \
    langchain-core==0.3.* \
    langchain-anthropic==0.3.* \
    langchain-openai==0.3.* \
    pydantic==2.* \
    python-dotenv==1.* \
    httpx==0.* \
    structlog==24.*
```

❌ ARMADILHA: Modelos baratos às vezes inventam versões de pacote. Se der erro de versão, remova a constraint de versão (ex: `langgraph` em vez de `langgraph==0.3.*`) e deixe o pip resolver.

🧪 TESTE:

```bash
source /opt/vps-agent/core/venv/bin/activate
python3 -c "
import telegram
import psycopg2
import redis
import langgraph
print('telegram:', telegram.__version__)
print('psycopg2:', psycopg2.__version__)
print('redis:', redis.__version__)
print('langgraph:', langgraph.__version__)
print('✅ Todas as dependências OK')
"
```

---

### 2.2 Criar Telegram Bot

🟡 MODELO MÉDIO RECOMENDADO (lógica de integração)

**Passo manual obrigatório:**
1. Abrir Telegram, buscar @BotFather
2. Enviar `/newbot`
3. Escolher nome e username
4. Copiar o token gerado
5. Salvar no `.env`

📋 Adicionar ao `/opt/vps-agent/core/.env`:

```bash
# Adicionar estas linhas ao .env existente:
TELEGRAM_BOT_TOKEN=SEU_TOKEN_AQUI
TELEGRAM_ALLOWED_USERS=SEU_TELEGRAM_ID
# Para descobrir seu ID: envie mensagem para @userinfobot
```

📋 COPIAR E COLAR — `/opt/vps-agent/core/telegram-bot/bot.py`:

```python
"""
VPS-Agent Telegram Bot — Interface principal
Versão: 1.0
"""
import os
import asyncio
import json
from datetime import datetime, timezone

import structlog
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import psycopg2
from psycopg2.extras import Json
import redis

# Configuração
load_dotenv("/opt/vps-agent/core/.env")
logger = structlog.get_logger()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = [
    int(uid.strip()) 
    for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") 
    if uid.strip()
]

# Conexões
def get_db_conn():
    """Retorna conexão com PostgreSQL."""
    return psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        dbname="vps_agent",
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

def get_redis():
    """Retorna conexão com Redis."""
    return redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)


# Middleware de segurança
def authorized_only(func):
    """Decorator: só permite usuários autorizados."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USERS:
            logger.warning("acesso_negado", user_id=user_id)
            await update.message.reply_text("⛔ Acesso não autorizado.")
            return
        return await func(update, context)
    return wrapper


# Handlers
@authorized_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /start."""
    await update.message.reply_text(
        "🤖 VPS-Agent v2 Online!\n\n"
        "Comandos disponíveis:\n"
        "/status — Estado da VPS\n"
        "/ram — Uso de memória\n"
        "/containers — Containers ativos\n"
        "/health — Health check completo\n"
        "/help — Ajuda"
    )


@authorized_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /status — mostra estado geral."""
    try:
        r = get_redis()
        r.ping()
        redis_status = "✅"
    except Exception:
        redis_status = "❌"

    try:
        conn = get_db_conn()
        conn.close()
        pg_status = "✅"
    except Exception:
        pg_status = "❌"

    # RAM
    import subprocess
    result = subprocess.run(
        ["free", "-m"], capture_output=True, text=True
    )
    lines = result.stdout.strip().split("\n")
    mem_parts = lines[1].split()
    total = int(mem_parts[1])
    used = int(mem_parts[2])
    available = int(mem_parts[6])

    status_text = (
        f"📊 **Status VPS-Agent**\n\n"
        f"🗄 PostgreSQL: {pg_status}\n"
        f"⚡ Redis: {redis_status}\n"
        f"💾 RAM: {used}MB / {total}MB (livre: {available}MB)\n"
        f"🕐 Hora: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
    )

    await update.message.reply_text(status_text, parse_mode="Markdown")


@authorized_only
async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /ram — detalhe de memória por container."""
    import subprocess
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", 
         "{{.Name}}: {{.MemUsage}} ({{.MemPerc}})"],
        capture_output=True, text=True
    )
    
    if result.stdout.strip():
        text = f"🧠 **RAM por Container:**\n\n```\n{result.stdout}```"
    else:
        text = "Nenhum container rodando."
    
    await update.message.reply_text(text, parse_mode="Markdown")


@authorized_only
async def cmd_containers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /containers — lista containers."""
    import subprocess
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
        capture_output=True, text=True
    )
    
    if result.stdout.strip():
        text = f"🐳 **Containers Ativos:**\n\n```\n{result.stdout}```"
    else:
        text = "Nenhum container rodando."
    
    await update.message.reply_text(text, parse_mode="Markdown")


@authorized_only
async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /health — check completo."""
    checks = []
    
    # 1. PostgreSQL
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM agent_memory")
        count = cur.fetchone()[0]
        conn.close()
        checks.append(f"✅ PostgreSQL: {count} memórias")
    except Exception as e:
        checks.append(f"❌ PostgreSQL: {e}")
    
    # 2. Redis
    try:
        r = get_redis()
        info = r.info("memory")
        used_mb = round(int(info["used_memory"]) / 1024 / 1024, 1)
        checks.append(f"✅ Redis: {used_mb}MB usado")
    except Exception as e:
        checks.append(f"❌ Redis: {e}")
    
    # 3. Disk
    import subprocess
    disk = subprocess.run(
        ["df", "-h", "/"], capture_output=True, text=True
    )
    disk_line = disk.stdout.strip().split("\n")[1].split()
    checks.append(f"💿 Disco: {disk_line[2]} usado de {disk_line[1]} ({disk_line[4]})")
    
    # 4. Load
    load = subprocess.run(
        ["uptime"], capture_output=True, text=True
    )
    checks.append(f"⚙️ {load.stdout.strip().split('load average:')[1].strip()}")
    
    text = "🏥 **Health Check:**\n\n" + "\n".join(checks)
    await update.message.reply_text(text, parse_mode="Markdown")


@authorized_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de texto — futuro ponto de entrada do LangGraph."""
    user_msg = update.message.text
    user_id = str(update.effective_user.id)
    
    # Log no PostgreSQL
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversation_log (user_id, role, content) VALUES (%s, %s, %s)",
            (user_id, "user", user_msg)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("erro_log_conversa", error=str(e))
    
    # Por enquanto, resposta placeholder
    # Na Fase 3, isso será substituído pelo LangGraph
    await update.message.reply_text(
        f"📝 Recebi: \"{user_msg}\"\n\n"
        "⏳ LangGraph ainda não conectado (Fase 3).\n"
        "Use /status ou /health para interagir."
    )


def main():
    """Inicia o bot."""
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado no .env")
    
    if not ALLOWED_USERS:
        raise ValueError("TELEGRAM_ALLOWED_USERS não configurado no .env")
    
    logger.info("bot_iniciando", allowed_users=ALLOWED_USERS)
    
    app = Application.builder().token(TOKEN).build()
    
    # Registrar handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ram", cmd_ram))
    app.add_handler(CommandHandler("containers", cmd_containers))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("bot_rodando")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
```

📋 Criar script de inicialização — `/opt/vps-agent/scripts/start-bot.sh`:

```bash
#!/bin/bash
# /opt/vps-agent/scripts/start-bot.sh
cd /opt/vps-agent/core
source venv/bin/activate
python3 telegram-bot/bot.py
```

```bash
chmod +x /opt/vps-agent/scripts/start-bot.sh
```

🧪 TESTE:

```bash
# Testar o bot (Ctrl+C para parar após verificar)
cd /opt/vps-agent/core
source venv/bin/activate
python3 telegram-bot/bot.py
```

Depois, no Telegram:
1. Enviar `/start` ao bot → deve responder com menu
2. Enviar `/status` → deve mostrar estado do PostgreSQL e Redis
3. Enviar `/ram` → deve mostrar uso de RAM
4. Enviar qualquer texto → deve salvar no banco e responder placeholder

---

### 2.3 Criar serviço systemd para o bot

🟢 MODELO ECONÔMICO OK

📋 COPIAR E COLAR — `/etc/systemd/system/vps-agent-bot.service`:

```bash
sudo tee /etc/systemd/system/vps-agent-bot.service > /dev/null <<'EOF'
[Unit]
Description=VPS-Agent Telegram Bot
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/vps-agent/core
ExecStart=/opt/vps-agent/core/venv/bin/python3 /opt/vps-agent/core/telegram-bot/bot.py
Restart=always
RestartSec=10
Environment=PATH=/opt/vps-agent/core/venv/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable vps-agent-bot
sudo systemctl start vps-agent-bot
```

🧪 TESTE:

```bash
sudo systemctl status vps-agent-bot
# Deve mostrar "active (running)"

# Verificar logs:
journalctl -u vps-agent-bot -f --no-pager -n 20
```

### ⛳ CHECKPOINT FASE 2 COMPLETA

```bash
echo "========================================="
echo "    CHECKPOINT FINAL — FASE 2"
echo "========================================="
echo ""
echo "1. Python:" && python3 --version
echo "2. Venv:" && /opt/vps-agent/core/venv/bin/python3 -c "import telegram; print('telegram OK')"
echo "3. Bot service:" && sudo systemctl is-active vps-agent-bot
echo "4. PostgreSQL:" && docker exec vps-postgres pg_isready -U vps_agent
echo "5. Redis:" && docker exec vps-redis redis-cli ping
echo ""
echo "6. Teste de integração (mensagens salvas no banco):"
docker exec vps-postgres psql -U vps_agent -d vps_agent -c "SELECT COUNT(*) as total_mensagens FROM conversation_log;" 2>/dev/null
echo ""
FREE_MEM=$(free -m | awk '/Mem:/ {print $7}')
echo "7. RAM disponível: ${FREE_MEM} MB"
echo ""
echo "========================================="
```

**Critérios para avançar:**
- [ ] Bot respondendo no Telegram (/start, /status, /health)
- [ ] Mensagens sendo salvas no PostgreSQL
- [ ] Service systemd ativo e reiniciando automaticamente
- [ ] RAM disponível > 1400 MB

**Atualizar brief.md:**
```markdown
## Fase Atual: FASE 3
## Última ação: Fase 2 completa — Bot Telegram + integração DB/Redis
## Próxima ação: Fase 3.1 — Estrutura LangGraph
```

---

## FASE 3 — LANGGRAPH + MEMÓRIA (Dias 8-12) {#fase-3}

### Objetivo
Criar o sistema nervoso do agente: orquestração de decisões via LangGraph com memória persistente.

🔴 **ATENÇÃO:** Esta é a fase mais complexa. Recomendo revisão com modelo robusto após cada sub-fase.

---

### 3.1 Estrutura do LangGraph

🟡 MODELO MÉDIO RECOMENDADO

📋 COPIAR E COLAR — `/opt/vps-agent/core/langgraph/__init__.py`:

```python
"""LangGraph Agent — Orquestração do VPS-Agent v2"""
```

📋 COPIAR E COLAR — `/opt/vps-agent/core/langgraph/state.py`:

```python
"""
Estado compartilhado do agente LangGraph.
Tudo que o agente "sabe" em um dado momento.
"""
from typing import TypedDict, Optional, Literal
from datetime import datetime


class AgentState(TypedDict):
    """Estado que flui pelo grafo do agente."""
    
    # Input
    user_id: str
    user_message: str
    
    # Classificação da intenção
    intent: Optional[str]  # 'command', 'question', 'task', 'chat'
    intent_confidence: Optional[float]
    
    # Contexto recuperado da memória
    user_context: Optional[dict]  # Fatos sobre o usuário
    conversation_history: Optional[list]  # Últimas N mensagens
    
    # Planejamento
    plan: Optional[list]  # Lista de passos a executar
    current_step: Optional[int]
    
    # Ferramentas
    tools_needed: Optional[list]  # Quais ferramentas o passo requer
    tools_available: Optional[list]  # Quais estão rodando agora
    
    # Execução
    execution_result: Optional[str]
    error: Optional[str]
    
    # Output
    response: Optional[str]
    should_save_memory: Optional[bool]
    memory_updates: Optional[list]  # Novos fatos para salvar
    
    # Meta
    timestamp: Optional[str]
    ram_available_mb: Optional[int]
```

📋 COPIAR E COLAR — `/opt/vps-agent/core/langgraph/memory.py`:

```python
"""
Sistema de memória do agente.
Duas dimensões: por usuário e global.
PostgreSQL para fatos, Redis para cache.
"""
import os
import json
from typing import Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor
import redis
from dotenv import load_dotenv

load_dotenv("/opt/vps-agent/core/.env")


class AgentMemory:
    """Gerencia memória persistente do agente."""
    
    def __init__(self):
        self._db_config = {
            "host": "127.0.0.1",
            "port": 5432,
            "dbname": "vps_agent",
            "user": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD"),
        }
        self._redis = redis.Redis(
            host="127.0.0.1", port=6379, decode_responses=True
        )
    
    def _get_conn(self):
        return psycopg2.connect(**self._db_config)
    
    # --- Memória por usuário ---
    
    def get_user_facts(self, user_id: str) -> dict:
        """Recupera todos os fatos conhecidos sobre um usuário."""
        # Tentar cache primeiro
        cache_key = f"user_facts:{user_id}"
        cached = self._redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT key, value, confidence FROM agent_memory "
            "WHERE user_id = %s AND memory_type = 'fact' "
            "ORDER BY confidence DESC",
            (user_id,)
        )
        facts = {row["key"]: row["value"] for row in cur.fetchall()}
        conn.close()
        
        # Cache por 5 minutos
        self._redis.setex(cache_key, 300, json.dumps(facts))
        return facts
    
    def save_fact(self, user_id: str, key: str, value: dict, confidence: float = 1.0):
        """Salva ou atualiza um fato sobre o usuário."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_memory (user_id, memory_type, key, value, confidence)
            VALUES (%s, 'fact', %s, %s, %s)
            ON CONFLICT (user_id, memory_type, key) 
            DO UPDATE SET value = EXCLUDED.value, confidence = EXCLUDED.confidence
            """,
            (user_id, key, Json(value), confidence)
        )
        conn.commit()
        conn.close()
        
        # Invalidar cache
        self._redis.delete(f"user_facts:{user_id}")
    
    # --- Histórico de conversas ---
    
    def get_recent_messages(self, user_id: str, limit: int = 10) -> list:
        """Retorna as últimas N mensagens do usuário."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT role, content, created_at FROM conversation_log "
            "WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
            (user_id, limit)
        )
        messages = list(reversed(cur.fetchall()))
        conn.close()
        return messages
    
    def save_message(self, user_id: str, role: str, content: str, metadata: dict = None):
        """Salva uma mensagem no histórico."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversation_log (user_id, role, content, metadata) "
            "VALUES (%s, %s, %s, %s)",
            (user_id, role, content, Json(metadata or {}))
        )
        conn.commit()
        conn.close()
    
    # --- Estado do sistema ---
    
    def get_system_state(self, component: str) -> Optional[dict]:
        """Recupera estado de um componente do sistema."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT state FROM system_state WHERE component = %s",
            (component,)
        )
        row = cur.fetchone()
        conn.close()
        return row["state"] if row else None
    
    def save_system_state(self, component: str, state: dict):
        """Salva estado de um componente."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO system_state (component, state, last_health_check)
            VALUES (%s, %s, NOW())
            ON CONFLICT (component) 
            DO UPDATE SET state = EXCLUDED.state, last_health_check = NOW()
            """,
            (component, Json(state))
        )
        conn.commit()
        conn.close()
    
    # --- Skills ---
    
    def get_matching_skill(self, message: str) -> Optional[dict]:
        """Busca skill que corresponde à mensagem."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM agent_skills ORDER BY success_count DESC"
        )
        skills = cur.fetchall()
        conn.close()
        
        # Match simples por keywords (Qdrant fará busca semântica depois)
        message_lower = message.lower()
        for skill in skills:
            if skill["trigger_pattern"]:
                keywords = skill["trigger_pattern"].split(",")
                if any(kw.strip().lower() in message_lower for kw in keywords):
                    return dict(skill)
        return None
```

📋 COPIAR E COLAR — `/opt/vps-agent/core/langgraph/graph.py`:

```python
"""
Grafo principal do agente LangGraph.
Define o fluxo de decisão: input → classificar → planejar → executar → responder.
"""
from langgraph.graph import StateGraph, END
from .state import AgentState
from .memory import AgentMemory
from .nodes import (
    node_classify_intent,
    node_load_context,
    node_plan,
    node_execute,
    node_generate_response,
    node_save_memory,
)

memory = AgentMemory()


def build_agent_graph() -> StateGraph:
    """Constrói e retorna o grafo do agente."""
    
    graph = StateGraph(AgentState)
    
    # Adicionar nós
    graph.add_node("classify", node_classify_intent)
    graph.add_node("load_context", node_load_context)
    graph.add_node("plan", node_plan)
    graph.add_node("execute", node_execute)
    graph.add_node("respond", node_generate_response)
    graph.add_node("save_memory", node_save_memory)
    
    # Definir fluxo
    graph.set_entry_point("classify")
    
    graph.add_edge("classify", "load_context")
    graph.add_edge("load_context", "plan")
    
    # Condicional: se é comando direto, executar. Se é chat, responder.
    graph.add_conditional_edges(
        "plan",
        lambda state: "execute" if state.get("plan") else "respond",
        {
            "execute": "execute",
            "respond": "respond",
        }
    )
    
    graph.add_edge("execute", "respond")
    
    # Condicional: salvar memória se necessário
    graph.add_conditional_edges(
        "respond",
        lambda state: "save_memory" if state.get("should_save_memory") else "end",
        {
            "save_memory": "save_memory",
            "end": END,
        }
    )
    
    graph.add_edge("save_memory", END)
    
    return graph.compile()
```

📋 COPIAR E COLAR — `/opt/vps-agent/core/langgraph/nodes.py`:

```python
"""
Nós do grafo LangGraph.
Cada função é um passo no fluxo de decisão do agente.

NOTA: Na versão inicial, os nós usam lógica baseada em regras.
Na evolução, serão substituídos por chamadas a LLMs via API.
"""
import subprocess
import json
from datetime import datetime, timezone

from .state import AgentState
from .memory import AgentMemory

memory = AgentMemory()

# Comandos reconhecidos pelo bot
KNOWN_COMMANDS = {
    "status": "Verificar estado da VPS",
    "ram": "Verificar uso de memória",
    "containers": "Listar containers",
    "health": "Health check completo",
    "tools": "Listar ferramentas disponíveis",
    "start_tool": "Iniciar uma ferramenta",
    "stop_tool": "Parar uma ferramenta",
}


def node_classify_intent(state: AgentState) -> dict:
    """
    Classifica a intenção do usuário.
    V1: baseado em regras. V2 futura: classificador LLM.
    """
    msg = state["user_message"].lower().strip()
    
    # Comandos diretos
    if msg.startswith("/"):
        cmd = msg.split()[0][1:]  # Remove /
        if cmd in KNOWN_COMMANDS:
            return {
                "intent": "command",
                "intent_confidence": 1.0,
            }
    
    # Palavras-chave de tarefas
    task_keywords = ["subir", "parar", "reiniciar", "instalar", "configurar", 
                     "backup", "atualizar", "deploy"]
    if any(kw in msg for kw in task_keywords):
        return {
            "intent": "task",
            "intent_confidence": 0.8,
        }
    
    # Perguntas
    question_keywords = ["como", "por que", "quando", "qual", "quanto", "?"]
    if any(kw in msg for kw in question_keywords):
        return {
            "intent": "question",
            "intent_confidence": 0.7,
        }
    
    # Default: chat
    return {
        "intent": "chat",
        "intent_confidence": 0.5,
    }


def node_load_context(state: AgentState) -> dict:
    """Carrega contexto relevante da memória."""
    user_id = state["user_id"]
    
    user_facts = memory.get_user_facts(user_id)
    recent_msgs = memory.get_recent_messages(user_id, limit=5)
    
    # Checar RAM disponível
    result = subprocess.run(
        ["free", "-m"], capture_output=True, text=True
    )
    lines = result.stdout.strip().split("\n")
    available = int(lines[1].split()[6])
    
    return {
        "user_context": user_facts,
        "conversation_history": [
            {"role": m["role"], "content": m["content"]} 
            for m in recent_msgs
        ],
        "ram_available_mb": available,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def node_plan(state: AgentState) -> dict:
    """
    Planeja a ação baseado na intenção.
    V1: mapeamento direto. V2 futura: LLM planner.
    """
    intent = state.get("intent", "chat")
    msg = state["user_message"].lower().strip()
    
    if intent == "command":
        cmd = msg.split()[0][1:] if msg.startswith("/") else msg.split()[0]
        return {
            "plan": [{"action": "run_command", "command": cmd}],
            "current_step": 0,
        }
    
    if intent == "task":
        # Verificar se existe uma skill para isso
        skill = memory.get_matching_skill(msg)
        if skill:
            return {
                "plan": skill["execution_steps"],
                "current_step": 0,
            }
        
        # Sem skill: responder que não sabe (ainda)
        return {
            "plan": None,
            "response": (
                "🤔 Ainda não tenho uma skill para essa tarefa.\n"
                "No futuro, vou aprender com você!"
            ),
        }
    
    # Perguntas e chat: sem plano, vai direto para resposta
    return {"plan": None}


def node_execute(state: AgentState) -> dict:
    """
    Executa o plano passo a passo.
    V1: apenas comandos conhecidos. V2: execução via CLI.
    """
    plan = state.get("plan", [])
    if not plan:
        return {"execution_result": "Nenhum plano para executar."}
    
    step = plan[state.get("current_step", 0)]
    action = step.get("action", "")
    
    if action == "run_command":
        cmd_name = step.get("command", "")
        
        if cmd_name == "status":
            return {"execution_result": "STATUS_CMD"}
        elif cmd_name == "ram":
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format",
                 "{{.Name}}: {{.MemUsage}} ({{.MemPerc}})"],
                capture_output=True, text=True
            )
            return {"execution_result": result.stdout or "Sem containers."}
        elif cmd_name == "containers":
            result = subprocess.run(
                ["docker", "ps", "--format",
                 "{{.Names}}\t{{.Status}}"],
                capture_output=True, text=True
            )
            return {"execution_result": result.stdout or "Sem containers."}
        elif cmd_name == "health":
            return {"execution_result": "HEALTH_CMD"}
    
    return {"execution_result": f"Ação desconhecida: {action}"}


def node_generate_response(state: AgentState) -> dict:
    """
    Gera a resposta final para o usuário.
    V1: template-based. V2 futura: LLM.
    """
    # Se já tem resposta definida (ex: do planner)
    if state.get("response"):
        return {"should_save_memory": False}
    
    intent = state.get("intent", "chat")
    exec_result = state.get("execution_result", "")
    
    if intent == "command" and exec_result:
        return {
            "response": f"📋 Resultado:\n\n```\n{exec_result}\n```",
            "should_save_memory": False,
        }
    
    if intent == "question":
        return {
            "response": (
                "❓ Entendi sua pergunta, mas ainda não tenho um LLM "
                "conectado para responder livremente.\n"
                "Na Fase 3 completa, vou poder conversar sobre qualquer tema!\n\n"
                "Por enquanto, use os comandos: /status, /ram, /health"
            ),
            "should_save_memory": False,
        }
    
    # Chat genérico
    return {
        "response": (
            "💬 Recebi sua mensagem! Ainda estou em fase de construção.\n"
            "Use /help para ver o que posso fazer agora."
        ),
        "should_save_memory": False,
    }


def node_save_memory(state: AgentState) -> dict:
    """Salva novos fatos na memória se necessário."""
    updates = state.get("memory_updates", [])
    user_id = state["user_id"]
    
    for update in updates:
        memory.save_fact(
            user_id=user_id,
            key=update["key"],
            value=update["value"],
            confidence=update.get("confidence", 0.8),
        )
    
    return {}
```

🧪 TESTE da Fase 3.1:

```bash
cd /opt/vps-agent/core
source venv/bin/activate
python3 -c "
from langgraph.state import AgentState
from langgraph.memory import AgentMemory
from langgraph.graph import build_agent_graph

# Testar memória
mem = AgentMemory()
mem.save_fact('test_user', 'name', {'value': 'Guilherme'})
facts = mem.get_user_facts('test_user')
print('Memória:', facts)

# Testar grafo
graph = build_agent_graph()
print('Grafo compilado:', type(graph))
print('✅ LangGraph OK')
"
```

---

### 3.2 Integrar LangGraph ao Telegram Bot

🟡 MODELO MÉDIO RECOMENDADO

**Instrução para o Kilocode:**
> Modifique o arquivo `/opt/vps-agent/core/telegram-bot/bot.py`. 
> Substitua APENAS a função `handle_message` pela versão abaixo.
> NÃO altere o restante do arquivo.

Localizar a função `handle_message` no bot.py e substituir por:

```python
@authorized_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de texto — conectado ao LangGraph."""
    import sys
    sys.path.insert(0, "/opt/vps-agent/core")
    from langgraph.graph import build_agent_graph
    from langgraph.memory import AgentMemory
    
    user_msg = update.message.text
    user_id = str(update.effective_user.id)
    mem = AgentMemory()
    
    # Salvar mensagem do usuário
    mem.save_message(user_id, "user", user_msg)
    
    # Rodar o grafo
    try:
        graph = build_agent_graph()
        result = graph.invoke({
            "user_id": user_id,
            "user_message": user_msg,
        })
        
        response = result.get("response", "🤷 Não sei o que responder.")
        
    except Exception as e:
        logger.error("erro_langgraph", error=str(e))
        response = f"⚠️ Erro no processamento: {str(e)[:200]}"
    
    # Salvar resposta do agente
    mem.save_message(user_id, "assistant", response)
    
    await update.message.reply_text(response, parse_mode="Markdown")
```

```bash
# Reiniciar o bot
sudo systemctl restart vps-agent-bot

# Verificar se reiniciou OK
sudo systemctl status vps-agent-bot
```

🧪 TESTE no Telegram:
1. Enviar "oi" → deve responder com mensagem de chat
2. Enviar "como está a ram?" → deve classificar como pergunta
3. Enviar "subir n8n" → deve classificar como task (sem skill ainda)

### ⛳ CHECKPOINT FASE 3 COMPLETA

```bash
echo "========================================="
echo "    CHECKPOINT FINAL — FASE 3"
echo "========================================="
echo ""
echo "1. LangGraph importável:"
cd /opt/vps-agent/core && source venv/bin/activate
python3 -c "from langgraph.graph import build_agent_graph; print('✅ OK')" 2>&1

echo "2. Memória funcional:"
python3 -c "
from langgraph.memory import AgentMemory
m = AgentMemory()
m.save_fact('checkpoint', 'test', {'ok': True})
r = m.get_user_facts('checkpoint')
print('✅ OK' if r else '❌ FALHOU')
" 2>&1

echo "3. Bot ativo:" && sudo systemctl is-active vps-agent-bot
echo "4. Mensagens no banco:"
docker exec vps-postgres psql -U vps_agent -d vps_agent \
    -c "SELECT COUNT(*) as total FROM conversation_log;" 2>/dev/null

FREE_MEM=$(free -m | awk '/Mem:/ {print $7}')
echo "5. RAM disponível: ${FREE_MEM} MB"
echo ""
echo "========================================="
```

🔴 **REVISÃO ESTRATÉGICA:** Esta é a metade do projeto. Antes de seguir:
1. Teste os 3 cenários no Telegram (chat, pergunta, tarefa)
2. Verifique que mensagens estão sendo salvas no banco
3. Revise com modelo robusto: "A estrutura de memória e grafo está adequada para as próximas fases?"

**Atualizar brief.md:**
```markdown
## Fase Atual: FASE 4
## Última ação: Fase 3 completa — LangGraph + Memória integrados ao Telegram
## Próxima ação: Fase 4.1 — Resource Manager
```

---

## FASE 4 — FERRAMENTAS SOB DEMANDA (Dias 13-15) {#fase-4}

### Objetivo
Criar o Resource Manager que sobe/desce containers conforme demanda, respeitando os 2.4 GB.

---

### 4.1 Resource Manager

🟡 MODELO MÉDIO RECOMENDADO

📋 COPIAR E COLAR — `/opt/vps-agent/core/resource-manager/manager.py`:

```python
"""
Resource Manager — Gerencia RAM subindo/descendo containers sob demanda.
Regra: nunca ultrapassar 2.4 GB total. Serviços core (~750 MB) sempre ligados.
"""
import subprocess
import json
import os
from typing import Optional
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()

# Configuração das ferramentas sob demanda
TOOLS_CONFIG = {
    "qdrant": {
        "compose_file": "/opt/vps-agent/tools/qdrant/docker-compose.yml",
        "ram_mb": 400,
        "health_cmd": "curl -sf http://127.0.0.1:6333/healthz",
        "description": "Busca vetorial / memória semântica",
    },
    "n8n": {
        "compose_file": "/opt/vps-agent/tools/n8n/docker-compose.yml",
        "ram_mb": 300,
        "health_cmd": "curl -sf http://127.0.0.1:5678/healthz",
        "description": "Automações no-code",
    },
    "flowise": {
        "compose_file": "/opt/vps-agent/tools/flowise/docker-compose.yml",
        "ram_mb": 350,
        "health_cmd": "curl -sf http://127.0.0.1:3000",
        "description": "Fluxos de LLM visuais",
    },
    "evolution-api": {
        "compose_file": "/opt/vps-agent/tools/evolution-api/docker-compose.yml",
        "ram_mb": 250,
        "health_cmd": "curl -sf http://127.0.0.1:8080/health",
        "description": "WhatsApp integration",
    },
}

# RAM reservada para core (PostgreSQL + Redis + Bot + LangGraph)
CORE_RAM_MB = 750
# RAM total da VPS
TOTAL_RAM_MB = 2400
# Margem de segurança
SAFETY_MARGIN_MB = 200


def get_available_ram() -> int:
    """Retorna RAM disponível em MB."""
    result = subprocess.run(
        ["free", "-m"], capture_output=True, text=True
    )
    lines = result.stdout.strip().split("\n")
    return int(lines[1].split()[6])


def get_running_tools() -> list:
    """Retorna lista de ferramentas sob demanda rodando."""
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    containers = result.stdout.strip().split("\n") if result.stdout.strip() else []
    
    running = []
    for tool_name, config in TOOLS_CONFIG.items():
        # Verifica se algum container da ferramenta está rodando
        if any(tool_name in c for c in containers):
            running.append(tool_name)
    return running


def can_start_tool(tool_name: str) -> tuple[bool, str]:
    """Verifica se é possível iniciar uma ferramenta."""
    if tool_name not in TOOLS_CONFIG:
        return False, f"Ferramenta '{tool_name}' não existe."
    
    available = get_available_ram()
    needed = TOOLS_CONFIG[tool_name]["ram_mb"]
    running = get_running_tools()
    
    if tool_name in running:
        return False, f"'{tool_name}' já está rodando."
    
    if len(running) >= 2:
        return False, (
            f"Já existem 2 ferramentas rodando ({', '.join(running)}). "
            f"Pare uma antes de iniciar outra."
        )
    
    if available < needed + SAFETY_MARGIN_MB:
        return False, (
            f"RAM insuficiente. Disponível: {available}MB. "
            f"Necessário: {needed}MB + {SAFETY_MARGIN_MB}MB margem."
        )
    
    return True, "OK"


def start_tool(tool_name: str) -> tuple[bool, str]:
    """Inicia uma ferramenta sob demanda."""
    can_start, reason = can_start_tool(tool_name)
    if not can_start:
        return False, reason
    
    config = TOOLS_CONFIG[tool_name]
    compose_file = config["compose_file"]
    
    if not os.path.exists(compose_file):
        return False, f"Arquivo compose não encontrado: {compose_file}"
    
    logger.info("iniciando_ferramenta", tool=tool_name, ram_estimada=config["ram_mb"])
    
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d"],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        return False, f"Erro ao iniciar: {result.stderr[:300]}"
    
    return True, f"✅ {tool_name} iniciado com sucesso."


def stop_tool(tool_name: str) -> tuple[bool, str]:
    """Para uma ferramenta sob demanda."""
    if tool_name not in TOOLS_CONFIG:
        return False, f"Ferramenta '{tool_name}' não existe."
    
    config = TOOLS_CONFIG[tool_name]
    compose_file = config["compose_file"]
    
    if not os.path.exists(compose_file):
        return False, f"Arquivo compose não encontrado: {compose_file}"
    
    logger.info("parando_ferramenta", tool=tool_name)
    
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "down"],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        return False, f"Erro ao parar: {result.stderr[:300]}"
    
    return True, f"✅ {tool_name} parado."


def get_tools_status() -> dict:
    """Retorna status de todas as ferramentas."""
    running = get_running_tools()
    available_ram = get_available_ram()
    
    status = {}
    for name, config in TOOLS_CONFIG.items():
        is_running = name in running
        can_start_it, reason = can_start_tool(name) if not is_running else (False, "Já rodando")
        
        status[name] = {
            "running": is_running,
            "ram_mb": config["ram_mb"],
            "can_start": can_start_it,
            "reason": reason if not can_start_it and not is_running else "",
            "description": config["description"],
        }
    
    return {
        "tools": status,
        "running_count": len(running),
        "available_ram_mb": available_ram,
        "max_simultaneous": 2,
    }
```

### 4.2 Docker Compose das ferramentas

🟢 MODELO ECONÔMICO OK

Criar um docker-compose mínimo para cada ferramenta. Abaixo os dois mais importantes (Qdrant e n8n). Os demais seguem o mesmo padrão.

📋 `/opt/vps-agent/tools/qdrant/docker-compose.yml`:

```yaml
version: "3.8"
services:
  qdrant:
    image: qdrant/qdrant:v1.12.6
    container_name: vps-qdrant
    restart: unless-stopped
    volumes:
      - /opt/vps-agent/data/qdrant-storage:/qdrant/storage
    ports:
      - "127.0.0.1:6333:6333"
    deploy:
      resources:
        limits:
          memory: 400M
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334
    networks:
      - vps-core-network

networks:
  vps-core-network:
    external: true
```

📋 `/opt/vps-agent/tools/n8n/docker-compose.yml`:

```yaml
version: "3.8"
services:
  n8n:
    image: n8nio/n8n:1.73.1
    container_name: vps-n8n
    restart: unless-stopped
    volumes:
      - /opt/vps-agent/tools/n8n/data:/home/node/.n8n
    ports:
      - "127.0.0.1:5678:5678"
    deploy:
      resources:
        limits:
          memory: 300M
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER:-admin}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD:-TROCAR}
    networks:
      - vps-core-network

networks:
  vps-core-network:
    external: true
```

📋 Criar os diretórios de dados:

```bash
mkdir -p /opt/vps-agent/tools/n8n/data
mkdir -p /opt/vps-agent/tools/flowise/data
```

### 4.3 Integrar Resource Manager ao Bot

🟡 MODELO MÉDIO RECOMENDADO

**Instrução para o Kilocode:**
> Adicione estes comandos ao bot.py. NÃO substitua os handlers existentes, ADICIONE os novos.

Adicionar ao bot.py, antes de `def main()`:

```python
@authorized_only
async def cmd_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /tools — lista ferramentas e status."""
    import sys
    sys.path.insert(0, "/opt/vps-agent/core")
    from resource_manager.manager import get_tools_status
    
    status = get_tools_status()
    
    lines = [f"🔧 **Ferramentas** (RAM livre: {status['available_ram_mb']}MB)\n"]
    
    for name, info in status["tools"].items():
        icon = "🟢" if info["running"] else "⚪"
        ram = f"{info['ram_mb']}MB"
        lines.append(f"{icon} **{name}** ({ram}) — {info['description']}")
    
    lines.append(f"\n🔄 Rodando: {status['running_count']}/{status['max_simultaneous']}")
    lines.append("\nUse: `/start_tool nome` ou `/stop_tool nome`")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@authorized_only
async def cmd_start_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /start_tool — inicia uma ferramenta."""
    import sys
    sys.path.insert(0, "/opt/vps-agent/core")
    from resource_manager.manager import start_tool
    
    args = context.args
    if not args:
        await update.message.reply_text("Uso: `/start_tool nome`\nEx: `/start_tool qdrant`", parse_mode="Markdown")
        return
    
    tool_name = args[0].lower()
    await update.message.reply_text(f"⏳ Iniciando {tool_name}...")
    
    success, message = start_tool(tool_name)
    await update.message.reply_text(message)


@authorized_only
async def cmd_stop_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /stop_tool — para uma ferramenta."""
    import sys
    sys.path.insert(0, "/opt/vps-agent/core")
    from resource_manager.manager import stop_tool
    
    args = context.args
    if not args:
        await update.message.reply_text("Uso: `/stop_tool nome`\nEx: `/stop_tool qdrant`", parse_mode="Markdown")
        return
    
    tool_name = args[0].lower()
    success, message = stop_tool(tool_name)
    await update.message.reply_text(message)
```

Adicionar os handlers no `main()`, junto dos existentes:

```python
    app.add_handler(CommandHandler("tools", cmd_tools))
    app.add_handler(CommandHandler("start_tool", cmd_start_tool))
    app.add_handler(CommandHandler("stop_tool", cmd_stop_tool))
```

```bash
sudo systemctl restart vps-agent-bot
```

### ⛳ CHECKPOINT FASE 4 COMPLETA

Testar no Telegram:
1. `/tools` → deve listar todas as ferramentas com status
2. `/start_tool qdrant` → deve subir o Qdrant
3. `/tools` → Qdrant deve aparecer como 🟢
4. `/ram` → verificar uso de memória com Qdrant ativo
5. `/stop_tool qdrant` → deve descer o Qdrant
6. Tentar `/start_tool ferramenta_fake` → deve dar erro

**Atualizar brief.md:**
```markdown
## Fase Atual: FASE 5
## Última ação: Fase 4 completa — Resource Manager + ferramentas sob demanda
## Próxima ação: Fase 5.1 — Isolamento do Moltbot
```

---

## FASE 5 — MOLTBOT ISOLADO (Dias 16-17) {#fase-5}

### Objetivo
Criar ambiente sandbox isolado para testar o Moltbot sem comprometer a segurança do agente principal.

🔴 **MODELO ROBUSTO RECOMENDADO** para esta fase — decisões de segurança.

---

### 5.1 Criar namespace isolado

📋 COPIAR E COLAR — `/opt/vps-agent/sandbox/docker-compose.sandbox.yml`:

```yaml
# /opt/vps-agent/sandbox/docker-compose.sandbox.yml
# ISOLADO do core — rede separada, sem acesso aos serviços do agente

version: "3.8"

services:
  moltbot-sandbox:
    image: ubuntu:24.04
    container_name: vps-sandbox-moltbot
    restart: "no"
    command: sleep infinity
    deploy:
      resources:
        limits:
          memory: 500M
          cpus: "1.0"
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    read_only: false
    tmpfs:
      - /tmp:size=100M
    volumes:
      - /opt/vps-agent/sandbox/workspace:/workspace
    networks:
      - sandbox-network
    # SEM acesso à rede do core
    # SEM acesso ao Docker socket
    # SEM acesso aos volumes de dados do agente

networks:
  sandbox-network:
    name: vps-sandbox-network
    driver: bridge
    internal: false  # Permitir acesso à internet para instalar pacotes
```

📋 Criar diretório de trabalho:

```bash
mkdir -p /opt/vps-agent/sandbox/workspace
```

**Regras de segurança do sandbox:**
- Rede separada (sandbox-network) — sem acesso ao PostgreSQL/Redis do core
- Sem acesso ao Docker socket — não pode controlar outros containers
- Limites rígidos de RAM (500 MB) e CPU (1 core)
- `no-new-privileges` — não pode escalar privilégios
- Capabilities mínimas
- Volume isolado (/workspace) — sem acesso aos dados do agente

### 5.2 Integrar sandbox ao Resource Manager

Adicionar ao `TOOLS_CONFIG` em `manager.py`:

```python
    "moltbot": {
        "compose_file": "/opt/vps-agent/sandbox/docker-compose.sandbox.yml",
        "ram_mb": 500,
        "health_cmd": "docker exec vps-sandbox-moltbot echo ok",
        "description": "Sandbox isolado para testes do Moltbot",
    },
```

❌ ARMADILHA: O Moltbot precisa de instalação manual dentro do container após subir. O sandbox é só o ambiente. A instalação do Moltbot em si deve ser feita com cuidado e revisão.

### ⛳ CHECKPOINT FASE 5 COMPLETA

```bash
echo "=== CHECKPOINT FASE 5 ==="

# 1. Subir sandbox
cd /opt/vps-agent/sandbox
docker compose -f docker-compose.sandbox.yml up -d

# 2. Verificar isolamento - NÃO deve acessar PostgreSQL do core
docker exec vps-sandbox-moltbot bash -c "apt-get update -qq && apt-get install -qq -y curl > /dev/null 2>&1 && curl -s http://127.0.0.1:5432 || echo '✅ PostgreSQL inacessível (esperado)'"

# 3. Verificar que TEM internet
docker exec vps-sandbox-moltbot bash -c "curl -s -o /dev/null -w '%{http_code}' https://google.com || echo 'Sem internet'"

# 4. Verificar limites de RAM
docker stats --no-stream --format "{{.Name}}: {{.MemUsage}} / {{.MemPerc}}" vps-sandbox-moltbot

# 5. Descer sandbox
docker compose -f docker-compose.sandbox.yml down

echo "=== FIM ==="
```

---

## FASE 6 — MONITORAMENTO + HARDENING (Dias 18-20) {#fase-6}

### Objetivo
Garantir que o sistema é observável, resiliente e seguro.

---

### 6.1 Script de monitoramento

🟢 MODELO ECONÔMICO OK

📋 COPIAR E COLAR — `/opt/vps-agent/scripts/health-monitor.sh`:

```bash
#!/bin/bash
# /opt/vps-agent/scripts/health-monitor.sh
# Roda a cada 5 minutos via cron. Envia alerta se algo estiver errado.

LOG_FILE="/opt/vps-agent/logs/health.log"
ALERT_FILE="/tmp/vps-agent-alert"

log() {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | $1" >> "$LOG_FILE"
}

alert() {
    echo "$1" >> "$ALERT_FILE"
    log "ALERT: $1"
}

# Limpar alertas anteriores
> "$ALERT_FILE"

# 1. Checar RAM
AVAILABLE=$(free -m | awk '/Mem:/ {print $7}')
if [ "$AVAILABLE" -lt 200 ]; then
    alert "⚠️ RAM CRÍTICA: apenas ${AVAILABLE}MB disponível!"
fi

# 2. Checar PostgreSQL
if ! docker exec vps-postgres pg_isready -U vps_agent > /dev/null 2>&1; then
    alert "❌ PostgreSQL DOWN!"
    docker compose -f /opt/vps-agent/core/docker-compose.core.yml restart postgres
fi

# 3. Checar Redis
if ! docker exec vps-redis redis-cli ping > /dev/null 2>&1; then
    alert "❌ Redis DOWN!"
    docker compose -f /opt/vps-agent/core/docker-compose.core.yml restart redis
fi

# 4. Checar Bot
if ! systemctl is-active --quiet vps-agent-bot; then
    alert "❌ Telegram Bot DOWN!"
    systemctl restart vps-agent-bot
fi

# 5. Checar disco
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_USAGE" -gt 85 ]; then
    alert "⚠️ Disco ${DISK_USAGE}% usado!"
fi

# 6. Log normal
log "OK | RAM:${AVAILABLE}MB | Disco:${DISK_USAGE}%"

# Se houve alertas, notificar via bot (se estiver rodando)
if [ -s "$ALERT_FILE" ]; then
    ALERTS=$(cat "$ALERT_FILE")
    # Envia via Redis pub/sub (o bot escuta)
    docker exec vps-redis redis-cli PUBLISH vps-alerts "$ALERTS" 2>/dev/null || true
fi
```

```bash
chmod +x /opt/vps-agent/scripts/health-monitor.sh
```

📋 Adicionar ao cron:

```bash
# Abrir crontab do deploy
crontab -e

# Adicionar esta linha:
*/5 * * * * /opt/vps-agent/scripts/health-monitor.sh
```

### 6.2 Backup automático

🟢 MODELO ECONÔMICO OK

📋 COPIAR E COLAR — `/opt/vps-agent/scripts/backup.sh`:

```bash
#!/bin/bash
# /opt/vps-agent/scripts/backup.sh
# Backup diário do PostgreSQL e configs

BACKUP_DIR="/opt/vps-agent/backups"
DATE=$(date +%Y%m%d_%H%M)

# Backup PostgreSQL
docker exec vps-postgres pg_dump -U vps_agent vps_agent | gzip > "${BACKUP_DIR}/db_${DATE}.sql.gz"

# Backup configs
tar czf "${BACKUP_DIR}/configs_${DATE}.tar.gz" /opt/vps-agent/configs/ /opt/vps-agent/core/.env 2>/dev/null

# Manter apenas últimos 7 dias
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | Backup completo: db_${DATE}.sql.gz" >> /opt/vps-agent/logs/backup.log
```

```bash
chmod +x /opt/vps-agent/scripts/backup.sh

# Cron: todo dia às 3h da manhã
crontab -e
# Adicionar:
0 3 * * * /opt/vps-agent/scripts/backup.sh
```

### 6.3 Hardening final

🟢 MODELO ECONÔMICO OK

📋 COPIAR E COLAR:

```bash
# 1. Garantir que portas sensíveis só escutam localhost
echo "=== Verificando portas ==="
ss -tlnp | grep -E "5432|6379|6333|5678|3000|8080"
# TODAS devem mostrar 127.0.0.1, NUNCA 0.0.0.0

# 2. Desabilitar login root via SSH (se ainda não feito)
sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# 3. Proteger arquivos sensíveis
chmod 600 /opt/vps-agent/core/.env
chmod 700 /opt/vps-agent/configs
chmod 700 /opt/vps-agent/backups

# 4. Habilitar atualizações automáticas de segurança
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### ⛳ CHECKPOINT FINAL — FASE 6 E PROJETO COMPLETO

```bash
echo "=============================================="
echo "   CHECKPOINT FINAL — VPS-AGENT v2 COMPLETO"
echo "=============================================="
echo ""

echo "--- INFRAESTRUTURA ---"
echo "1. Docker:" && docker --version | cut -d' ' -f3
echo "2. PostgreSQL:" && docker exec vps-postgres pg_isready -U vps_agent
echo "3. Redis:" && docker exec vps-redis redis-cli ping
echo ""

echo "--- AGENTE ---"
echo "4. Bot Telegram:" && sudo systemctl is-active vps-agent-bot
echo "5. LangGraph:"
cd /opt/vps-agent/core && source venv/bin/activate
python3 -c "from langgraph.graph import build_agent_graph; print('✅ OK')" 2>&1
echo ""

echo "--- RESOURCE MANAGER ---"
echo "6. Ferramentas configuradas:"
python3 -c "
from resource_manager.manager import get_tools_status
s = get_tools_status()
for name, info in s['tools'].items():
    icon = '🟢' if info['running'] else '⚪'
    print(f'  {icon} {name} ({info[\"ram_mb\"]}MB)')
print(f'  RAM disponível: {s[\"available_ram_mb\"]}MB')
" 2>&1

echo ""
echo "--- SEGURANÇA ---"
echo "7. UFW:" && sudo ufw status | head -1
echo "8. Fail2ban:" && sudo fail2ban-client status sshd 2>/dev/null | grep "Currently"
echo "9. Root SSH:" && grep "PermitRootLogin" /etc/ssh/sshd_config | head -1
echo "10. Portas expostas (deve ser tudo 127.0.0.1):"
ss -tlnp 2>/dev/null | grep -E "5432|6379" | awk '{print "    "$4}'
echo ""

echo "--- MONITORAMENTO ---"
echo "11. Cron jobs:" && crontab -l 2>/dev/null | grep -c "vps-agent"
echo "12. Health log:" && tail -1 /opt/vps-agent/logs/health.log 2>/dev/null || echo "Ainda sem logs"
echo "13. Backups:" && ls -la /opt/vps-agent/backups/*.gz 2>/dev/null | wc -l

echo ""
FREE_MEM=$(free -m | awk '/Mem:/ {print $7}')
echo "--- RECURSOS ---"
echo "14. RAM disponível: ${FREE_MEM} MB"
docker stats --no-stream --format "    {{.Name}}: {{.MemUsage}}" 2>/dev/null
echo ""
echo "=============================================="
echo "   🎉 Se todos os itens estão OK,"
echo "   a VPS-Agente v2 está operacional!"
echo "=============================================="
```

---

## 9. MAPA DE CUSTOS DE MODELO POR TAREFA {#custos}

| Fase | Tarefa | Modelo Recomendado | Justificativa |
|---|---|---|---|
| 1.1-1.3 | Hardening, Docker, diretórios | 🟢 Econômico | Copy-paste, sem lógica |
| 1.4 | PostgreSQL + Redis | 🟢 Econômico | Docker compose pronto |
| 2.1 | Python + deps | 🟢 Econômico | Instalação padrão |
| 2.2 | Telegram Bot | 🟡 Médio | Integração com lógica |
| 2.3 | Systemd service | 🟢 Econômico | Config pronta |
| 3.1 | LangGraph estrutura | 🟡 Médio | Lógica de grafo |
| 3.2 | Integrar LangGraph ao bot | 🟡 Médio | Integração complexa |
| 4.1 | Resource Manager | 🟡 Médio | Lógica de gestão RAM |
| 4.2 | Docker Compose ferramentas | 🟢 Econômico | Config pronta |
| 4.3 | Integrar ao bot | 🟡 Médio | Novos handlers |
| 5.1 | Sandbox Moltbot | 🔴 Robusto | Decisões de segurança |
| 5.2 | Integrar sandbox | 🟢 Econômico | Apenas config |
| 6.1-6.3 | Monitoramento + hardening | 🟢 Econômico | Scripts prontos |
| Revisões | Checkpoints estratégicos | 🔴 Robusto | Análise crítica |

**Estimativa de custo total (via OpenRouter/API):**
- ~70% das tarefas com modelo econômico ($0.10-0.30/M tokens)
- ~20% com modelo médio ($1-3/M tokens)
- ~10% revisões com modelo robusto ($10-15/M tokens)
- **Custo estimado total do projeto: $5-15 USD** (dependendo de quantas revisões)

---

## 10. TROUBLESHOOTING {#troubleshooting}

### Problema: Container não sobe
```bash
# Verificar logs
docker logs NOME_DO_CONTAINER --tail 50

# Verificar RAM
free -m

# Se RAM insuficiente, parar ferramentas sob demanda
docker compose -f /opt/vps-agent/tools/FERRAMENTA/docker-compose.yml down
```

### Problema: Bot não responde no Telegram
```bash
# Verificar service
sudo systemctl status vps-agent-bot

# Verificar logs
journalctl -u vps-agent-bot -f --no-pager -n 50

# Reiniciar
sudo systemctl restart vps-agent-bot
```

### Problema: PostgreSQL sem espaço
```bash
# Verificar tamanho do banco
docker exec vps-postgres psql -U vps_agent -d vps_agent \
    -c "SELECT pg_size_pretty(pg_database_size('vps_agent'));"

# Limpar logs de conversa antigos (manter últimos 30 dias)
docker exec vps-postgres psql -U vps_agent -d vps_agent \
    -c "DELETE FROM conversation_log WHERE created_at < NOW() - INTERVAL '30 days';"
```

### Problema: Modelo barato "inventou" código errado
1. NÃO rode o código inventado
2. Copie o erro para o chat
3. Cole a instrução original deste documento
4. Peça ao modelo para seguir EXATAMENTE o que está no documento
5. Se persistir, troque para modelo médio/robusto para essa tarefa

---

## PRÓXIMOS PASSOS (Pós v2)

Após a implantação completa, as evoluções naturais são:

1. **Conectar LLM ao LangGraph** — substituir nós de regras por chamadas a API de LLM
2. **Qdrant para memória semântica** — busca por similaridade nas conversas
3. **AGENT.md portável** — document que descreve como o agente funciona, independente do CLI
4. **Skills auto-aprendidas** — agente registra novos patterns de sucesso
5. **Multi-usuário** — expandir para mais de um usuário no Telegram

---

*Documento gerado em 06/02/2026 — VPS-Agente v2*
*Para dúvidas ou revisão, consulte o chat original: https://claude.ai/chat/82bc79f2-a973-4458-918b-3041892f8a4b*
