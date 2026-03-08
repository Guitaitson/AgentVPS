"""
VPS-Agent Telegram Bot â€” Interface principal
VersÃ£o: 2.0 â€” Com LangGraph e timeout otimizado
"""

import logging
import os

import psycopg2
import redis
import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# VPS-Agent Core (nosso mÃ³dulo)
from core.env import load_project_env
from core.vps_agent.agent import process_message_async

# Telegram Log Handler (F0-06)

# ConfiguraÃ§Ã£o de logging estruturado
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# Carregar variÃ¡veis de ambiente
load_project_env()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = [
    int(uid.strip()) for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if uid.strip()
]


# ConexÃµes
def get_db_conn():
    """Retorna conexÃ£o com PostgreSQL."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "vps_agent"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def get_redis():
    """Retorna conexÃ£o com Redis."""
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True,
    )



def _parse_db_json(value):
    """Converte JSON do banco para dict de forma resiliente."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}

# Middleware de seguranÃ§a
def authorized_only(func):
    """Decorator: sÃ³ permite usuÃ¡rios autorizados."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USERS:
            logger.warning("acesso_negado", user_id=user_id)
            await update.message.reply_text("â›” Acesso nÃ£o autorizado.")
            return
        return await func(update, context)

    return wrapper


# Handlers
@authorized_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /start."""
    user_name = update.effective_user.first_name

    await update.message.reply_text(
        f"ðŸ¤– **VPS-Agent v2 Online!**\n\n"
        f"OlÃ¡, {user_name}! Seu agente autÃ´nomo estÃ¡ pronto.\n\n"
        f"**Comandos disponÃ­veis:**\n"
        f"â€¢ `/status` â€” Estado da VPS\n"
        f"â€¢ `/ram` â€” Uso de memÃ³ria\n"
        f"â€¢ `/containers` â€” Containers ativos\n"
        f"â€¢ `/health` â€” Health check completo\n"
        f"â€¢ `/help` â€” Ajuda\n\n"
        f"Ou basta enviar uma mensagem e eu proceso atravÃ©s do LangGraph!"
    )


