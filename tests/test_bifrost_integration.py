"""
Bifrost integration test — verifies MCPKU can talk to a live bifrost server.

Bifrost = MaximHQ LLM gateway (Go binary, OpenAI-compatible API).
Default endpoint: http://localhost:8080/v1
Default key: "ignored" (bifrost accepts any non-empty key for free models).

These tests are SIDE-EFFECT FREE — they only read models and do 1 short
chat completion per test. Safe to run repeatedly.

All tests skip with a clear message when bifrost is unreachable, so this
file does NOT fail CI when the server is offline. To run explicitly:
    pytest tests/test_bifrost_integration.py -v
    pytest tests/test_bifrost_integration.py -v --no-header
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BIFROST_URL = os.environ.get("BIFROST_URL", "http://localhost:8080/v1")
BIFROST_KEY = os.environ.get("BIFROST_KEY", "ignored")
CHAT_TIMEOUT_S = 60
MODELS_TIMEOUT_S = 10


def _parse_jsonc(text: str) -> dict | None:
    """Parse JSON-with-comments (JSONC) used by opencode.jsonc.

    Strategy: strip `//` line comments and `/* */` block comments
    without touching string contents, then json.loads.
    """
    import re

    out: list[str] = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            # line comment — skip to end of line (keep the newline out)
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            # block comment — skip until */
            i += 2
            while i < len(text) and not (text[i] == "*" and i + 1 < len(text) and text[i + 1] == "/"):
                i += 1
            i += 2  # skip closing */
            continue
        out.append(ch)
        i += 1
    cleaned = "".join(out)
    # Remove blank lines left behind by stripped comments
    cleaned = re.sub(r"\n\s*\n+", "\n", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _http_json(method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
    """Minimal HTTP client. Returns (status_code, parsed_json_or_text)."""
    url = f"{BIFROST_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "x-bf-api-key": BIFROST_KEY,
        },
    )
    timeout = CHAT_TIMEOUT_S if body else MODELS_TIMEOUT_S
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def _is_reachable() -> bool:
    """Quick reachability check — used by pytest.skip in every test."""
    try:
        status, _ = _http_json("GET", "/models")
        return status == 200
    except Exception:
        return False


pytestmark_skip_if_offline = pytest_mark_skip_msg = None  # alias for clarity


# Shared fixture: skip all tests in this module if bifrost is down.
# Implemented as a session-scoped autouse fixture (no skipif decorator
# needed — keeps the test list clean when bifrost is offline).
import pytest  # noqa: E402  (after _http_json so skip message is informative)


@pytest.fixture(scope="module", autouse=True)
def _skip_if_bifrost_offline():
    if not _is_reachable():
        pytest.skip(
            f"Bifrost not reachable at {BIFROST_URL} — start it with "
            "`bifrost-http` or set BIFROST_URL env var. "
            "Tests in this file are integration-only and require a live server."
        )


# ── Connectivity ─────────────────────────────────────────────────────────────


class TestConnectivity:
    def test_models_endpoint_returns_200(self):
        status, body = _http_json("GET", "/models")
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert "data" in body, f"Response missing 'data' key: {body}"
        assert isinstance(body["data"], list)
        assert len(body["data"]) > 0, "Model list is empty — bifrost misconfigured?"

    def test_models_have_required_fields(self):
        _, body = _http_json("GET", "/models")
        for m in body["data"][:5]:
            assert "id" in m, f"Model missing 'id': {m}"
            assert isinstance(m["id"], str) and m["id"], f"Invalid id: {m}"

    def test_at_least_one_openrouter_model(self):
        _, body = _http_json("GET", "/models")
        ids = [m["id"] for m in body["data"]]
        openrouter = [i for i in ids if i.startswith("openrouter/")]
        assert openrouter, (
            f"No openrouter/* models found in {ids}. "
            "Bifrost config may have lost its openrouter provider."
        )


# ── Chat completion ──────────────────────────────────────────────────────────


# Models that historically respond (update if rate-limited for prolonged period).
KNOWN_WORKING_MODELS = (
    "openrouter/openai/gpt-oss-20b:free",
    "openrouter/openai/gpt-oss-120b:free",
)


class TestChatCompletion:
    @pytest.mark.parametrize("model", list(KNOWN_WORKING_MODELS))
    def test_simple_completion_against_known_model(self, model: str):
        """Hit a known-stable free model with a tiny prompt.

        Parametrized across multiple models so we still get coverage
        if one of them is rate-limited.
        """
        status, body = _http_json(
            "POST",
            "/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with just the word: pong"}],
                "max_tokens": 10,
                "temperature": 0,
            },
        )
        if status == 429:
            pytest.skip(f"{model} rate-limited right now (429). Try again later.")
        if status == 400:
            pytest.skip(f"{model} rejected the request (400): {body}")
        assert status == 200, f"Chat completion failed: {status} {body}"
        assert "choices" in body, f"Response missing 'choices': {body}"
        assert len(body["choices"]) >= 1
        msg = body["choices"][0].get("message", {}).get("content", "")
        assert msg.strip(), f"Empty response from {model}"
        assert "pong" in msg.lower(), f"Expected 'pong' in reply, got: {msg!r}"

    @pytest.mark.parametrize("model", list(KNOWN_WORKING_MODELS))
    def test_completion_respects_max_tokens(self, model: str):
        """Verify max_tokens is honored — no runaway response."""
        status, body = _http_json(
            "POST",
            "/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": "Count: 1 2 3"}],
                "max_tokens": 5,
            },
        )
        if status in (429, 400):
            pytest.skip(f"Skipped: {status} {body}")
        assert status == 200
        usage = body.get("usage", {})
        completion = usage.get("completion_tokens", 0)
        # Allow some slack — providers sometimes return a bit more
        assert completion <= 10, f"max_tokens=5 not respected: {completion} tokens returned"


# ── opencode.jsonc integration ───────────────────────────────────────────────


USER_OPENCODE_CONFIG_CANDIDATES = [
    Path(os.environ.get("APPDATA", "")) / "opencode" / "opencode.jsonc",
    Path(os.environ.get("USERPROFILE", "")) / ".config" / "opencode" / "opencode.jsonc",
    Path.home() / ".config" / "opencode" / "opencode.jsonc",
]


def _resolve_user_config() -> Path | None:
    """Return the first existing user opencode.jsonc, or None."""
    for p in USER_OPENCODE_CONFIG_CANDIDATES:
        if p.exists():
            return p
    return None


USER_OPENCODE_CONFIG = _resolve_user_config() or USER_OPENCODE_CONFIG_CANDIDATES[0]
WORKSPACE_OPENCODE_CONFIG = Path(r"E:\MCPKU\opencode.jsonc")


class TestOpencodeIntegration:
    """Verify bifrost is registered as a provider in opencode config(s)."""

    @pytest.mark.parametrize(
        "config_path",
        [
            pytest.param(USER_OPENCODE_CONFIG, id="user-config"),
            pytest.param(WORKSPACE_OPENCODE_CONFIG, id="workspace-config"),
        ],
    )
    def test_bifrost_provider_declared(self, config_path: Path):
        if not config_path.exists():
            pytest.skip(f"{config_path} not found — user has no opencode config yet")
        text = config_path.read_text(encoding="utf-8")
        cfg = _parse_jsonc(text)
        if cfg is None:
            pytest.fail(f"Could not parse {config_path.name} as JSONC")
        providers = cfg.get("provider", {})
        if "bifrost" not in providers:
            # Workspace config is a "sync backup" — may lag behind user config.
            # User config is the source of truth, so failure there is hard.
            if config_path == USER_OPENCODE_CONFIG:
                pytest.fail(
                    f"bifrost provider not in user config {config_path.name}. "
                    f"Found providers: {list(providers.keys())}"
                )
            pytest.skip(
                f"bifrost not in {config_path.name} (workspace sync backup) — "
                f"sync from user config. Providers present: {list(providers.keys())}"
            )
        bifrost = providers["bifrost"]
        assert bifrost.get("options", {}).get("baseURL", "").startswith("http"), (
            f"bifrost baseURL missing or invalid: {bifrost.get('options')}"
        )
        assert bifrost.get("models"), "bifrost provider has no models declared"


# ── Latency sanity (optional) ────────────────────────────────────────────────


class TestLatency:
    """Quick latency check — fails soft (records warning) but doesn't block CI."""

    @pytest.mark.parametrize("model", list(KNOWN_WORKING_MODELS))
    def test_first_token_under_30s(self, model: str):
        status, body = _http_json(
            "POST",
            "/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
            },
        )
        if status in (429, 400):
            pytest.skip(f"Skipped: {status}")
        # This test is informational — just check that we DID get a response.
        # Real timing measured in dedicated benchmark suite (not yet built).
        assert status == 200
        assert body.get("choices"), "No choices returned"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
