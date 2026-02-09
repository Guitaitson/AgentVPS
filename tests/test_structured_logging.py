"""
Testes para o Structured Logging.
"""

import io
import json

import pytest

from core.structured_logging import (
    LogCategory,
    LogEntry,
    LoggerManager,
    LogLevel,
    StructuredLogger,
    get_logger,
    log_error,
    log_performance,
)


class TestLogEntry:
    """Testes para entrada de log."""

    def test_create_entry(self):
        """Testa criação de entrada de log."""
        entry = LogEntry(
            timestamp="2024-01-01T00:00:00Z",
            level="INFO",
            category="system",
            message="Test message",
        )

        assert entry.timestamp == "2024-01-01T00:00:00Z"
        assert entry.level == "INFO"
        assert entry.category == "system"
        assert entry.message == "Test message"

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        entry = LogEntry(
            timestamp="2024-01-01T00:00:00Z",
            level="INFO",
            category="system",
            message="Test message",
        )

        entry_dict = entry.to_dict()

        assert entry_dict["timestamp"] == "2024-01-01T00:00:00Z"
        assert entry_dict["level"] == "INFO"
        assert entry_dict["category"] == "system"
        assert entry_dict["message"] == "Test message"

    def test_to_json(self):
        """Testa conversão para JSON."""
        entry = LogEntry(
            timestamp="2024-01-01T00:00:00Z",
            level="INFO",
            category="system",
            message="Test message",
        )

        entry_json = entry.to_json()

        parsed = json.loads(entry_json)
        assert parsed["timestamp"] == "2024-01-01T00:00:00Z"
        assert parsed["level"] == "INFO"
        assert parsed["category"] == "system"


class TestStructuredLogger:
    """Testes para logger estruturado."""

    def test_create_logger(self):
        """Testa criação de logger."""
        logger = StructuredLogger("test_logger")

        assert logger.name == "test_logger"
        assert logger.level == LogLevel.INFO

    def test_set_context(self):
        """Testa definição de contexto."""
        logger = StructuredLogger("test_logger")
        logger.set_context(user_id="test_user", session_id="test_session")

        assert logger._context.user_id == "test_user"
        assert logger._context.session_id == "test_session"

    def test_add_tag(self):
        """Testa adição de tag."""
        logger = StructuredLogger("test_logger")
        logger.add_tag("test_tag")

        assert "test_tag" in logger._context.tags

    def test_add_metadata(self):
        """Testa adição de metadata."""
        logger = StructuredLogger("test_logger")
        logger.add_metadata("key", "value")

        assert logger._context.metadata["key"] == "value"

    def test_log_levels(self):
        """Testa diferentes níveis de log."""
        output = io.StringIO()
        logger = StructuredLogger("test_logger", level=LogLevel.DEBUG, output=output)

        logger.debug(LogCategory.SYSTEM, "Debug message")
        logger.info(LogCategory.SYSTEM, "Info message")
        logger.warning(LogCategory.SYSTEM, "Warning message")
        logger.error(LogCategory.SYSTEM, "Error message")
        logger.critical(LogCategory.SYSTEM, "Critical message")

        output.seek(0)
        logs = output.read()

        assert "Debug message" in logs
        assert "Info message" in logs
        assert "Warning message" in logs
        assert "Error message" in logs
        assert "Critical message" in logs

    def test_log_with_context(self):
        """Testa log com contexto."""
        output = io.StringIO()
        logger = StructuredLogger("test_logger", output=output)
        logger.set_context(user_id="test_user", session_id="test_session")

        logger.info(LogCategory.API, "Test message")

        output.seek(0)
        log_json = output.read()
        log_data = json.loads(log_json)

        assert log_data["context"]["user_id"] == "test_user"
        assert log_data["context"]["session_id"] == "test_session"

    def test_log_with_error(self):
        """Testa log com erro."""
        output = io.StringIO()
        logger = StructuredLogger("test_logger", output=output)

        try:
            raise ValueError("Test error")
        except Exception as e:
            logger.exception(LogCategory.ERROR, "Error occurred", e)

        output.seek(0)
        log_json = output.read()
        log_data = json.loads(log_json)

        assert log_data["error"]["type"] == "ValueError"
        assert log_data["error"]["message"] == "Test error"
        assert "traceback" in log_data["error"]

    def test_log_with_performance(self):
        """Testa log com performance."""
        output = io.StringIO()
        logger = StructuredLogger("test_logger", output=output)

        logger.info(
            LogCategory.PERFORMANCE,
            "Operation completed",
            performance={"operation": "test", "duration_ms": 100}
        )

        output.seek(0)
        log_json = output.read()
        log_data = json.loads(log_json)

        assert log_data["performance"]["operation"] == "test"
        assert log_data["performance"]["duration_ms"] == 100


class TestLoggerManager:
    """Testes para gerenciador de loggers."""

    def test_get_logger(self):
        """Testa obtenção de logger."""
        logger1 = LoggerManager.get_logger("test_logger")
        logger2 = LoggerManager.get_logger("test_logger")

        assert logger1 is logger2

    def test_set_global_level(self):
        """Testa definição de nível global."""
        LoggerManager.get_logger("logger1")
        LoggerManager.get_logger("logger2")

        LoggerManager.set_global_level(LogLevel.DEBUG)

        assert LoggerManager._loggers["logger1"].level == LogLevel.DEBUG
        assert LoggerManager._loggers["logger2"].level == LogLevel.DEBUG


class TestLogHelpers:
    """Testes para helpers de log."""

    def test_log_performance(self):
        """Testa log de performance."""
        output = io.StringIO()
        logger = StructuredLogger("test_logger", output=output)

        log_performance(logger, "test_operation", 150.5, extra_info="test")

        output.seek(0)
        log_json = output.read()
        log_data = json.loads(log_json)

        assert log_data["performance"]["operation"] == "test_operation"
        assert log_data["performance"]["duration_ms"] == 150.5
        assert log_data["performance"]["extra_info"] == "test"

    def test_log_error(self):
        """Testa log de erro."""
        output = io.StringIO()
        logger = StructuredLogger("test_logger", output=output)

        try:
            raise RuntimeError("Test error")
        except Exception as e:
            log_error(logger, e, context={"user_id": "test_user"})

        output.seek(0)
        log_json = output.read()
        log_data = json.loads(log_json)

        assert log_data["error"]["type"] == "RuntimeError"
        assert log_data["error"]["message"] == "Test error"
        assert log_data["error"]["user_id"] == "test_user"

    def test_get_logger(self):
        """Testa função get_logger."""
        logger = get_logger("test_logger")

        assert logger.name == "test_logger"
        assert isinstance(logger, StructuredLogger)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
