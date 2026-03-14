# Voice Recorder Tuning

Objetivo: melhorar a qualidade da entrada para ASR/memoria, reduzindo ruido e arquivos excessivamente longos.

## Arquivo de configuracao

No gravador atual, a configuracao operacional fica em `FACTORY.TXT`.

Campos relevantes observados:
- `VOR`: voice-activated recording
- `DENOISE`: intensidade de reducao de ruido
- `AGC`: automatic gain control
- `BIT RATE`: perfil de gravacao
- `GAIN`: sensibilidade do microfone
- `SECTION`: autosplit de arquivo em minutos

## Perfil em teste atual

Configuracao aplicada agora no dispositivo:

```text
VOR:3
DENOISE:20
AGC:20
BIT RATE:7
GAIN:5
SECTION:(060)
```

Leitura tecnica:
- `VOR:3`: corta mais silencio/ambiente que o perfil anterior
- `DENOISE:20`: filtro mais forte contra ruido constante
- `AGC:20`: sobe a captacao, mas ainda abaixo do maximo absoluto
- `BIT RATE:7`: privilegia fidelidade para ASR
- `GAIN:5`: aumenta a sensibilidade do microfone
- `SECTION:(060)`: continua quebrando lotes longos em partes mais trataveis

## Perfil conservador alternativo

As configuracoes abaixo ficam como fallback caso o perfil atual gere artefatos excessivos ou palavras "inventadas" pelo modelo.

```text
VOR:1
DENOISE:10
AGC:16
BIT RATE:6
GAIN:4
SECTION:(060)
```

Racional:
- o perfil atual prioriza captacao e fidelidade
- o perfil conservador reduz risco de superprocessamento do audio pelo proprio gravador

## Processo seguro

1. fazer backup do `FACTORY.TXT` original
2. aplicar o perfil recomendado
3. testar um lote curto de 20-40 minutos
4. passar o lote pela pre-triagem local do companion Windows
5. se necessario, rodar `/contextsync inspect` na VPS para avaliar sem gerar memoria
6. revisar transcript, quality score e itens que iriam para review
7. iterar antes de voltar para gravacoes muito longas

## Ciclo end-to-end recomendado

Para um lote organico do dia:

1. conectar o gravador e rodar `voice_device_watcher.ps1 -RunOnce -BatchAction send -RemoteAction inspect`
2. abrir o lote local gerado em `preTriageDir`
3. revisar `batch_review.json` e `remote_inspect.json`
4. se `green_gate.passed=true`, repetir com `-RemoteAction sync_if_green` para efetivar memoria no mesmo ciclo
5. se `green_gate.failed_reasons` incluir `review_dominates_batch`, segregar os arquivos mais longos antes de novo envio
6. se `green_gate.failed_reasons` incluir `conservative_profile_required`, reduzir a agressividade do perfil atual ou voltar para o perfil conservador

## Heuristicas praticas de microajuste

- `muitos trechos curtos e fragmentados`: reduzir `VOR` primeiro
- `pouca fala util detectada`: revisar `VOR` e padrao de pausas longas
- `baixa estabilidade lexical na transcricao`: reduzir `DENOISE` antes de mexer em bitrate
- `linhas muito curtas, possivel segmentacao ruidosa`: reduzir `AGC` se o volume estiver oscilando
- `audio longo com vocabulario pouco consistente`: manter `SECTION:(060)` e segregar arquivos longos no gate local

## Observacao importante

O proprio arquivo do gravador avisa que, no Windows 11, salvar via Notepad e o caminho mais confiavel para a configuracao surtir efeito. Isso deve ser respeitado se o dispositivo ignorar edicoes programaticas.
