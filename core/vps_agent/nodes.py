"""
Nós do grafo LangGraph.
Cada função é um passo no fluxo de decisão do agente.
"""
import subprocess
import json
import sys
import os
sys.path.insert(0, "/opt/vps-agent/core")

from datetime import datetime, timezone
from resource_manager.manager import get_tools_status, start_tool, stop_tool

from .state import AgentState
from .memory import AgentMemory

memory = AgentMemory()

# Comandos reconhecidos pelo bot
KNOWN_COMMANDS = {
    "status": "Verificar estado da VPS",
    "ram": "Verificar uso de memória",
    "containers": "Listar containers",
    "health": "Health check completo",
    "tools": "Listar ferramentas disponíveis",
    "start_tool": "Iniciar uma ferramenta",
    "stop_tool": "Parar uma ferramenta",
}


def node_classify_intent(state: AgentState) -> dict:
    """
    Classifica a intenção do usuário.
    """
    msg = state["user_message"].lower().strip()
    
    # Comandos diretos
    if msg.startswith("/"):
        cmd = msg.split()[0][1:]  # Remove /
        if cmd in KNOWN_COMMANDS:
            return {
                "intent": "command",
                "intent_confidence": 1.0,
            }
        
        # Comandos de ferramenta
        if cmd == "start" and len(msg.split()) > 1:
            return {"intent": "start_tool", "intent_confidence": 0.95}
        if cmd == "stop" and len(msg.split()) > 1:
            return {"intent": "stop_tool", "intent_confidence": 0.95}
    
    # Palavras-chave de tarefas
    task_keywords = ["subir", "parar", "reiniciar", "instalar", "configurar", 
                     "backup", "atualizar", "deploy", "analise", "verifique"]
    if any(kw in msg for kw in task_keywords):
        return {
            "intent": "task",
            "intent_confidence": 0.85,
        }
    
    # Perguntas
    question_keywords = ["como", "por que", "quando", "qual", "quanto", "?"]
    if any(kw in msg for kw in question_keywords):
        return {
            "intent": "question",
            "intent_confidence": 0.8,
        }
    
    # Default: chat
    return {
        "intent": "chat",
        "intent_confidence": 0.5,
    }


def node_load_context(state: AgentState) -> dict:
    """Carrega contexto relevante da memória."""
    user_id = state["user_id"]
    
    user_facts = memory.get_user_facts(user_id)
    recent_msgs = memory.get_conversation_history(user_id, limit=5)
    
    # Checar RAM disponível
    result = subprocess.run(
        ["free", "-m"], capture_output=True, text=True
    )
    lines = result.stdout.strip().split("\n")
    available = int(lines[1].split()[6])
    
    return {
        "user_context": user_facts,
        "conversation_history": [
            {"role": m["role"], "content": m["content"]} 
            for m in recent_msgs
        ],
        "ram_available_mb": available,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def node_plan(state: AgentState) -> dict:
    """Planeja a ação baseado na intenção."""
    intent = state.get("intent", "chat")
    msg = state["user_message"].lower().strip()
    
    if intent == "command":
        cmd = msg.split()[0][1:] if msg.startswith("/") else msg.split()[0]
        return {
            "plan": [{"action": "run_command", "command": cmd}],
            "current_step": 0,
        }
    
    if intent == "start_tool":
        tool = msg.split()[1] if len(msg.split()) > 1 else ""
        return {
            "plan": [{"action": "start_tool", "tool": tool}],
            "current_step": 0,
        }
    
    if intent == "stop_tool":
        tool = msg.split()[1] if len(msg.split()) > 1 else ""
        return {
            "plan": [{"action": "stop_tool", "tool": tool}],
            "current_step": 0,
        }
    
    # Tarefas e perguntas vão para o CLI
    if intent == "task" or intent == "question":
        return {
            "plan": [{"action": "call_cli"}],
            "current_step": 0,
        }
    
    # Chat simple - sem ação
    return {"plan": None}


def node_execute(state: AgentState) -> dict:
    """Executa o plano passo a passo."""
    plan = state.get("plan", [])
    if not plan:
        return {"execution_result": "Nenhum plano para executar."}
    
    step = plan[state.get("current_step", 0)]
    action = step.get("action", "")
    
    if action == "run_command":
        cmd_name = step.get("command", "")
        
        if cmd_name == "status":
            result = subprocess.run(
                ["free", "-m"], capture_output=True, text=True
            )
            lines = result.stdout.strip().split("\n")
            mem_parts = lines[1].split()
            total = int(mem_parts[1])
            used = int(mem_parts[2])
            available = int(mem_parts[6])
            return {
                "execution_result": "RAM: {}MB / {}MB (livre: {}MB)".format(used, total, available)
            }
        
        elif cmd_name == "ram":
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format",
                 "{{.Name}}: {{.MemUsage}} ({{.MemPerc}})"],
                capture_output=True, text=True
            )
            return {"execution_result": result.stdout or "Sem containers."}
        
        elif cmd_name == "containers":
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True, text=True
            )
            return {"execution_result": result.stdout or "Sem containers."}
        
        elif cmd_name == "tools":
            status = get_tools_status()
            return {"execution_result": json.dumps(status, indent=2)}
        
        elif cmd_name == "health":
            # Health check completo
            checks = []
            
            # PostgreSQL
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host="127.0.0.1", port=5432, dbname="vps_agent",
                    user="postgres", password="postgres", connect_timeout=5
                )
                conn.close()
                checks.append("✅ PostgreSQL")
            except Exception as e:
                checks.append("❌ PostgreSQL: {}".format(e))
            
            # Redis
            try:
                import redis
                r = redis.Redis(host="127.0.0.1", port=6379, socket_timeout=5)
                r.ping()
                checks.append("✅ Redis")
            except Exception as e:
                checks.append("❌ Redis: {}".format(e))
            
            # Docker
            try:
                result = subprocess.run(
                    ["docker", "ps", "-q"], capture_output=True, text=True
                )
                containers = len(result.stdout.strip().split("\n"))
                checks.append("✅ Docker ({} containers)".format(containers))
            except Exception as e:
                checks.append("❌ Docker: {}".format(e))
            
            return {"execution_result": "\n".join(checks)}
    
    if action == "start_tool":
        tool = step.get("tool", "")
        success, msg = start_tool(tool)
        return {"execution_result": msg}
    
    if action == "stop_tool":
        tool = step.get("tool", "")
        success, msg = stop_tool(tool)
        return {"execution_result": msg}
    
    if action == "call_cli":
        # Skip - será processado por node_call_cli
        return {"skip_execution": True}
    
    return {"execution_result": "Ação desconhecida: " + action}


