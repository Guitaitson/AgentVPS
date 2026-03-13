# Voice Device Companion (Windows)

Este helper monitora drives removiveis, detecta o gravador de voz, monta um lote local de pre-triagem e so envia os arquivos aprovados para a VPS via `scp` + `ssh`.

## Arquivos
- `voice-device-config.example.json`: modelo de configuracao.
- `voice_device_watcher.ps1`: loop principal.
- `start_voice_device_watcher.ps1`: inicializacao simples com policy local.

## Pre-requisitos
- Windows com OpenSSH (`scp.exe`) disponivel.
- Chave SSH configurada para a VPS.
- Pasta de inbox de voz existente na VPS.

## Passos
1. Copie `voice-device-config.example.json` para `voice-device-config.json`.
2. Ajuste `volumeLabel`, `importPath`, `extensions`, `stagingDir`, `preTriageDir`, `recorderProfile`, `reviewDurationMinutes`, `minimumDurationSeconds`, `minimumFileSizeKb`, `sshTarget`, `remoteStagingDir`, `remoteInboxDir` e `remoteManifestDir`.
3. Se usar chave dedicada, preencha `sshKeyPath`.
4. Rode `./start_voice_device_watcher.ps1`.

## Observacoes
- O helper mantem estado local em `%LOCALAPPDATA%\\AgentVPS\\voice-device-state.json` para nao reenviar arquivos ja aprovados e publicados.
- Cada conexao nova gera um lote local com `batch_manifest.json` e `batch_review.json` dentro de `preTriageDir`.
- O gate local usa metadata basica por arquivo: tamanho, duracao quando `ffprobe` estiver disponivel, e duplicidade de upload.
- O upload passa primeiro por `remoteStagingDir`, instala os audios aprovados em `remoteInboxDir` e publica o manifesto do lote em `remoteManifestDir`.
- A janela pergunta se deve enviar os aprovados agora ou abrir a pasta do lote para revisao local.
- O processamento do audio acontece na VPS via `/contextsync` ou, para avaliar sem side effects, `/contextsync inspect`.
- Para melhorar a qualidade de entrada, revise tambem [docs/VOICE_RECORDER_TUNING.md](C:\Users\Pc Gamer\.claude-worktrees\AgenteVPS\vigorous-elbakyan\docs\VOICE_RECORDER_TUNING.md) e o `FACTORY.TXT` do gravador.
