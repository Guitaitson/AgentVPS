"""
VPS-Agent Telegram Bot Ã¢â‚¬â€ Interface principal
VersÃƒÂ£o: 2.0 Ã¢â‚¬â€ Com LangGraph e timeout otimizado
"""

import asyncio
import logging
import os
import time

import psycopg2
import redis
import structlog
from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# VPS-Agent Core (nosso mÃƒÂ³dulo)
from core.env import load_project_env
from core.vps_agent.agent import process_message_async

# Telegram Log Handler (F0-06)

# ConfiguraÃƒÂ§ÃƒÂ£o de logging estruturado
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# Carregar variÃƒÂ¡veis de ambiente
load_project_env()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USERS = [
    int(uid.strip()) for uid in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if uid.strip()
]
PROGRESS_MESSAGE_THRESHOLD_SECONDS = float(
    os.getenv("TELEGRAM_PROGRESS_MESSAGE_THRESHOLD_SECONDS", "2.0")
)
TYPING_INTERVAL_SECONDS = float(os.getenv("TELEGRAM_TYPING_INTERVAL_SECONDS", "4.0"))


class TelegramProgressSession:
    """Typing indicator plus a single editable status message."""

    PHASE_LABELS = {
        "received": "Analisando mensagem...",
        "routing": "Definindo a melhor rota...",
        "formatting": "Escrevendo resposta...",
        "done": "Finalizando resposta...",
        "error": "Tratando erro...",
    }

    SERVER_LABELS = {
        "fleetintel": "Consultando FleetIntel...",
        "brazilcnpj": "Consultando BrazilCNPJ...",
        "codex_operator": "Delegando ao operador Codex...",
    }

    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.update = update
        self.context = context
        self.chat_id = update.effective_chat.id
        self.start_time = time.monotonic()
        self._typing_task: asyncio.Task | None = None
        self._delayed_task: asyncio.Task | None = None
        self._status_message = None
        self._last_label = "Analisando mensagem..."
        self._closed = False

    async def start(self) -> None:
        self._typing_task = asyncio.create_task(self._typing_loop())
        self._delayed_task = asyncio.create_task(self._show_status_after_threshold())

    async def on_progress(self, event: str, payload: dict[str, object]) -> None:
        label = self._resolve_label(event, payload)
        if not label or label == self._last_label:
            return
        self._last_label = label
        if self._status_message is None:
            if time.monotonic() - self.start_time < PROGRESS_MESSAGE_THRESHOLD_SECONDS:
                return
            await self._ensure_status_message()
        await self._edit_status_message(label)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for task in (self._typing_task, self._delayed_task):
            if task is None:
                continue
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if self._status_message is not None:
            try:
                await self._status_message.delete()
            except Exception:
                try:
                    await self._status_message.edit_text("Resposta pronta.")
                except Exception:
                    pass

    async def _typing_loop(self) -> None:
        while not self._closed:
            try:
                await self.context.bot.send_chat_action(
                    chat_id=self.chat_id, action=ChatAction.TYPING
                )
            except Exception as exc:
                logger.debug("typing_indicator_error", error=str(exc))
                return
            await asyncio.sleep(TYPING_INTERVAL_SECONDS)

    async def _show_status_after_threshold(self) -> None:
        await asyncio.sleep(PROGRESS_MESSAGE_THRESHOLD_SECONDS)
        if self._closed or self._status_message is not None:
            return
        await self._ensure_status_message()

    async def _ensure_status_message(self) -> None:
        if self._status_message is not None or self._closed:
            return
        self._status_message = await self.update.message.reply_text(self._last_label)

    async def _edit_status_message(self, label: str) -> None:
        if self._status_message is None or self._closed:
            return
        try:
            await self._status_message.edit_text(label)
        except BadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                logger.debug("progress_edit_ignored", error=str(exc))
        except Exception as exc:
            logger.debug("progress_edit_failed", error=str(exc))

    def _resolve_label(self, event: str, payload: dict[str, object]) -> str:
        if event == "external_call":
            server = str(payload.get("server") or "").lower()
            return self.SERVER_LABELS.get(server, "Executando integracao externa...")
        return self.PHASE_LABELS.get(event, "Processando...")


