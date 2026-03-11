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

## Perfil recomendado para AgentVPS

As configuracoes abaixo sao uma inferencia pragmatica a partir do comportamento do dispositivo e do resultado ruim do primeiro lote de 5h. O objetivo nao e audio "bonito"; e ASR mais estavel.

```text
VOR:1
DENOISE:10
AGC:16
BIT RATE:6
GAIN:4
SECTION:(060)
```

Racional:
- `VOR:1`: reduz silencio/ambiente sem cortar tanto quanto sensibilidades mais agressivas
- `DENOISE:10`: menos agressivo que o valor anterior, para evitar artefatos
- `AGC:16`: sai do maximo, que tende a puxar ruido ambiente
- `BIT RATE:6`: sai do modo `4` observado como `Translate ON`
- `GAIN:4`: leve aumento de captacao sem exagerar
- `SECTION:(060)`: evita lotes gigantes e facilita revisao/descartes

## Processo seguro

1. fazer backup do `FACTORY.TXT` original
2. aplicar o perfil recomendado
3. testar um lote curto de 20-40 minutos
4. revisar transcript e quality score
5. iterar antes de voltar para gravacoes muito longas

## Observacao importante

O proprio arquivo do gravador avisa que, no Windows 11, salvar via Notepad e o caminho mais confiavel para a configuracao surtir efeito. Isso deve ser respeitado se o dispositivo ignorar edicoes programaticas.
