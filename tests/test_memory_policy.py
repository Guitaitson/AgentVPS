from core.memory import MemoryPolicy, MemoryType


def test_memory_policy_redacts_sensitive_keys():
    policy = MemoryPolicy()
    payload = {
        "api_key": "plain-secret",
        "profile": {
            "name": "alice",
            "token": "abc123",
        },
    }

    redacted = policy.redact_value(payload)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["profile"]["token"] == "[REDACTED]"
    assert redacted["profile"]["name"] == "alice"


def test_memory_policy_redacts_string_patterns():
    policy = MemoryPolicy()
    value = "Authorization: Bearer this_is_a_token"

    redacted = policy.redact_value(value)

    assert "Bearer" not in redacted
    assert redacted == "Authorization: [REDACTED]"


def test_memory_policy_ttl_defaults():
    policy = MemoryPolicy()

    assert policy.ttl_for(MemoryType.EPISODIC) is not None
    assert policy.ttl_for(MemoryType.SEMANTIC) is not None
    assert policy.ttl_for(MemoryType.PROFILE) is None


def test_memory_policy_sanitize_context_keeps_only_allowed_keys():
    policy = MemoryPolicy()
    context = {
        "public_summary": "ok",
        "secret_token": "top-secret",
        "internal_notes": "do not delegate",
    }

    sanitized = policy.sanitize_context(context, allowed_keys={"public_summary", "secret_token"})

    assert "public_summary" in sanitized
    assert "secret_token" in sanitized
    assert sanitized["secret_token"] == "[REDACTED]"
    assert "internal_notes" not in sanitized
