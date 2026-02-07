"""
Nodes do agente LangGraph.
Cada função é um nó no grafo de decisões.
"""
import subprocess
import json
from typing import Optional
from datetime import datetime

from .memory import AgentMemory
from .state import AgentState

memory = AgentMemory()


def node_classify_intent(state: AgentState) -> AgentState:
    """Classifica a intenção do usuário."""
    message = state["user_message"].lower()
    
    # Comandos diretos do Telegram
    telegram_commands = [
        "/start", "/status", "/ram", "/containers", "/health", "/help",
        "status", "ram", "containers", "health", "help"
    ]
    
    if any(message.startswith(cmd) for cmd in telegram_commands):
        return {
            **state,
            "intent": "command",
            "intent_confidence": 0.95,
        }
    
    # Perguntas sobre o sistema
    system_keywords = ["ram", "memória", "cpu", "docker", "container", "status", "saúde"]
    if any(kw in message for kw in system_keywords):
        return {
            **state,
            "intent": "question",
            "intent_confidence": 0.85,
        }
    
    # Tarefas a executar
    action_keywords = ["rode", "execute", "rode", "inicia", "para", "reinicia"]
    if any(kw in message for kw in action_keywords):
        return {
            **state,
            "intent": "task",
            "intent_confidence": 0.80,
        }
    
    # Default: conversa
    return {
        **state,
        "intent": "chat",
        "intent_confidence": 0.70,
    }


def node_load_context(state: AgentState) -> AgentState:
    """Carrega contexto do usuário da memória."""
    user_id = state["user_id"]
    
    # Fatos do usuário
    user_facts = memory.get_user_facts(user_id)
    
    # Histórico recente
    history = memory.get_conversation_history(user_id, limit=5)
    
    return {
        **state,
        "user_context": user_facts,
        "conversation_history": history,
    }


def node_plan(state: AgentState) -> AgentState:
    """Cria plano de ação baseado na intenção."""
    intent = state.get("intent")
    
    if intent == "command":
        command = state["user_message"].split()[0].lstrip("/")
        return {
            **state,
            "plan": [{"type": "command", "action": command}],
            "current_step": 0,
            "tools_needed": [],
        }
    
    if intent == "question":
        return {
            **state,
            "plan": [{"type": "query", "action": "get_system_info"}],
            "current_step": 0,
            "tools_needed": [],
        }
    
    if intent == "task":
        action = state["user_message"]
        return {
            **state,
            "plan": [{"type": "execute", "action": action}],
            "current_step": 0,
            "tools_needed": ["docker"],
        }
    
    # Chat: resposta direta
    return {
        **state,
        "plan": None,
        "current_step": None,
    }


def node_execute(state: AgentState) -> AgentState:
    """Executa o plano definido."""
    intent = state.get("intent")
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    
    if not plan or step >= len(plan):
        return {**state, "execution_result": "nothing_to_do"}
    
    current_action = plan[step]
    action_type = current_action.get("type")
    action = current_action.get("action")
    
    try:
        if action_type == "command" and action == "ram":
            # Executar comando de RAM
            result = subprocess.run(
                ["free", "-m"],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout
            
            # Parsear memória
            lines = output.strip().split("\n")
            mem_line = lines[1].split()
            total = mem_line[1]
            used = mem_line[2]
            free = mem_line[3]
            
            return {
                **state,
                "execution_result": f"RAM: {used}/{total} MB (livre: {free} MB)",
            }
        
        elif action_type == "command" and action == "containers":
            # Listar containers
            result = subprocess.run(
                ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return {
                **state,
                "execution_result": result.stdout or "Nenhum container ativo",
            }
        
        elif action_type == "command" and action == "status":
            # Status completo
            result = subprocess.run(
                ["free", "-m"],
                capture_output=True,
                text=True,
                timeout=10
            )
            ram_info = result.stdout
            
            return {
                **state,
                "execution_result": f"Status:\n{ram_info}",
            }
        
        elif action_type == "command" and action == "health":
            # Health check
            checks = []
            
            # PostgreSQL
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host="127.0.0.1",
                    port=5432,
                    dbname="vps_agent",
                    user="postgres",
                    password="postgres",
                    connect_timeout=5
                )
                conn.close()
                checks.append("✅ PostgreSQL")
            except Exception as e:
                checks.append(f"❌ PostgreSQL: {e}")
            
            # Redis
            try:
                import redis
                r = redis.Redis(host="127.0.0.1", port=6379, socket_timeout=5)
                r.ping()
                checks.append("✅ Redis")
            except Exception as e:
                checks.append(f"❌ Redis: {e}")
            
            return {
                **state,
                "execution_result": "\n".join(checks),
            }
        
        else:
            return {
                **state,
                "execution_result": f"Comando '{action}' não implementado",
            }
    
    except Exception as e:
        return {
            **state,
            "error": str(e),
            "execution_result": f"Erro ao executar: {e}",
        }


def node_generate_response(state: AgentState) -> AgentState:
    """Gera resposta final ao usuário."""
    intent = state.get("intent")
    execution_result = state.get("execution_result")
    user_context = state.get("user_context", {})
    user_message = state.get("user_message")
    
    if execution_result:
        response = execution_result
    elif intent == "chat":
        response = f"Entendi sua mensagem: '{user_message}'. Como posso ajudar?"
    else:
        response = "Comando executado com sucesso!"
    
    # Salvar memória se foi uma interação significativa
    should_save = intent in ["command", "task"] or len(user_message) > 50
    
    return {
        **state,
        "response": response,
        "should_save_memory": should_save,
        "memory_updates": [
            {"key": "last_interaction", "value": {"type": intent, "time": datetime.now().isoformat()}}
        ] if should_save else [],
    }


def node_save_memory(state: AgentState) -> AgentState:
    """Salva atualizações na memória."""
    user_id = state["user_id"]
    updates = state.get("memory_updates", [])
    
    for update in updates:
        key = update["key"]
        value = update["value"]
        memory.save_fact(user_id, key, value)
    
    return state