def node_call_cli(state: AgentState) -> dict:
    """
    Chama o CLI (Kilocode) para processar tarefa ou pergunta.
    Usa MiniMax M2.1 via OpenRouter (free).
    """
    intent = state.get("intent", "task")
    user_msg = state.get("user_message", "")
    user_context = state.get("user_context", [])
    
    # Construir prompt com contexto
    context_prompt = ""
    if user_context:
        context_prompt = "\nContexto do usuário:\n" + json.dumps(user_context, indent=2) + "\n"
    
    # Prompt completo
    full_prompt = """Você é um assistente VPS útil.

Contexto atual:
- RAM disponível: {}MB
{}

Mensagem do usuário: {}

Responda de forma concisa e útil.""".format(
        state.get("ram_available_mb", 0),
        context_prompt,
        user_msg
    )
    
    # Executar com OpenRouter (MiniMax M2.1)
    try:
        import requests
        
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        
        if openrouter_key:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": "Bearer " + openrouter_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": "minimax/minimax-m2.1",
                    "messages": [
                        {"role": "system", "content": "Você é um assistente VPS útil e conciso."},
                        {"role": "user", "content": full_prompt}
                    ],
                    "temperature": 0.7,
                },
                timeout=60
            )
            
            if response.status_code == 200:
                cli_response = response.json()["choices"][0]["message"]["content"]
            else:
                cli_response = "Erro ao chamar API: {}".format(response.status_code)
        else:
            cli_response = "⚠️ OpenRouter API Key não configurada. Configure com: agent-cli configure kilocode"
            
    except ImportError:
        cli_response = "⚠️ Biblioteca requests não disponível para chamadas de API."
    except Exception as e:
        cli_response = "Erro ao chamar CLI: " + str(e)
    
    return {
        "cli_response": cli_response,
        "cli_used_model": "minimax/minimax-m2.1",
    }


def node_generate_response(state: AgentState) -> dict:
    """Gera a resposta final para o usuário."""
    if state.get("response"):
        return {"should_save_memory": False}
    
    intent = state.get("intent", "chat")
    exec_result = state.get("execution_result", "")
    cli_response = state.get("cli_response", "")
    
    if intent == "command" and exec_result:
        return {
            "response": "📋 Resultado:\n\n```\n{}\n```".format(exec_result),
            "should_save_memory": False,
        }
    
    if intent == "start_tool" or intent == "stop_tool":
        return {
            "response": exec_result,
            "should_save_memory": False,
        }
    
    # Resposta do CLI (para task ou question)
    if cli_response:
        return {
            "response": cli_response,
            "should_save_memory": True,
        }
    
    if intent == "question":
        return {
            "response": "❓ Entendi sua pergunta. Vou processá-la...",
            "should_save_memory": True,
        }
    
    return {
        "response": "Entendi sua mensagem: '{}'. Como posso ajudar?".format(state.get('user_message', '')),
        "should_save_memory": False,
    }


def node_save_memory(state: AgentState) -> dict:
    """Salva atualizações na memória."""
    user_id = state.get("user_id")
    message = state.get("user_message", "")
    response = state.get("response", "")
    
    # Salvar na memória estruturada
    if user_id and message:
        memory.add_fact(user_id, {
            "type": "conversation",
            "message": message,
            "response": response,
            "intent": state.get("intent", "unknown"),
        })
    
    return state
