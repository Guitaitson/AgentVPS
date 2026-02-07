# Guia: SSH Tunnel para Claude CLI OAuth

O Claude CLI com assinatura requer autenticação OAuth via navegador. Como a VPS é headless, usamos SSH tunnel para abrir o browser no seu PC.

## Método 1: SSH com Forwarding (Recomendado)

### Passo 1: Iniciar SSH com Portal de Browser

No seu **PC local** (Windows/Mac/Linux), execute:

```bash
# Linux/Mac
ssh -L 9999:localhost:9999 root@107.175.1.42

# Windows (PowerShell)
ssh -L 9999:localhost:9999 root@107.175.1.42
```

Isso cria um túnel da porta 9999 do seu PC para a VPS.

### Passo 2: Na VPS (novo terminal)

```bash
# Exportar variáveis e iniciar autenticação
export DISPLAY=:0
claude setup-token
```

O comando vai abrir uma URL no seu navegador local (http://localhost:9999/...).

### Passo 3: Fazer Login

1. Você será redirecionado para o login da Anthropic
2. Faça login com: `guilhermetaitson@gmail.com`
3. Autorize o acesso
4. O token será salvo automaticamente

---

## Método 2: URL Manual (Mais Simples)

### Passo 1: Na VPS

```bash
export DISPLAY=:0
claude setup-token
```

O comando vai exibir uma **URL** (algo como `https://claude.com/auth/...`).

### Passo 2: No seu PC

1. Copie a URL exibida
2. Cole no navegador do seu PC
3. Faça login na Anthropic
4. **O token será salvo na VPS automaticamente**

---

## Método 3: Usar API Key (Sem OAuth)

Se preferir não usar OAuth, pode gerar uma API Key no console da Anthropic:

1. Acesse: https://console.anthropic.com/settings/keys
2. Crie uma nova API Key
3. Configure na VPS:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-sua-chave-aqui"
echo "export ANTHROPIC_API_KEY='sk-ant-api03-sua-chave-aqui'" >> ~/.bashrc
```

**Nota:** API Keys usam cobrança por uso. OAuth com assinatura é diferente.

---

## Verificar Autenticação

Após configurar, verify:

```bash
# Status do CLI
agent-cli status

# Testar Claude
claude --version
```

---

## Solução de Problemas

### "Browser não encontrado"
```bash
# Instalar browser leve na VPS
apt-get install -y firefox-esr
# ou
apt-get install -y chromium-browser
```

### "Display não configurado"
```bash
export DISPLAY=:0
# ou
export DISPLAY=:1
```

### Token expirado
```bash
claude setup-token
# Vai pedir nova autenticação
```

---

## Fontes

- [Reddit: bypass OAuth login](https://www.reddit.com/r/ClaudeAI/comments/1mideyc/how_to_bypass_claude_code_initial_oauth_login/)
- [Claude Code Docs: Authentication](https://code.claude.com/docs/en/authentication)
