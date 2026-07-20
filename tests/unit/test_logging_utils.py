"""P1-14: 安全日誌工具"""
from backend.logging_utils import (
    ErrorCode,
    redact_secrets,
    short_id,
    safe_log_extra,
    new_request_id,
    get_request_id,
)


def test_redact_api_key():
    s = redact_secrets("key=sk-proj-ABCDEFGHIJKLMNOPQRST")
    assert "sk-proj-ABCDEFGHIJKLMNOPQRST" not in s
    assert "REDACTED" in s


def test_redact_jwtish():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaa.bbbb"
    assert "eyJ" not in redact_secrets(f"token {jwt}") or "REDACTED" in redact_secrets(
        f"token {jwt}"
    )


def test_short_id():
    assert short_id("abcdefghijklmnop") == "abcdefgh…"
    assert short_id(None) == "-"


def test_request_id_context():
    rid = new_request_id()
    assert len(rid) == 16
    assert get_request_id() == rid


def test_safe_log_extra_strips_message():
    extra = safe_log_extra(
        conversation_id="conv123456",
        user_id="user987654",
        event="chat",
        message="SECRET CHAT",
        password="x",
    )
    assert "SECRET CHAT" not in str(extra)
    assert extra["conversation_id"].startswith("conv1234")
    assert ErrorCode.OPENAI_ERROR == "OPENAI_ERROR"
