"""
Pytest configuration for VPS-Agent tests.

Com o novo sistema de pacotes (pyproject.toml), os imports devem ser:
- from core.xxx import ... (para código do core)
- from telegram_bot.xxx import ... (para código do telegram)

Para desenvolvimento local sem instalação, adicionamos o diretório raiz ao path.
"""
import sys
import os

# Add project root to path for imports (development mode)
# Quando o pacote estiver instalado via pip install -e ., isso não é necessário
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Também adicionar o diretório pai para imports absolutos funcionarem
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Mock para testes que precisam de variáveis de ambiente
import pytest


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Fixture para mockar variáveis de ambiente comuns."""
    env_vars = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "test_db",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_pass",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_ALLOWED_USERS": "123456",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def mock_telegram_update():
    """Fixture para criar mock de update do Telegram."""
    class MockUser:
        def __init__(self):
            self.id = 123456
            self.first_name = "Test"
            self.username = "testuser"
    
    class MockChat:
        def __init__(self):
            self.id = 123456
            self.type = "private"
    
    class MockMessage:
        def __init__(self, text="/start"):
            self.text = text
            self.chat = MockChat()
            self.from_user = MockUser()
            self.message_id = 1
    
    class MockUpdate:
        def __init__(self, text="/start"):
            self.message = MockMessage(text)
            self.effective_user = MockUser()
    
    return MockUpdate
