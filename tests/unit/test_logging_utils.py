"""P1-14: 安全日誌工具 + 假 Secret Exception 回歸"""
import logging

from backend.logging_utils import (
    ErrorCode,
    redact_secrets,
    short_id,
    safe_log_extra,
    new_request_id,
    get_request_id,
    format_external_error,
    log_external_failure,
    RedactingFilter,
)


def test_redact_api_key():
    s = redact_secrets("key=sk-proj-ABCDEFGHIJKLMNOPQRST")
    assert "sk-proj-ABCDEFGHIJKLMNOPQRST" not in s
    assert "REDACTED" in s


def test_redact_jwtish():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaa.bbbb"
    red = redact_secrets(f"token {jwt}")
    assert "REDACTED" in red
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaa.bbbb" not in red


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


def test_format_external_error_production_hides_secret_in_exception(monkeypatch):
    monkeypatch.delenv("LOG_VERBOSE_EXCEPTIONS", raising=False)
    new_request_id()
    exc = RuntimeError(
        "OpenAI failed api_key=sk-proj-FAKESECRETKEY12345 "
        "auth Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxx.yyy"
    )
    summary = format_external_error(exc, code=ErrorCode.OPENAI_ERROR)
    assert "RuntimeError" in summary
    assert ErrorCode.OPENAI_ERROR in summary
    assert "sk-proj-FAKESECRETKEY12345" not in summary
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in summary
    # 診斷仍保留類型
    assert "type=RuntimeError" in summary


def test_format_external_error_verbose_still_redacts(monkeypatch):
    monkeypatch.setenv("LOG_VERBOSE_EXCEPTIONS", "true")
    exc = ValueError("bad key sk-proj-VISIBLELEAK999 and done")
    summary = format_external_error(exc, code=ErrorCode.OPENAI_ERROR)
    assert "sk-proj-VISIBLELEAK999" not in summary
    assert "REDACTED" in summary or "ValueError" in summary


def test_log_external_failure_does_not_use_exception_traceback(monkeypatch, caplog):
    monkeypatch.delenv("LOG_VERBOSE_EXCEPTIONS", raising=False)
    logger = logging.getLogger("test_external_fail")
    exc = ConnectionError("SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aa.bb")
    with caplog.at_level(logging.ERROR, logger="test_external_fail"):
        summary = log_external_failure(
            logger, exc, code=ErrorCode.SUPABASE_ERROR, event="sb_down"
        )
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in summary
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in caplog.text
    assert "ConnectionError" in summary or "SUPABASE_ERROR" in summary


def test_redacting_filter_docs_limitation_on_msg_only():
    """Filter 可脫敏 msg，但不保證 exc_info（此測試鎖定 msg 行為）。"""
    f = RedactingFilter()
    record = logging.LogRecord(
        name="t",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="fail sk-proj-ABCDEFGHIJKLMN",
        args=(),
        exc_info=None,
    )
    assert f.filter(record) is True
    assert "sk-proj-ABCDEFGHIJKLMN" not in str(record.msg)