# ConexÃƒÂµes
def get_db_conn():
    """Retorna conexÃƒÂ£o com PostgreSQL."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "vps_agent"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def get_redis():
    """Retorna conexÃƒÂ£o com Redis."""
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


# Middleware de seguranÃƒÂ§a
def authorized_only(func):
    """Decorator: sÃƒÂ³ permite usuÃƒÂ¡rios autorizados."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USERS:
            logger.warning("acesso_negado", user_id=user_id)
            await update.message.reply_text("Ã¢â€ºâ€ Acesso nÃƒÂ£o autorizado.")
            return
        return await func(update, context)

    return wrapper


async def _run_agent_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: str,
    message: str,
) -> str:
    progress = TelegramProgressSession(update, context)
    await progress.start()
    try:
        return await process_message_async(user_id, message, progress_callback=progress.on_progress)
    finally:
        await progress.close()


# Handlers
@authorized_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /start."""
    user_name = update.effective_user.first_name

    await update.message.reply_text(
        f"Ã°Å¸Â¤â€“ **VPS-Agent v2 Online!**\n\n"
        f"OlÃƒÂ¡, {user_name}! Seu agente autÃƒÂ´nomo estÃƒÂ¡ pronto.\n\n"
        f"**Comandos disponÃƒÂ­veis:**\n"
        f"Ã¢â‚¬Â¢ `/status` Ã¢â‚¬â€ Estado da VPS\n"
        f"Ã¢â‚¬Â¢ `/ram` Ã¢â‚¬â€ Uso de memÃƒÂ³ria\n"
        f"Ã¢â‚¬Â¢ `/containers` Ã¢â‚¬â€ Containers ativos\n"
        f"Ã¢â‚¬Â¢ `/health` Ã¢â‚¬â€ Health check completo\n"
        f"Ã¢â‚¬Â¢ `/help` Ã¢â‚¬â€ Ajuda\n\n"
        f"Ou basta enviar uma mensagem e eu proceso atravÃƒÂ©s do LangGraph!"
    )


@authorized_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens gerais Ã¢â‚¬â€ usa LangGraph com tratamento de erro robusto."""
    user_id = str(update.effective_user.id)
    message = update.message.text

    logger.info("mensagem_recebida", user_id=user_id, message=message[:100])

    try:
        # Processar atravÃƒÂ©s do LangGraph
        response = await _run_agent_request(
            update,
            context,
            user_id=user_id,
            message=message,
        )

        # Garantir que temos uma resposta vÃƒÂ¡lida
        if not response:
            response = "Desculpe, nÃƒÂ£o consegui processar sua mensagem. Tente novamente."

        await update.message.reply_text(response)

    except Exception as e:
        logger.error("erro_processamento_mensagem", user_id=user_id, error=str(e))

        # Resposta de fallback amigÃƒÂ¡vel
        fallback_response = (
            "Ã°Å¸Â¤â€“ **VPS-Agent**\n\n"
            "Desculpe, ocorreu um erro ao processar sua mensagem.\n\n"
            "VocÃƒÂª pode tentar:\n"
            "Ã¢â‚¬Â¢ Enviar a mensagem novamente\n"
            "Ã¢â‚¬Â¢ Usar comandos diretos como `/status` ou `/help`\n\n"
            f"_Erro: {str(e)[:100]}_"
        )

        try:
            await update.message.reply_text(fallback_response, parse_mode="Markdown")
        except Exception:
            # Se atÃƒÂ© o fallback falhar, enviar sem markdown
            await update.message.reply_text(
                "Desculpe, ocorreu um erro. Tente novamente ou use /help."
            )


@authorized_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /status Ã¢â‚¬â€ usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_status", user_id=user_id)

    # Roteia pelo grafo com /status para ativar intent de comando
    response = await _run_agent_request(update, context, user_id=user_id, message="/status")
    await update.message.reply_text(response)


