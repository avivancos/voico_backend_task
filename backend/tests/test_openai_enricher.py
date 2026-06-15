"""Tests for the OpenAI-backed enricher — real ``OpenAIEnricher`` code against a **recorded**
``chat.completions`` response, replayed at the HTTP boundary via ``httpx.MockTransport``.

This is the Python analogue of the frontend's MSW network-boundary mocking: we never monkeypatch the
OpenAI SDK or our own code — we inject a real ``AsyncOpenAI`` whose transport returns a captured
response. So every line of ``OpenAIEnricher`` (request build, content parse, summary truncation,
label coercion) runs for real; only the network egress is stubbed with a recorded fixture.
"""

import json
from pathlib import Path

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st
from openai import AsyncOpenAI

from app.core.config import settings
from app.modules.calls.enrichment import (
    Enrichment,
    OpenAIEnricher,
    _coerce_label,
    build_default_enricher,
)
from app.modules.calls.schema import CallLabel

pytestmark = pytest.mark.integration

_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "openai_chat_completion.json").read_text()
)


def _client(*, content: str | None = "__fixture__", status_code: int = 200) -> AsyncOpenAI:
    """An AsyncOpenAI wired to a MockTransport that replays the recorded envelope.

    ``content`` overrides ``choices[0].message.content`` to simulate different model outputs; the
    sentinel keeps the fixture's content. ``status_code != 200`` simulates an API error.
    """
    envelope = json.loads(json.dumps(_FIXTURE))  # deep copy per call
    if content != "__fixture__":
        envelope["choices"][0]["message"]["content"] = content

    def handler(request: httpx.Request) -> httpx.Response:
        if status_code != 200:
            return httpx.Response(status_code, json={"error": {"message": "boom"}})
        return httpx.Response(200, json=envelope)

    transport = httpx.MockTransport(handler)
    return AsyncOpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=transport),
    )


async def test_enriches_from_recorded_response():
    enricher = OpenAIEnricher(_client())
    out = await enricher.enrich("Agent: How can I help?\nCaller: I'd like to upgrade my plan.")

    assert isinstance(out, Enrichment)
    assert out.label == CallLabel.sales_inquiry
    assert out.summary.startswith("The caller asked to upgrade")


async def test_out_of_enum_label_is_coerced_to_other():
    # Even if the model returns a label outside the enum, we never store a non-enum value.
    enricher = OpenAIEnricher(_client(content='{"summary": "x", "label": "NUCLEAR_LAUNCH"}'))
    out = await enricher.enrich("anything")
    assert out.label == CallLabel.other


async def test_summary_is_truncated_to_the_cap():
    long_summary = "S" * 5000
    enricher = OpenAIEnricher(
        _client(content=json.dumps({"summary": long_summary, "label": "Support"}))
    )
    out = await enricher.enrich("anything")
    assert len(out.summary) == 600
    assert out.label == CallLabel.support


async def test_malformed_json_content_raises():
    enricher = OpenAIEnricher(_client(content="this is not json {"))
    with pytest.raises(Exception):
        await enricher.enrich("anything")


async def test_empty_content_raises():
    enricher = OpenAIEnricher(_client(content=""))
    with pytest.raises(ValueError):
        await enricher.enrich("anything")


async def test_null_content_raises():
    enricher = OpenAIEnricher(_client(content=None))
    with pytest.raises(ValueError):
        await enricher.enrich("anything")


async def test_api_error_propagates():
    # A 5xx from the API surfaces as an exception; the *service* layer is what swallows it to null.
    enricher = OpenAIEnricher(_client(status_code=500))
    with pytest.raises(Exception):
        await enricher.enrich("anything")


# --- _coerce_label: total, never raises -----------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        (CallLabel.support, CallLabel.support),  # already an enum member
        ("Sales inquiry", CallLabel.sales_inquiry),  # exact value
        ("sales_inquiry", CallLabel.sales_inquiry),  # member name
        ("SALES INQUIRY", CallLabel.sales_inquiry),  # case-insensitive value
        ("  Support  ", CallLabel.support),  # surrounding whitespace
        ("definitely not a label", CallLabel.other),  # unknown -> other
        (None, CallLabel.other),  # non-string -> other
        (12345, CallLabel.other),  # non-string -> other
    ],
)
def test_coerce_label_cases(raw, expected):
    assert _coerce_label(raw) == expected


@given(st.text())
def test_coerce_label_is_total_over_any_text(s):
    # Property: whatever hostile string the model emits, we always return a valid enum member.
    assert _coerce_label(s) in set(CallLabel)


# --- build_default_enricher: wiring from settings -------------------------------------------


def test_build_default_enricher_is_none_without_api_key():
    # Tests run on pure defaults (ENV_FILE="" -> openai_api_key == "").
    assert settings.openai_api_key == ""
    assert build_default_enricher() is None


def test_build_default_enricher_with_api_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-123")
    enricher = build_default_enricher()
    assert isinstance(enricher, OpenAIEnricher)


def test_build_default_enricher_bounds_latency(monkeypatch):
    # The webhook enriches in-request, so the OpenAI client MUST carry a finite timeout and limited
    # retries — otherwise a hung call stalls the request up to the SDK default (600s).
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-123")
    client = build_default_enricher()._client
    assert client.timeout == settings.openai_timeout_seconds
    assert client.max_retries == settings.openai_max_retries
