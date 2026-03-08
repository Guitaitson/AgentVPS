# Guia: SSH Tunnel (Headless VPS)

Use este guia quando você precisa acessar serviços locais da VPS (por exemplo MCP, OAuth callback) a partir do seu computador.

## Pré-requisitos

- SSH funcional para sua VPS
- Serviço alvo ouvindo em `localhost` na VPS
- Host e usuário definidos em variáveis locais (não versionar)

## Exemplo Genérico

No computador local:

```bash
ssh -L <PORTA_LOCAL>:localhost:<PORTA_REMOTA> <USUARIO>@<SEU_HOST_VPS>
```

Exemplo para MCP na porta `8765`:

```bash
ssh -L 8765:localhost:8765 <USUARIO>@<SEU_HOST_VPS>
```

Depois disso, no seu computador:

```bash
curl http://localhost:8765/health
```

## Boas Práticas

- Não publique IP, usuário, senha, tokens ou e-mails pessoais em arquivos versionados.
- Prefira autenticação por chave SSH.
- Mantenha serviços sensíveis bindados em `127.0.0.1` na VPS.
- Se expor um túnel para terceiros, use autenticação adicional (`X-API-Key`, proxy, ACL).
