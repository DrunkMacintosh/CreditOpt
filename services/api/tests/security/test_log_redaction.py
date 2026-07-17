from __future__ import annotations

import json
import logging

from starlette.responses import Response

from creditops.log_redaction import LogRedactor
from creditops.observability import StructuredJsonFormatter
from creditops.security_headers import apply_security_headers


def test_signed_urls_and_tokens_are_redacted() -> None:
    redactor = LogRedactor()

    event = redactor.clean(
        {"authorization": "Bearer secret", "signedUrl": "https://storage/token"}
    )

    assert event == {"authorization": "[REDACTED]", "signedUrl": "[REDACTED]"}


def test_redaction_is_recursive_and_does_not_mutate_the_event() -> None:
    redactor = LogRedactor()
    event = {
        "request": {
            "headers": {"Cookie": "session=secret", "Accept": "application/json"},
            "items": [{"api_key": "provider-secret", "task_id": "task-1"}],
        }
    }

    cleaned = redactor.clean(event)

    assert cleaned == {
        "request": {
            "headers": {"Cookie": "[REDACTED]", "Accept": "application/json"},
            "items": [{"api_key": "[REDACTED]", "task_id": "task-1"}],
        }
    }
    assert event["request"]["headers"]["Cookie"] == "session=secret"


def test_common_secret_header_aliases_are_redacted() -> None:
    cleaned = LogRedactor().clean(
        {
            "access_token": "access-secret",
            "X-API-Key": "api-secret",
            "Set-Cookie": "session=secret",
        }
    )

    assert cleaned == {
        "access_token": "[REDACTED]",
        "X-API-Key": "[REDACTED]",
        "Set-Cookie": "[REDACTED]",
    }


def test_embedded_bearer_and_url_credentials_are_redacted() -> None:
    redactor = LogRedactor()

    cleaned = redactor.clean(
        {
            "message": "request failed with Authorization: Bearer abc.def-123",
            "endpoint": "https://user:password@example.test/path?token=secret&safe=yes",
        }
    )

    assert "abc.def-123" not in cleaned["message"]
    assert "password" not in cleaned["endpoint"]
    assert "token=secret" not in cleaned["endpoint"]
    assert "safe=yes" in cleaned["endpoint"]


def test_structured_formatter_redacts_context_and_exception_text() -> None:
    formatter = StructuredJsonFormatter(service_name="creditops-api")
    record = logging.LogRecord(
        name="creditops.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="provider failed for Bearer provider-token",
        args=(),
        exc_info=None,
    )
    record.context = {"request_id": "req-1", "signed_url": "https://secret"}

    payload = json.loads(formatter.format(record))

    assert payload["service"] == "creditops-api"
    assert payload["severity"] == "ERROR"
    assert payload["request_id"] == "req-1"
    assert payload["signed_url"] == "[REDACTED]"
    assert "provider-token" not in payload["message"]


def test_structured_context_cannot_replace_log_envelope() -> None:
    formatter = StructuredJsonFormatter(service_name="creditops-api")
    record = logging.LogRecord(
        name="creditops.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="expected message",
        args=(),
        exc_info=None,
    )
    record.context = {
        "service": "attacker-service",
        "severity": "INFO",
        "message": "forged message",
    }

    payload = json.loads(formatter.format(record))

    assert payload["service"] == "creditops-api"
    assert payload["severity"] == "WARNING"
    assert payload["message"] == "expected message"


def test_security_headers_are_fail_closed() -> None:
    response = apply_security_headers(Response())

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
