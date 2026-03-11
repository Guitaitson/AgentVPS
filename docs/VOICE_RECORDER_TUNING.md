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
4. revisar transcript e quality score
5. iterar antes de voltar para gravacoes muito longas

## Observacao importante

O proprio arquivo do gravador avisa que, no Windows 11, salvar via Notepad e o caminho mais confiavel para a configuracao surtir efeito. Isso deve ser respeitado se o dispositivo ignorar edicoes programaticas.
