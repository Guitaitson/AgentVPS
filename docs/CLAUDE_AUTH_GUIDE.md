# Guia de Autenticação Claude CLI

⚠️ **Aviso:** O comando `claude setup-token` é interativo e pode travar em VPS headless.

## Métodos Seguros

### Método 1: Timeout com Redirecionamento (Recomendado)

```bash
# Executar com timeout de 30 segundos
timeout 30 claude setup-token > /tmp/claude_auth_url.txt 2>&1 &

# Verificar resultado após 2 segundos
sleep 2
cat /tmp/claude_auth_url.txt
```

Se gerou URL, copie e abra no seu navegador.

---

### Método 2: API Key (Mais Simples)

1. Acesse: https://console.anthropic.com/settings/keys
2. Crie API Key
3. Configure:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-sua-chave"
echo "export ANTHROPIC_API_KEY='sk-ant-api03-sua-chave'" >> ~/.bashrc
```

---

### Método 3: SSH Tunnel

```bash
# No seu PC (Linux/Mac)
ssh -L 9999:localhost:9999 root@107.175.1.42

# Na VPS (novo terminal)
export DISPLAY=:0
claude setup-token
```

---

### Verificar Autenticação

```bash
claude --version
claude "Hello" --print
```

---

## Solução de Problemas

| Problema | Solução |
|----------|---------|
| Comando travou | Ctrl+C, use timeout |
| Sem browser | Use API Key |
| Token expirado | `claude setup-token` novamente |
| Erro de rede | Verifique conectividade |

---

## Boas Práticas

1. **Sempre use timeout** em comandos interativos
2. **Redirecione output** para arquivo
3. **Documente URLs** antes de abrir
4. **Teste com timeout** antes de uso em produção
