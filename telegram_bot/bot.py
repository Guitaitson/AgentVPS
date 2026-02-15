"""
VPS-Agent Telegram Bot — Interface principal
Versão: 2.0 — Com LangGraph e timeout otimizado
"""

import logging
import os

import psycopg2
import redis
import structlog
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# VPS-Agent Core (nosso módulo)
from core.vps_agent.agent import process_message_async

# Telegram Log Handler (F0-06)

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
    int(uid.strip()) for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if uid.strip()
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
        decode_responses=True,
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
    """Handler para mensagens gerais — usa LangGraph com tratamento de erro robusto."""
    user_id = str(update.effective_user.id)
    message = update.message.text

    logger.info("mensagem_recebida", user_id=user_id, message=message[:100])

    try:
        # Processar através do LangGraph
        response = await process_message_async(user_id, message)

        # Garantir que temos uma resposta válida
        if not response:
            response = "Desculpe, não consegui processar sua mensagem. Tente novamente."

        await update.message.reply_text(response)

    except Exception as e:
        logger.error("erro_processamento_mensagem", user_id=user_id, error=str(e))

        # Resposta de fallback amigável
        fallback_response = (
            "🤖 **VPS-Agent**\n\n"
            "Desculpe, ocorreu um erro ao processar sua mensagem.\n\n"
            "Você pode tentar:\n"
            "• Enviar a mensagem novamente\n"
            "• Usar comandos diretos como `/status` ou `/help`\n\n"
            f"_Erro: {str(e)[:100]}_"
        )

        try:
            await update.message.reply_text(fallback_response, parse_mode="Markdown")
        except Exception:
            # Se até o fallback falhar, enviar sem markdown
            await update.message.reply_text(
                "Desculpe, ocorreu um erro. Tente novamente ou use /help."
            )


@authorized_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /status — usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_status", user_id=user_id)

    # Roteia pelo grafo com /status para ativar intent de comando
    response = await process_message_async(user_id, "/status")
    await update.message.reply_text(response)


@authorized_only
async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /ram — usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_ram", user_id=user_id)

    # Roteia pelo grafo com /ram para ativar intent de comando
    response = await process_message_async(user_id, "/ram")
    await update.message.reply_text(response)


@authorized_only
async def cmd_containers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /containers — usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_containers", user_id=user_id)

    # Roteia pelo grafo com /containers para ativar intent de comando
    response = await process_message_async(user_id, "/containers")
    await update.message.reply_text(response)


@authorized_only
async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /health — usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_health", user_id=user_id)

    # Roteia pelo grafo com /health para ativar intent de comando
    response = await process_message_async(user_id, "/health")
    await update.message.reply_text(response)


@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /help — ajuda."""
    help_text = """
🤖 **VPS-Agent v3 — Ajuda**

**Comandos disponíveis:**
- `/start` — Iniciar conversa
- `/status` — Estado geral da VPS
- `/ram` — Uso de memória por container
- `/containers` — Lista de containers ativos
- `/health` — Health check completo
- `/proposals` — Lista proposals autonomas pendentes
- `/approve <id>` — Aprova proposal autonoma
- `/reject <id>` — Rejeita proposal autonoma
- `/help` — Esta ajuda

**Sobre:**
Este bot controla o VPS-Agent, um agente autonomo com ReAct + function calling.
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")


@authorized_only
async def cmd_proposals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /proposals — lista proposals pendentes."""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, trigger_name, suggested_action, created_at
            FROM agent_proposals
            WHERE status = 'pending' AND requires_approval = TRUE
            ORDER BY priority ASC, created_at ASC
            LIMIT 10"""
        )
        proposals = cur.fetchall()
        conn.close()

        if not proposals:
            await update.message.reply_text("Nenhuma proposal pendente de aprovacao.")
            return

        import json

        lines = ["Proposals pendentes:\n"]
        for p_id, trigger, action_json, created in proposals:
            action = json.loads(action_json)
            desc = action.get("description", action.get("action", "?"))
            lines.append(f"#{p_id} [{trigger}] {desc}\n  /approve {p_id} | /reject {p_id}")

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error("cmd_proposals_error", error=str(e))
        await update.message.reply_text(f"Erro ao listar proposals: {str(e)[:100]}")


@authorized_only
async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /approve <id> — aprova proposal."""
    if not context.args:
        await update.message.reply_text("Uso: /approve <id>")
        return

    try:
        proposal_id = int(context.args[0])
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            """UPDATE agent_proposals
            SET status = 'approved', approval_note = 'Aprovado via Telegram'
            WHERE id = %s AND status = 'pending'""",
            (proposal_id,),
        )
        affected = cur.rowcount
        conn.commit()
        conn.close()

        if affected:
            await update.message.reply_text(
                f"Proposal #{proposal_id} aprovada. Sera executada no proximo ciclo."
            )
        else:
            await update.message.reply_text(
                f"Proposal #{proposal_id} nao encontrada ou ja processada."
            )
    except ValueError:
        await update.message.reply_text("ID invalido. Uso: /approve <numero>")
    except Exception as e:
        logger.error("cmd_approve_error", error=str(e))
        await update.message.reply_text(f"Erro: {str(e)[:100]}")


@authorized_only
async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /reject <id> — rejeita proposal."""
    if not context.args:
        await update.message.reply_text("Uso: /reject <id>")
        return

    try:
        proposal_id = int(context.args[0])
        note = " ".join(context.args[1:]) if len(context.args) > 1 else "Rejeitado via Telegram"
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            """UPDATE agent_proposals
            SET status = 'rejected', approval_note = %s
            WHERE id = %s AND status = 'pending'""",
            (note, proposal_id),
        )
        affected = cur.rowcount
        conn.commit()
        conn.close()

        if affected:
            await update.message.reply_text(f"Proposal #{proposal_id} rejeitada.")
        else:
            await update.message.reply_text(
                f"Proposal #{proposal_id} nao encontrada ou ja processada."
            )
    except ValueError:
        await update.message.reply_text("ID invalido. Uso: /reject <numero>")
    except Exception as e:
        logger.error("cmd_reject_error", error=str(e))
        await update.message.reply_text(f"Erro: {str(e)[:100]}")


async def send_notification(message: str):
    """Envia notificacao para todos os usuarios autorizados."""
    import telegram

    bot = telegram.Bot(token=TOKEN)
    for user_id in ALLOWED_USERS:
        try:
            await bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error("send_notification_error", user_id=user_id, error=str(e))


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
        .connect_timeout(30.0)  # Timeout de conexão
        .read_timeout(30.0)  # Timeout de leitura
        .write_timeout(30.0)  # Timeout de escrita
        .pool_timeout(30.0)  # Timeout do pool de conexões
        .concurrent_updates(10)  # Atualizações simultâneas
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
    app.add_handler(CommandHandler("proposals", cmd_proposals))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))

    # Handler para mensagens gerais (LangGraph)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_error_handler(error_handler)

    logger.info("bot_pronto")
    app.run_polling()


if __name__ == "__main__":
    main()