@authorized_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens gerais â€” usa LangGraph com tratamento de erro robusto."""
    user_id = str(update.effective_user.id)
    message = update.message.text

    logger.info("mensagem_recebida", user_id=user_id, message=message[:100])

    try:
        # Processar atravÃ©s do LangGraph
        response = await process_message_async(user_id, message)

        # Garantir que temos uma resposta vÃ¡lida
        if not response:
            response = "Desculpe, nÃ£o consegui processar sua mensagem. Tente novamente."

        await update.message.reply_text(response)

    except Exception as e:
        logger.error("erro_processamento_mensagem", user_id=user_id, error=str(e))

        # Resposta de fallback amigÃ¡vel
        fallback_response = (
            "ðŸ¤– **VPS-Agent**\n\n"
            "Desculpe, ocorreu um erro ao processar sua mensagem.\n\n"
            "VocÃª pode tentar:\n"
            "â€¢ Enviar a mensagem novamente\n"
            "â€¢ Usar comandos diretos como `/status` ou `/help`\n\n"
            f"_Erro: {str(e)[:100]}_"
        )

        try:
            await update.message.reply_text(fallback_response, parse_mode="Markdown")
        except Exception:
            # Se atÃ© o fallback falhar, enviar sem markdown
            await update.message.reply_text(
                "Desculpe, ocorreu um erro. Tente novamente ou use /help."
            )


@authorized_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /status â€” usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_status", user_id=user_id)

    # Roteia pelo grafo com /status para ativar intent de comando
    response = await process_message_async(user_id, "/status")
    await update.message.reply_text(response)


@authorized_only
async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /ram â€” usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_ram", user_id=user_id)

    # Roteia pelo grafo com /ram para ativar intent de comando
    response = await process_message_async(user_id, "/ram")
    await update.message.reply_text(response)


@authorized_only
async def cmd_containers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /containers â€” usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_containers", user_id=user_id)

    # Roteia pelo grafo com /containers para ativar intent de comando
    response = await process_message_async(user_id, "/containers")
    await update.message.reply_text(response)


@authorized_only
async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /health â€” usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_health", user_id=user_id)

    # Roteia pelo grafo com /health para ativar intent de comando
    response = await process_message_async(user_id, "/health")
    await update.message.reply_text(response)


@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /help â€” ajuda."""
    help_text = """
ðŸ¤– **VPS-Agent v3 â€” Ajuda**

**Comandos disponÃ­veis:**
- `/start` â€” Iniciar conversa
- `/status` â€” Estado geral da VPS
- `/ram` â€” Uso de memÃ³ria por container
- `/containers` â€” Lista de containers ativos
- `/health` â€” Health check completo
- `/proposals` â€” Lista proposals autonomas pendentes
- `/proposal <id>` â€” Detalha uma proposal
- `/approve <id>` â€” Aprova proposal autonoma
- `/reject <id>` â€” Rejeita proposal autonoma
- `/catalogsync [check|apply] [source]` â€” Sincroniza catalogo de skills
- `/updatestatus` â€” Mostra status do updater automatico
- `/help` â€” Esta ajuda

**Sobre:**
Este bot controla o VPS-Agent, um agente autonomo com ReAct + function calling.
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")


@authorized_only
async def cmd_proposals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /proposals - lista proposals pendentes."""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, trigger_name, suggested_action, condition_data, created_at
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

        lines = ["Proposals pendentes:\n"]
        for p_id, trigger, action_json, condition_json, _created in proposals:
            action = _parse_db_json(action_json)
            condition = _parse_db_json(condition_json)
            desc = action.get("description", action.get("action", "?"))

            details = ""
            if trigger == "catalog_update_available":
                details = (
                    f" (changes={condition.get('changes_detected', 0)}, "
                    f"add={condition.get('added', 0)}, upd={condition.get('updated', 0)}, "
                    f"rm={condition.get('removed', 0)})"
                )

            lines.append(
                f"#{p_id} [{trigger}] {desc}{details}\n"
                f"  /proposal {p_id}\n"
                f"  /approve {p_id} | /reject {p_id}"
            )

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error("cmd_proposals_error", error=str(e))
        await update.message.reply_text(f"Erro ao listar proposals: {str(e)[:100]}")


@authorized_only
async def cmd_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /proposal <id> - detalha proposal."""
    if not context.args:
        await update.message.reply_text("Uso: /proposal <id>")
        return

    try:
        proposal_id = int(context.args[0])
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, trigger_name, status, requires_approval, suggested_action, condition_data, created_at
            FROM agent_proposals
            WHERE id = %s
            LIMIT 1""",
            (proposal_id,),
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            await update.message.reply_text(f"Proposal #{proposal_id} nao encontrada.")
            return

        p_id, trigger, status, requires_approval, action_json, condition_json, created_at = row
        action = _parse_db_json(action_json)
        condition = _parse_db_json(condition_json)

        text = (
            f"Proposal #{p_id}\n"
            f"- trigger: {trigger}\n"
            f"- status: {status}\n"
            f"- requires_approval: {requires_approval}\n"
            f"- created_at: {created_at}\n"
            f"- action: {action.get('action', '?')}\n"
            f"- description: {action.get('description', '-')}\n"
            f"- args: {action.get('args', {})}\n"
            f"- condition: {condition}"
        )
        await update.message.reply_text(text)
    except ValueError:
        await update.message.reply_text("ID invalido. Uso: /proposal <numero>")
    except Exception as e:
        logger.error("cmd_proposal_error", error=str(e))
        await update.message.reply_text(f"Erro: {str(e)[:100]}")