@authorized_only
async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /ram Ã¢â‚¬â€ usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_ram", user_id=user_id)

    # Roteia pelo grafo com /ram para ativar intent de comando
    response = await _run_agent_request(update, context, user_id=user_id, message="/ram")
    await update.message.reply_text(response)


@authorized_only
async def cmd_containers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /containers Ã¢â‚¬â€ usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_containers", user_id=user_id)

    # Roteia pelo grafo com /containers para ativar intent de comando
    response = await _run_agent_request(update, context, user_id=user_id, message="/containers")
    await update.message.reply_text(response)


@authorized_only
async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /health Ã¢â‚¬â€ usa grafo LangGraph."""
    user_id = str(update.effective_user.id)
    logger.info("comando_health", user_id=user_id)

    # Roteia pelo grafo com /health para ativar intent de comando
    response = await _run_agent_request(update, context, user_id=user_id, message="/health")
    await update.message.reply_text(response)


@authorized_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /help Ã¢â‚¬â€ ajuda."""
    help_text = """
**VPS-Agent v3 - Ajuda**

**Comandos disponiveis:**
- `/start` - Iniciar conversa
- `/status` - Estado geral da VPS
- `/ram` - Uso de memoria por container
- `/containers` - Lista de containers ativos
- `/health` - Health check completo
- `/proposals` - Lista proposals autonomas pendentes
- `/proposal <id>` - Detalha uma proposal
- `/approve <id>` - Aprova proposal autonoma
- `/reject <id>` - Rejeita proposal autonoma
- `/catalogsync <cmd>` - check/apply/pin/unpin/rollback/provenance do catalogo
- `/runtimes [list|enable|disable]` - Gerencia runtimes externos
- `/contextsync` - Processa audios pendentes na inbox de voz
- `/contextstatus` - Mostra status da captura de contexto por voz
- `/contextdiscard <job_id>` - Descarta lote de voz ruim e remove memoria derivada
- `/updatestatus` - Mostra status do updater automatico
- `/help` - Esta ajuda

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
    """Handler para /approve <id> Ã¢â‚¬â€ aprova proposal."""
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
            try:
                from core.voice_context import VoiceContextService

                VoiceContextService().sync_proposal_state(
                    proposal_id=proposal_id,
                    decision="approved",
                    actor=f"tg:{update.effective_user.id}",
                )
            except Exception as sync_exc:
                logger.error("cmd_approve_voice_sync_error", error=str(sync_exc))
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
    """Handler para /reject <id> Ã¢â‚¬â€ rejeita proposal."""
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
            try:
                from core.voice_context import VoiceContextService

                VoiceContextService().sync_proposal_state(
                    proposal_id=proposal_id,
                    decision="rejected",
                    actor=f"tg:{update.effective_user.id}",
                )
            except Exception as sync_exc:
                logger.error("cmd_reject_voice_sync_error", error=str(sync_exc))
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
    """Handler para /catalogsync commands."""
    from core.catalog import SkillsCatalogSyncEngine

    try:
        engine = SkillsCatalogSyncEngine()
        args = [arg.strip() for arg in context.args] if context.args else []
        command = args[0].lower() if args else "check"

        if command in {"check", "apply"}:
            source = args[1] if len(args) > 1 else None
            result = await engine.sync(mode=command, source_name=source)
            if not result.get("success"):
                await update.message.reply_text(
                    f"ERRO catalog sync falhou\n- mode: {command}\n- erro: {result.get('error', 'unknown')}"
                )
                return
            text = (
                "catalog sync\n"
                f"- mode: {result.get('mode')}\n"
                f"- source_count: {result.get('sources_checked', 0)}\n"
                f"- skills_discovered: {result.get('skills_discovered', 0)}\n"
                f"- changes: {result.get('changes_detected', 0)}\n"
                f"- added: {result.get('added', 0)}\n"
                f"- updated: {result.get('updated', 0)}\n"
                f"- removed: {result.get('removed', 0)}\n"
                f"- pinned_skipped: {result.get('pinned_skipped', 0)}"
            )
            await update.message.reply_text(text)
            return

        if command == "pin":
            if len(args) < 2:
                await update.message.reply_text(
                    "Uso: /catalogsync pin <skill_name> [source_name] [version]"
                )
                return
            skill_name = args[1]
            source_name = args[2] if len(args) > 2 else None
            version = args[3] if len(args) > 3 else None
            result = await engine.pin(
                skill_name=skill_name,
                source_name=source_name,
                version=version,
                pinned_by=f"tg:{update.effective_user.id}",
            )
            if not result.get("success"):
                await update.message.reply_text(
                    f"ERRO pin falhou: {result.get('error', 'unknown_error')}"
                )
                return
            await update.message.reply_text(
                "pin aplicado\n"
                f"- skill: {result.get('skill_name')}\n"
                f"- source: {result.get('source_name')}\n"
                f"- version: {result.get('pinned_version')}"
            )
            return

        if command == "unpin":
            if len(args) < 2:
                await update.message.reply_text(
                    "Uso: /catalogsync unpin <skill_name> [source_name]"
                )
                return
            skill_name = args[1]
            source_name = args[2] if len(args) > 2 else None
            result = await engine.unpin(skill_name=skill_name, source_name=source_name)
            if not result.get("success"):
                await update.message.reply_text(
                    f"ERRO unpin falhou: {result.get('error', 'unknown_error')}"
                )
                return
            await update.message.reply_text(f"unpin concluido (updated={result.get('updated', 0)})")
            return

        if command == "rollback":
            if len(args) < 2:
                await update.message.reply_text(
                    "Uso: /catalogsync rollback <skill_name> [source_name] [target_version]"
                )
                return
            skill_name = args[1]
            source_name = args[2] if len(args) > 2 else None
            target_version = args[3] if len(args) > 3 else None
            result = await engine.rollback(
                skill_name=skill_name,
                source_name=source_name,
                target_version=target_version,
                actor=f"tg:{update.effective_user.id}",
                reason="rollback via telegram",
            )
            if not result.get("success"):
                await update.message.reply_text(
                    f"ERRO rollback falhou: {result.get('error', 'unknown_error')}"
                )
                return
            await update.message.reply_text(
                "rollback concluido\n"
                f"- skill: {result.get('skill_name')}\n"
                f"- source: {result.get('source_name')}\n"
                f"- version: {result.get('rolled_back_to_version')}"
            )
            return

        if command == "provenance":
            if len(args) < 2:
                await update.message.reply_text(
                    "Uso: /catalogsync provenance <skill_name> [source_name] [limit]"
                )
                return
            skill_name = args[1]
            source_name = args[2] if len(args) > 2 else None
            limit = int(args[3]) if len(args) > 3 and args[3].isdigit() else 5
            result = await engine.provenance(
                skill_name=skill_name,
                source_name=source_name,
                limit=limit,
            )
            if not result.get("success"):
                await update.message.reply_text(
                    f"Erro provenance: {result.get('error', 'unknown_error')}"
                )
                return
            current = result.get("current", {})
            history = result.get("history", [])
            lines = [
                "provenance",
                f"- skill: {current.get('skill_name')}",
                f"- source: {current.get('source_name')}",
                f"- current_version: {current.get('version')}",
                f"- status: {current.get('status')}",
                f"- pinned: {current.get('pinned', False)}",
            ]
            if current.get("pinned_version"):
                lines.append(f"- pinned_version: {current.get('pinned_version')}")
            if history:
                lines.append("")
                lines.append("history:")
                for item in history[:limit]:
                    lines.append(
                        f"- {item.get('changed_at', '?')} | v{item.get('version')} | {item.get('change_type', item.get('status', '?'))}"
                    )
            await update.message.reply_text("\n".join(lines))
            return

        await update.message.reply_text(
            "Uso: /catalogsync [check|apply|pin|unpin|rollback|provenance] ..."
        )
    except Exception as e:
        logger.error("cmd_catalogsync_error", error=str(e))
        await update.message.reply_text(f"Erro: {str(e)[:100]}")


@authorized_only
async def cmd_runtimes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /runtimes [list|enable|disable] [protocol]."""
    from core.orchestration import RuntimeControl, reset_runtime_router_for_tests

    args = [arg.strip().lower() for arg in context.args] if context.args else []
    command = args[0] if args else "list"

    try:
        control = RuntimeControl()
        if command == "list":
            states = control.list_states()
            lines = ["Runtime status:"]
            for state in states:
                endpoint = state.endpoint or "-"
                lines.append(
                    f"- {state.protocol}: {'enabled' if state.enabled else 'disabled'} "
                    f"(source={state.source}, default={state.default_enabled}, endpoint={endpoint})"
                )
            await update.message.reply_text("\n".join(lines))
            return

        if command in {"enable", "disable"}:
            if len(args) < 2:
                await update.message.reply_text("Uso: /runtimes [enable|disable] <protocol>")
                return
            protocol = args[1]
            result = control.set_enabled(protocol, command == "enable")
            if not result.get("success"):
                await update.message.reply_text(
                    f"Erro runtime update: {result.get('error', 'unknown_error')}"
                )
                return
            reset_runtime_router_for_tests()
            await update.message.reply_text(
                f"Runtime '{result.get('protocol')}' -> {'enabled' if result.get('enabled') else 'disabled'}"
            )
            return

        await update.message.reply_text("Uso: /runtimes [list|enable|disable] [protocol]")
    except Exception as e:
        logger.error("cmd_runtimes_error", error=str(e))
        await update.message.reply_text(f"Erro: {str(e)[:100]}")


