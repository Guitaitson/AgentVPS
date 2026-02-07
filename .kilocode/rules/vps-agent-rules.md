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

7. **Moltbot NÃO faz parte deste projeto**
   - Remover qualquer referência ao Moltbot

## PADRÕES DE CÓDIGO
- Python: 3.11+, type hints, docstrings
- Docker: sempre usar versões fixas de imagem (ex: postgres:16, não postgres:latest)
- Arquivos de config: YAML quando possível
- Logs: formato JSON estruturado
