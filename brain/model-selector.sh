#!/bin/bash
# VPS-Agent Model Selector
# Choose which model to use based on task complexity and budget

MODELS_CONFIG="/opt/vps-agent/configs/models.json"
DEFAULT_MODEL="minimax-m2.1"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🎛️ VPS-Agent Model Selector${NC}"
echo "================================="

# List available models
list_models() {
    echo -e "${YELLOW}Available Models:${NC}"
    echo ""
    echo "FREE:"
    echo "  minimax-m2.1  - MiniMax M2.1 (fast, free)"
    echo ""
    echo "PAID:"
    echo "  claude-3-5-sonnet - Best for complex tasks"
    echo "  claude-3-haiku   - Fast and efficient"
    echo "  gpt-4o          - OpenAI flagship"
    echo ""
}

# Get current model
get_current_model() {
    if [ -f "$MODELS_CONFIG" ]; then
        grep -o "\"default_model\": \"[^\"]*\"" "$MODELS_CONFIG" | cut -d'"' -f4
    else
        echo "$DEFAULT_MODEL"
    fi
}

# Set model
set_model() {
    local model="$1"
    local provider="$2"
    local cost="$3"
    
    echo -e "${GREEN}Setting model to: $model${NC}"
    echo "Provider: $provider"
    echo "Cost: $cost"
    
    # Update kilocode config
    export OPENROUTER_MODEL="$model"
    export KILOCODE_MODEL="$model"
    
    echo "$model" > /tmp/current_model.txt
}

# Select model based on task
select_for_task() {
    local task="$1"
    
    echo -e "${YELLOW}Analyzing task: $task${NC}"
    
    # Simple task - use free model
    if [ ${#task} -lt 50 ]; then
        echo "Task: Simple"
        set_model "minimax-m2.1" "openrouter" "free"
    # Medium task - balanced
    elif [ ${#task} -lt 200 ]; then
        echo "Task: Medium"
        set_model "minimax-m2.1" "openrouter" "free"
    # Complex task - use best model
    else
        echo "Task: Complex"
        set_model "claude-3-5-sonnet" "anthropic" "paid"
    fi
}

# Budget mode - always prefer free
budget_mode() {
    echo -e "${GREEN}💰 Budget Mode: ON${NC}"
    echo "Always prefer free models (minimax-m2.1)"
    set_model "minimax-m2.1" "openrouter" "free"
}

# Interactive selection
interactive_select() {
    echo ""
    echo "Choose a model:"
    echo "  1) minimax-m2.1  (free, fast)"
    echo "  2) claude-3-5-sonnet (paid, best)"
    echo "  3) claude-3-haiku (paid, fast)"
    echo "  4) gpt-4o (paid, general)"
    echo "  5) Budget mode (always free)"
    echo ""
    read -p "Choice (1-5): " choice
    
    case $choice in
        1) set_model "minimax-m2.1" "openrouter" "free" ;;
        2) set_model "claude-3-5-sonnet" "anthropic" "paid" ;;
        3) set_model "claude-3-haiku" "anthropic" "paid" ;;
        4) set_model "gpt-4o" "openrouter" "paid" ;;
        5) budget_mode ;;
        *) echo "Invalid choice" ;;
    esac
}

# Main
case "${1:-}" in
    list)
        list_models
        ;;
    get)
        echo "Current model: $(get_current_model)"
        ;;
    set)
        set_model "$2" "$3" "$4"
        ;;
    auto)
        select_for_task "$2"
        ;;
    budget)
        budget_mode
        ;;
    interactive|*)
        list_models
        interactive_select
        ;;
esac