@authorized_only
async def cmd_contextsync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /contextsync - processa inbox de audios pendentes."""
    try:
        from core.voice_context import VoiceContextService

        result = await VoiceContextService().sync_inbox(
            source=f"telegram:{update.effective_user.id}"
        )
        if not result.get("success"):
            await update.message.reply_text(
                f"Erro context sync: {result.get('error', 'unknown_error')}"
            )
            return
        await update.message.reply_text(
            "voice context sync\n"
            f"- status: {result.get('status', 'ok')}\n"
            f"- processed_files: {result.get('processed_files', 0)}\n"
            f"- duplicates_skipped: {result.get('duplicates_skipped', 0)}\n"
            f"- failed_files: {result.get('failed_files', 0)}\n"
            f"- discarded_low_quality: {result.get('discarded_low_quality', 0)}\n"
            f"- context_items: {result.get('context_items', 0)}\n"
            f"- auto_committed: {result.get('auto_committed', 0)}\n"
            f"- pending_review: {result.get('pending_review', 0)}"
        )
    except Exception as e:
        logger.error("cmd_contextsync_error", error=str(e))
        await update.message.reply_text(f"Erro: {str(e)[:100]}")


@authorized_only
async def cmd_contextstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /contextstatus - status do pipeline de voz."""
    try:
        from core.voice_context import VoiceContextService

        result = VoiceContextService().get_status()
        last_job = result.get("last_job") or {}
        stats = last_job.get("stats") or {}
        lines = [
            "voice context status",
            f"- inbox_files: {result.get('inbox_files', 0)}",
            f"- pending_review: {result.get('pending_review', 0)}",
            f"- approved_review: {result.get('approved_review', 0)}",
            f"- committed_items: {result.get('committed_items', 0)}",
            f"- rejected_items: {result.get('rejected_items', 0)}",
            f"- discarded_items: {result.get('discarded_items', 0)}",
        ]
        if last_job:
            lines.extend(
                [
                    "",
                    "last_job:",
                    f"- id: {last_job.get('id')}",
                    f"- source: {last_job.get('source')}",
                    f"- batch_date: {last_job.get('batch_date')}",
                    f"- status: {last_job.get('status')}",
                    f"- processed_files: {stats.get('processed_files', 0)}",
                    f"- discarded_low_quality: {stats.get('discarded_low_quality', 0)}",
                    f"- auto_committed: {stats.get('auto_committed', 0)}",
                    f"- pending_review: {stats.get('pending_review', 0)}",
                ]
            )
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error("cmd_contextstatus_error", error=str(e))
        await update.message.reply_text(f"Erro: {str(e)[:100]}")


