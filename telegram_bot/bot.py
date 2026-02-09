"""
VPS-Agent Telegram Bot — Interface principal
Versão: 2.0 — Com LangGraph e timeout otimizado
"""
import os
import sys
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import structlog
from dotenv import load_dotenv
import psycopg2
import redis

# Telegram Log Handler (F0-06)
from telegram_bot.telegram_handler import get_telegram_notifier

# VPS-Agent Core (nosso módulo)
from core.vps_agent.agent import process_message_async

# Configuração de logging estruturado
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# Carregar variáveis de ambiente
load_dotenv("/opt/vps-agent/core/.env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = [
    int(uid.strip()) 
    for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") 
    if uid.strip()
]

# Conexões
def get_db_conn():
    """Retorna conexão com PostgreSQL."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "vps_agent"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

def get_redis():
    """Retorna conexão com Redis."""
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True
    )


# Middleware de segurança
def authorized_only(func):
    """Decorator: só permite usuários autorizados."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USERS:
            logger.warning("acesso_negado", user_id=user_id)
            await update.message.reply_text("⛔ Acesso não autorizado.")
            return
        return await func(update, context)
    return wrapper


# Handlers
@authorized_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /start."""
    user_name = update.effective_user.first_name
    
    await update.message.reply_text(
        f"🤖 **VPS-Agent v2 Online!**\n\n"
        f"Olá, {user_name}! Seu agente autônomo está pronto.\n\n"
        f"**Comandos disponíveis:**\n"
        f"• `/status` — Estado da VPS\n"
        f"• `/ram` — Uso de memória\n"
        f"• `/containers` — Containers ativos\n"
        f"• `/health` — Health check completo\n"
        f"• `/help` — Ajuda\n\n"
        f"Ou basta enviar uma mensagem e eu proceso através do LangGraph!"
    )


@authorized_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens gerais — usa LangGraph."""
    user_id = str(update.effective_user.id)
    message = update.message.text
    
    logger.info("mensagem_recebida", user_id=user_id, message=message[:100])
    
    # Processar através do LangGraph
    response = await process_message_async(user_id, message)
    
    await update.message.reply_text(response)


@authorized_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /status — mostra estado geral."""
    redis_status = "❌"
    pg_status = "❌"
    
    try:
        r = get_redis()
        if r.ping():
            redis_status = "✅"
    except Exception:
        pass

    try:
        conn = get_db_conn()
        conn.close()
        pg_status = "✅"
    except Exception:
        pass

    import subprocess
    result = subprocess.run(["free", "-m"], capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")
    mem_parts = lines[1].split()
    total = int(mem_parts[1])
    used = int(mem_parts[2])
    available = int(mem_parts[6])

    status_text = (
        f"📊 **Status VPS-Agent**\n\n"
        f"🗄 PostgreSQL: {pg_status}\n"
        f"⚡ Redis: {redis_status}\n"
        f"💾 RAM: {used}MB / {total}MB (livre: {available}MB)\n"
        f"🕐 Hora: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")


@authorized_only
async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /ram — detalhe de memória por container."""
    import subprocess
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", 
         "{{.Name}}: {{.MemUsage}} ({{.MemPerc}})"],
        capture_output=True, text=True
    )
    
    text = f"🧠 **RAM por Container:**\n\n```\n{result.stdout if result.stdout.strip() else 'Nenhum container'}```"
    await update.message.reply_text(text, parse_mode="Markdown")


@authorized_only
async def cmd_containers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /containers — lista containers."""
    import subprocess
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
        capture_output=True, text=True
    )
    
    text = f"🐳 **Containers Ativos:**\n\n```\n{result.stdout if result.stdout.strip() else 'Nenhum container'}```"
    await update.message.reply_text(text, parse_mode="Markdown")


@authorized_only
async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /health — check completo."""
    checks = []
    
    # PostgreSQL
    try:
        conn = get_db_conn()
        conn.close()
        checks.append(("PostgreSQL", "✅"))
    except Exception:
        checks.append(("PostgreSQL", "❌"))
    
    # Redis
    try:
        r = get_redis()
        r.ping()
        checks.append(("Redis", "✅"))
    except Exception:
        checks.append(("Redis", "❌"))
    
    # Docker
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "-q"], capture_output=True, text=True
        )
        containers = len(result.stdout.strip().split("\n"))
        checks.append(("Docker", f"✅ ({containers} containers)"))
    except Exception:
        checks.append(("Docker", "❌"))
    
    # RAM
    try:
        import subprocess
        result = subprocess.run(["free", "-m"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")
        mem_parts = lines[1].split()
        available = int(mem_parts[6])
        checks.append(("RAM", f"✅ ({available}MB livre)"))
    except Exception:
        checks.append(("RAM", "❌"))
    
    text = "🔍 **Health Check:**\n\n" + "\n".join(f"{name}: {status}" for name, status in checks)
    await update.message.reply_text(text, parse_mode="Markdown")


@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /help — ajuda."""
    help_text = """
🤖 **VPS-Agent v2 — Ajuda**

**Comandos disponíveis:**
- `/start` — Iniciar conversa
- `/status` — Estado geral da VPS
- `/ram` — Uso de memória por container
- `/containers` — Lista de containers ativos
- `/health` — Health check completo
- `/help` — Esta ajuda

**Sobre:**
Este bot controla o VPS-Agent, um agente autônomo que roda na VPS.
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handler para erros — envia para Telegram e log local."""
    error_msg = str(context.error)
    
    # Log local
    logger.error("erro_telegram", error=error_msg)
    
    # Enviar para Telegram (F0-06)
    try:
        from telegram_bot.telegram_handler import get_telegram_notifier
        notifier = get_telegram_notifier()
        notifier.send_error(f"Erro no Bot:\n```\n{error_msg[:500]}\n```")
    except Exception:
        pass  # Silencioso se Telegram falhar


def main():
    """Inicializa e roda o bot com timeout otimizado."""
    logger.info("iniciando_bot", token=f"{TOKEN[:10]}...")
    
    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30.0)      # Timeout de conexão
        .read_timeout(30.0)        # Timeout de leitura
        .write_timeout(30.0)       # Timeout de escrita
        .pool_timeout(30.0)       # Timeout do pool de conexões
        .concurrent_updates(10)    # Atualizações simultâneas
        .connection_pool_size(20)  # Tamanho do pool de conexões
        .build()
    )
    
    # Handlers de comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ram", cmd_ram))
    app.add_handler(CommandHandler("containers", cmd_containers))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("help", cmd_help))
    
    # Handler para mensagens gerais (LangGraph)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.add_error_handler(error_handler)
    
    logger.info("bot_pronto")
    app.run_polling()


if __name__ == "__main__":
    main()
