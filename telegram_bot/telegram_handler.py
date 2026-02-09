"""
Telegram Log Handler — Notifica erros CRITICAL via Telegram
F0-06 — FASE 0 Estabilização
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import structlog
from telegram import Bot
from telegram.error import TelegramError

# Carregar variáveis de ambiente
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")

# Instância do bot (lazy initialization)
_bot_instance: Optional[Bot] = None


def get_bot() -> Optional[Bot]:
    """Retorna instância do bot (lazy init)."""
    global _bot_instance
    if _bot_instance is None and TELEGRAM_BOT_TOKEN:
        try:
            _bot_instance = Bot(token=TELEGRAM_BOT_TOKEN)
        except TelegramError:
            pass
    return _bot_instance


class TelegramLogHandler(logging.Handler):
    """
    Handler de logging que envia mensagens CRITICAL para Telegram.

    Uso:
        handler = TelegramLogHandler()
        logger.addHandler(handler)
    """

    def __init__(self, level: int = logging.CRITICAL, chat_id: Optional[str] = None):
        super().__init__(level=level)
        self.chat_id = chat_id or TELEGRAM_ADMIN_CHAT_ID

    def emit(self, record: logging.LogRecord):
        """Envia mensagem para Telegram se for CRITICAL."""
        if record.levelno < self.level:
            return

        bot = get_bot()
        if not bot or not self.chat_id:
            return

        try:
            # Formatar mensagem
            message = self._format_message(record)
            bot.send_message(chat_id=self.chat_id, text=message, parse_mode="Markdown")
        except TelegramError:
            pass  # Silencioso para evitar loops

    def _format_message(self, record: logging.LogRecord) -> str:
        """Formata a mensagem do log para Telegram."""
        emoji = {
            logging.CRITICAL: "🚨",
            logging.ERROR: "❌",
            logging.WARNING: "⚠️",
            logging.INFO: "ℹ️",
        }.get(record.levelno, "📝")

        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        # Limitar tamanho da mensagem
        msg = str(record.getMessage())
        if len(msg) > 1000:
            msg = msg[:997] + "..."

        return (
            f"{emoji} **VPS-Agent Log**\n\n"
            f"**Nível:** {record.levelname}\n"
            f"**Hora:** {timestamp}\n"
            f"**Arquivo:** {record.filename}:{record.lineno}\n"
            f"**Logger:** {record.name}\n"
            f"**Mensagem:**\n```{msg}```"
        )


class TelegramNotifier:
    """
    Classe para enviar notificações específicas via Telegram.

    Uso:
        notifier = TelegramNotifier()
        notifier.send_critical("Container com alta RAM")
        notifier.send_alert("Backup concluído")
    """

    def __init__(self, chat_id: Optional[str] = None):
        self.chat_id = chat_id or TELEGRAM_ADMIN_CHAT_ID

    def send(self, text: str, level: str = "info", disable_notification: bool = False):
        """Envia mensagem para Telegram."""
        bot = get_bot()
        if not bot or not self.chat_id:
            return False

        try:
            emoji = {
                "critical": "🚨",
                "error": "❌",
                "warning": "⚠️",
                "info": "ℹ️",
                "success": "✅",
            }.get(level, "📝")

            message = f"{emoji} **VPS-Agent**\n\n{text}"
            bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown",
                disable_notification=disable_notification,
            )
            return True
        except TelegramError:
            return False

    def send_critical(self, text: str):
        """Envia mensagem CRITICAL (notifica)."""
        return self.send(text, level="critical")

    def send_error(self, text: str):
        """Envia mensagem ERROR (notifica)."""
        return self.send(text, level="error")

    def send_warning(self, text: str):
        """Envia mensagem WARNING (não perturba)."""
        return self.send(text, level="warning", disable_notification=True)

    def send_info(self, text: str):
        """Envia mensagem INFO (não perturba)."""
        return self.send(text, level="info", disable_notification=True)

    def send_success(self, text: str):
        """Envia mensagem SUCCESS (não perturba)."""
        return self.send(text, level="success", disable_notification=True)

    def send_health_check(self, status: dict):
        """Envia health check formatado."""
        emoji = "✅" if status.get("healthy") else "🚨"
        lines = []
        for service, ok in status.get("services", {}).items():
            lines.append(f"{'✅' if ok else '❌'} {service}")

        text = (
            f"{emoji} **Health Check**\n\n{chr(10).join(lines)}\n\nRAM: {status.get('ram', 'N/A')}"
        )
        return self.send(text, level="warning" if not status.get("healthy") else "success")


def setup_telegram_logging(logger_name: str = None) -> tuple:
    """
    Configura logging com Telegram Handler.

    Returns:
        tuple: (structlog logger, TelegramNotifier instance)
    """
    # Criar notifier
    notifier = TelegramNotifier()

    # Criar handler
    handler = TelegramLogHandler(level=logging.CRITICAL)

    # Configurar structlog se logger_name fornecido
    if logger_name:
        log = structlog.get_logger(logger_name)
        # Adicionar handler ao logger root
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
    else:
        log = structlog.get_logger()

    return log, notifier


# Função de conveniência para integração rápida
def get_telegram_notifier() -> TelegramNotifier:
    """Retorna instância do TelegramNotifier."""
    return TelegramNotifier()