@authorized_only
async def cmd_updatestatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /updatestatus - status do updater autonomo."""
    try:
        from datetime import datetime, timezone

        from core.updater.deploy_safety import collect_deploy_safety_snapshot

        redis_conn = get_redis()
        last_check_raw = redis_conn.get("updater:last_check")
        last_summary_raw = redis_conn.get("updater:last_summary")
        summary = _parse_db_json(last_summary_raw)
        deploy_safety = collect_deploy_safety_snapshot()

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
            f"- safe_to_release_deploy: {str(deploy_safety.safe_to_deploy).lower()}",
            (
                "- active_blockers: "
                f"voice_jobs={deploy_safety.voice_jobs_running}, "
                f"voice_files={deploy_safety.voice_files_processing}, "
                f"missions={deploy_safety.running_missions}, "
                f"proposals={deploy_safety.executing_proposals}, "
                f"tasks={deploy_safety.running_tasks}, "
                f"manual={deploy_safety.manual_blockers}"
            ),
        ]

        jobs = summary.get("jobs", []) if isinstance(summary, dict) else []
        if jobs:
            for item in jobs[:5]:
                lines.append(
                    f"- job {item.get('job', '?')}: {item.get('status', '?')} "
                    f"(changes={item.get('changes', 0)})"
                )

        lines.extend(
            [
                "",
                "Update policy:",
                "- AgentVPS core usa release + deploy gate automatico",
                "- skills/tools/agentes externos do acervo entram por catalog sync e approval workflow",
                "- jobs longos podem criar blockers em runtime/deploy-blockers para adiar deploys",
            ]
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
                    f"- pinned_skipped: {stats.get('pinned_skipped', 0)}",
                ]
            )

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.error("cmd_updatestatus_error", error=str(e))
        await update.message.reply_text(f"Erro: {str(e)[:100]}")


@authorized_only
async def cmd_contextdiscard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para /contextdiscard [job_id] - descarta lote de voz."""
    try:
        from core.voice_context import VoiceContextService

        service = VoiceContextService()
        if context.args:
            job_id = int(context.args[0])
        else:
            last_job = service.get_status().get("last_job") or {}
            job_id = int(last_job.get("id", 0))

        if not job_id:
            await update.message.reply_text("Uso: /contextdiscard <job_id>")
            return

        result = service.discard_job(
            job_id=job_id,
            actor=f"tg:{update.effective_user.id}",
            note="discarded via telegram after user review",
        )
        if not result.get("success"):
            await update.message.reply_text("Erro ao descartar lote de voz.")
            return
        await update.message.reply_text(
            "voice context discarded\n"
            f"- job_id: {job_id}\n"
            f"- discarded_items: {result.get('discarded_items', 0)}\n"
            f"- deleted_memories: {result.get('deleted_memories', 0)}\n"
            f"- rejected_proposals: {result.get('rejected_proposals', 0)}"
        )
    except ValueError:
        await update.message.reply_text("Uso: /contextdiscard <job_id>")
    except Exception as e:
        logger.error("cmd_contextdiscard_error", error=str(e))
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
    """Handler para erros Ã¢â‚¬â€ envia para Telegram e log local."""
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
        .connect_timeout(30.0)  # Timeout de conexÃƒÂ£o
        .read_timeout(30.0)  # Timeout de leitura
        .write_timeout(30.0)  # Timeout de escrita
        .pool_timeout(30.0)  # Timeout do pool de conexÃƒÂµes
        .concurrent_updates(10)  # AtualizaÃƒÂ§ÃƒÂµes simultÃƒÂ¢neas
        .connection_pool_size(20)  # Tamanho do pool de conexÃƒÂµes
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
    app.add_handler(CommandHandler("runtimes", cmd_runtimes))
    app.add_handler(CommandHandler("contextsync", cmd_contextsync))
    app.add_handler(CommandHandler("contextstatus", cmd_contextstatus))
    app.add_handler(CommandHandler("contextdiscard", cmd_contextdiscard))
    app.add_handler(CommandHandler("updatestatus", cmd_updatestatus))

    # Handler para mensagens gerais (LangGraph)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_error_handler(error_handler)

    logger.info("bot_pronto")
    app.run_polling()


if __name__ == "__main__":
    main()
