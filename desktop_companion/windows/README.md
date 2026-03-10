# Voice Device Companion (Windows)

Este helper monitora drives removiveis, detecta o gravador de voz, pergunta se deve enviar os arquivos novos para a VPS e usa `scp` para publicar na inbox do AgentVPS.

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
2. Ajuste `volumeLabel`, `importPath`, `extensions`, `stagingDir`, `sshTarget` e `remoteInboxDir`.
3. Se usar chave dedicada, preencha `sshKeyPath`.
4. Rode `./start_voice_device_watcher.ps1`.

## Observacoes
- O helper mantem um manifesto local em `%LOCALAPPDATA%\\AgentVPS\\voice-device-state.json` para nao reenviar arquivos duplicados.
- A pergunta aparece apenas quando um drive elegivel e conectado com arquivos novos.
- O processamento do audio acontece na VPS via `/contextsync` ou lote automatico.
