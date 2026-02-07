#!/bin/bash
# VPS-Agente v2 - CLI Switcher
# Permite alternar entre Claude CLI e Kilocode CLI

set -e

# Carregar variáveis do bashrc (forçar shell interativo)
bash -i -c 'source ~/.bashrc' 2>/dev/null || true

# Se não carregou via bash -i, tentar ler diretamente
if [ -z "$KILO_API_KEY" ] && [ -f ~/.bashrc ]; then
    export KILO_API_KEY=$(grep "KILO_API_KEY=" ~/.bashrc | head -1 | cut -d"'" -f2 | cut -d'"' -f2 || echo "")
    export OPENROUTER_API_KEY=$(grep "OPENROUTER_API_KEY=" ~/.bashrc | head -1 | cut -d'=' -f2 | cut -d'"' -f2 || echo "")
    export ANTHROPIC_API_KEY=$(grep "ANTHROPIC_API_KEY=" ~/.bashrc | head -1 | cut -d"'" -f2 | cut -d'"' -f2 || echo "")
fi

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════╗"
echo "║           VPS-Agente v2 - CLI Switcher               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Mostrar status atual
show_status() {
    echo -e "${YELLOW}Status atual:${NC}"
    
    # Verificar CLI ativo
    if [ -n "$ACTIVE_CLI" ]; then
        echo -e "  CLI Ativo: ${GREEN}$ACTIVE_CLI${NC}"
    else
        echo -e "  CLI Ativo: ${YELLOW}Nenhum configurado${NC}"
    fi
    
    # Verificar variáveis de ambiente
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        echo -e "  Anthropic API Key: ${GREEN}Configurada${NC}"
    else
        echo -e "  Anthropic API Key: ${RED}Não configurada${NC}"
    fi
    
    if [ -n "$OPENROUTER_API_KEY" ]; then
        echo -e "  OpenRouter API Key: ${GREEN}Configurada${NC}"
    else
        echo -e "  OpenRouter API Key: ${RED}Não configurada${NC}"
    fi
    
    if [ -n "$KILO_API_KEY" ]; then
        echo -e "  Kilocode API Key: ${GREEN}Configurada${NC}"
    else
        echo -e "  Kilocode API Key: ${RED}Não configurada${NC}"
    fi
    
    echo ""
}

# Configurar Claude CLI
configure_claude() {
    echo -e "${GREEN}Configurando Claude CLI...${NC}"
    echo -e "${YELLOW}Opções:${NC}"
    echo "  1) Usar API Key (ANTHROPIC_API_KEY)"
    echo "  2) Usar OAuth (requer navegador)"
    echo ""
    read -p "Escolha (1/2): " option
    
    case $option in
        1)
            read -p "Digite sua Anthropic API Key: " -s api_key
            echo ""
            export ANTHROPIC_API_KEY="$api_key"
            if ! grep -q "ANTHROPIC_API_KEY" ~/.bashrc 2>/dev/null; then
                echo "export ANTHROPIC_API_KEY='$api_key'" >> ~/.bashrc
            fi
            echo -e "${GREEN}API Key configurada!${NC}"
            ;;
        2)
            echo -e "${GREEN}Iniciando OAuth...${NC}"
            echo -e "${YELLOW}Execute: claude setup-token${NC}"
            echo ""
            echo "Para autenticação via SSH Tunnel, consulte:"
            echo "  cat /opt/vps-agent/docs/SSH_TUNNEL_GUIDE.md"
            ;;
        *)
            echo -e "${RED}Opção inválida!${NC}"
            return 1
            ;;
    esac
}

# Autenticar Claude CLI (OAuth) - Método Seguro
auth_claude() {
    echo -e "${GREEN}Autenticando Claude CLI (OAuth)...${NC}"
    echo ""
    echo -e "${YELLOW}Aviso: Este comando é interativo.${NC}"
    echo "Métodos seguros disponíveis:"
    echo ""
    echo "1) Gerar URL com timeout (seguro)"
    echo "2) Usar API Key (mais simples)"
    echo "3) Ver guia completo"
    echo ""
    read -p "Escolha (1/2/3): " option
    
    case $option in
        1)
            echo -e "${GREEN}Gerando URL de autenticação...${NC}"
            echo "A URL será salva em /tmp/claude_auth_url.txt"
            timeout 10 claude setup-token > /tmp/claude_auth_url.txt 2>&1 &
            sleep 3
            if [ -s /tmp/claude_auth_url.txt ]; then
                echo -e "${GREEN}URL gerada:${NC}"
                cat /tmp/claude_auth_url.txt
            else
                echo -e "${YELLOW}Timeout ou erro. Consulte:${NC}"
                echo "  cat /opt/vps-agent/docs/CLAUDE_AUTH_GUIDE.md"
            fi
            ;;
        2)
            read -p "Digite sua Anthropic API Key: " -s api_key
            echo ""
            export ANTHROPIC_API_KEY="$api_key"
            if ! grep -q "ANTHROPIC_API_KEY" ~/.bashrc 2>/dev/null; then
                echo "export ANTHROPIC_API_KEY='$api_key'" >> ~/.bashrc
            fi
            echo -e "${GREEN}API Key configurada!${NC}"
            ;;
        3)
            cat /opt/vps-agent/docs/CLAUDE_AUTH_GUIDE.md
            ;;
        *)
            echo -e "${RED}Opção inválida!${NC}"
            return 1
            ;;
    esac
}