@authorized_only
async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /approve <id> â€” aprova proposal."""
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
    """Handler para /reject <id> â€” rejeita proposal."""
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


@authorized_only
async def cmd_catalogsync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /catalogsync [check|apply] [source]."""
    from core.catalog import SkillsCatalogSyncEngine

    mode = "check"
    source = None

    if context.args:
        candidate = context.args[0].strip().lower()
        if candidate in {"check", "apply"}:
            mode = candidate
            if len(context.args) > 1:
                source = context.args[1].strip()
        else:
            source = context.args[0].strip()
            if len(context.args) > 1 and context.args[1].strip().lower() in {"check", "apply"}:
                mode = context.args[1].strip().lower()

    try:
        engine = SkillsCatalogSyncEngine()
        result = await engine.sync(mode=mode, source_name=source)
        if not result.get("success"):
            await update.message.reply_text(
                f"❌ catalog sync falhou\n- mode: {mode}\n- erro: {result.get('error', 'unknown')}"
            )
            return

        text = (
            "📚 catalog sync\n"
            f"- mode: {result.get('mode')}\n"
            f"- source_count: {result.get('sources_checked', 0)}\n"
            f"- skills_discovered: {result.get('skills_discovered', 0)}\n"
            f"- changes: {result.get('changes_detected', 0)}\n"
            f"- added: {result.get('added', 0)}\n"
            f"- updated: {result.get('updated', 0)}\n"
            f"- removed: {result.get('removed', 0)}"
        )
        await update.message.reply_text(text)
    except Exception as e:
        logger.error("cmd_catalogsync_error", error=str(e))
        await update.message.reply_text(f"Erro: {str(e)[:100]}")


@authorized_only
async def cmd_updatestatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /updatestatus - status do updater autonomo."""
    try:
        from datetime import datetime, timezone

        redis_conn = get_redis()
        last_check_raw = redis_conn.get("updater:last_check")
        last_summary_raw = redis_conn.get("updater:last_summary")
        summary = _parse_db_json(last_summary_raw)

        last_check_text = "never"
        if last_check_raw:
            try:
                last_check_dt = datetime.fromtimestamp(float(last_check_raw), tz=timezone.utc)
                last_check_text = last_check_dt.isoformat()
            except Exception:
                last_check_text = str(last_check_raw)

        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT run_mode, status, stats, created_at
            FROM skills_catalog_sync_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        latest_sync = cur.fetchone()
        cur.execute(
            """
            SELECT COUNT(*) FROM agent_proposals
            WHERE trigger_name LIKE '%_update_available'
            AND status IN ('pending', 'approved', 'executing')
            """
        )
        open_proposals = cur.fetchone()[0]
        conn.close()

        lines = [
            "Updater status",
            f"- last_check_utc: {last_check_text}",
            f"- open_update_proposals: {open_proposals}",
        ]

        jobs = summary.get("jobs", []) if isinstance(summary, dict) else []
        if jobs:
            for item in jobs[:5]:
                lines.append(
                    f"- job {item.get('job', '?')}: {item.get('status', '?')} "
                    f"(changes={item.get('changes', 0)})"
                )

        if latest_sync:
            run_mode, status, stats_json, created_at = latest_sync
            stats = _parse_db_json(stats_json)
            lines.extend(
                [
                    "",
                    "Latest catalog sync run:",
                    f"- created_at: {created_at}",
                    f"- mode: {run_mode}",
                    f"- status: {status}",
                    f"- changes: {stats.get('changes_detected', 0)}",
                    f"- added: {stats.get('added', 0)}",
                    f"- updated: {stats.get('updated', 0)}",
                    f"- removed: {stats.get('removed', 0)}",
                ]
            )

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error("cmd_updatestatus_error", error=str(e))
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
    """Handler para erros â€” envia para Telegram e log local."""
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
        .connect_timeout(30.0)  # Timeout de conexÃ£o
        .read_timeout(30.0)  # Timeout de leitura
        .write_timeout(30.0)  # Timeout de escrita
        .pool_timeout(30.0)  # Timeout do pool de conexÃµes
        .concurrent_updates(10)  # AtualizaÃ§Ãµes simultÃ¢neas
        .connection_pool_size(20)  # Tamanho do pool de conexÃµes
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
    app.add_handler(CommandHandler("proposal", cmd_proposal))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("catalogsync", cmd_catalogsync))
    app.add_handler(CommandHandler("updatestatus", cmd_updatestatus))

    # Handler para mensagens gerais (LangGraph)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_error_handler(error_handler)

    logger.info("bot_pronto")
    app.run_polling()


if __name__ == "__main__":
    main()

