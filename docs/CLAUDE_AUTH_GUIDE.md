# Guia de Autenticação Claude CLI

## Opção 1: OAuth (recomendado para assinatura)

Na VPS:

```bash
claude setup-token
```

Se a VPS for headless, use túnel SSH conforme [SSH_TUNNEL_GUIDE.md](SSH_TUNNEL_GUIDE.md).

## Opção 2: API Key (uso pago por token)

```bash
export ANTHROPIC_API_KEY="sua-chave-aqui"
```

Não versione chaves em `.md`, `.env.example` ou scripts.

## Verificação

```bash
claude --version
```

## Segurança

- Nunca publique e-mail pessoal, host real ou credenciais em documentação.
- Guarde segredos apenas em `.env` privado (fora do git) ou secret manager.