# Configurar Kilocode CLI (Anthropic via OpenRouter)
configure_kilocode() {
    echo -e "${GREEN}Configurando Kilocode CLI (Anthropic via OpenRouter)...${NC}"
    echo -e "${YELLOW}Use sua chave OpenRouter com modelos Anthropic (Claude 3.5/3.7)${NC}"
    
    read -p "Digite sua OpenRouter API Key: " -s api_key
    echo ""
    
    if [ -z "$api_key" ]; then
        echo -e "${RED}API Key não pode ser vazia!${NC}"
        return 1
    fi
    
    # Exportar para sessão atual
    export OPENROUTER_API_KEY="$api_key"
    
    # Salvar em .bashrc para persistência
    if ! grep -q "OPENROUTER_API_KEY" ~/.bashrc 2>/dev/null; then
        echo "export OPENROUTER_API_KEY='$api_key'" >> ~/.bashrc
        echo -e "${GREEN}API Key salva em ~/.bashrc${NC}"
    fi
    
    echo -e "${GREEN}Kilocode CLI configurado com sucesso!${NC}"
}

# Usar Claude CLI
use_claude() {
    echo -e "${BLUE}Usando Claude CLI...${NC}"
    
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo -e "${RED}Claude CLI não configurado! Execute 'agent-cli configure claude' primeiro.${NC}"
        return 1
    fi
    
    export ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"
    export ACTIVE_CLI="claude"
    
    echo -e "${GREEN}Claude CLI ativado!${NC}"
    echo "Use 'claude' para interagir com o agente"
}

# Usar Kilocode CLI
use_kilocode() {
    echo -e "${BLUE}Usando Kilocode CLI...${NC}"
    
    if [ -z "$OPENROUTER_API_KEY" ]; then
        echo -e "${RED}Kilocode CLI não configurado! Execute 'agent-cli configure kilocode' primeiro.${NC}"
        return 1
    fi
    
    export OPENROUTER_API_KEY="$OPENROUTER_API_KEY"
    export ACTIVE_CLI="kilocode"
    
    echo -e "${GREEN}Kilocode CLI ativado!${NC}"
    echo "Use 'kilocode' para interagir com o agente"
}

# Executar tarefa com CLI ativo
run_task() {
    local task="$1"
    
    if [ "$ACTIVE_CLI" = "claude" ]; then
        echo -e "${BLUE}Executando com Claude CLI...${NC}"
        claude --workdir /opt/vps-agent "$task"
    elif [ "$ACTIVE_CLI" = "kilocode" ]; then
        echo -e "${BLUE}Executando com Kilocode CLI...${NC}"
        kilocode --workdir /opt/vps-agent "$task"
    else
        echo -e "${RED}Nenhum CLI ativo! Configure e selecione um primeiro.${NC}"
        echo "Uso: agent-cli use claude | agent-cli use kilocode"
        return 1
    fi
}

# Menu de ajuda
show_help() {
    echo -e "${BLUE}Comandos disponíveis:${NC}"
    echo ""
    echo "  agent-cli status          - Mostrar status atual"
    echo "  agent-cli auth           - Autenticar Claude CLI (OAuth)"
    echo "  agent-cli configure claude  - Configurar Claude CLI (Anthropic)"
    echo "  agent-cli configure kilocode - Configurar Kilocode CLI (OpenRouter)"
    echo "  agent-cli use claude      - Ativar Claude CLI"
    echo "  agent-cli use kilocode    - Ativar Kilocode CLI"
    echo "  agent-cli run '<tarefa>'  - Executar tarefa com CLI ativo"
    echo "  agent-cli help           - Mostrar esta ajuda"
    echo ""
    echo -e "${YELLOW}Exemplos:${NC}"
    echo "  agent-cli use claude"
    echo "  agent-cli run 'Analise o projeto e sugira melhorias'"
    echo ""
    echo -e "${YELLOW}Para autenticação OAuth:${NC}"
    echo "  agent-cli auth"
}

# Menu principal
case "${1:-}" in
    status)
        show_status
        ;;
    auth)
        auth_claude
        ;;
    configure)
        case "${2:-}" in
            claude)
                configure_claude
                ;;
            kilocode)
                configure_kilocode
                ;;
            *)
                echo -e "${RED}Uso: agent-cli configure claude|kilocode${NC}"
                exit 1
                ;;
        esac
        ;;
    use)
        case "${2:-}" in
            claude)
                use_claude
                ;;
            kilocode)
                use_kilocode
                ;;
            *)
                echo -e "${RED}Uso: agent-cli use claude|kilocode${NC}"
                exit 1
                ;;
        esac
        ;;
    run)
        if [ -z "${2:-}" ]; then
            echo -e "${RED}Uso: agent-cli run '<tarefa>'${NC}"
            exit 1
        fi
        run_task "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac
