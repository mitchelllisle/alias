"""Integration tests for POST /judge and POST /judge/stream.

The judge requires an LLM — in tests we use pydantic-ai's TestModel so no
real API calls are made and results are deterministic.
"""

from httpx import AsyncClient


async def _detect(client: AsyncClient, text: str) -> dict:  # type: ignore[type-arg]
    resp = await client.post("/detect", json={"text": text})
    assert resp.status_code == 200
    return resp.json()


# ── POST /judge ───────────────────────────────────────────────────────────────

async def test_judge_returns_200(judge_client: AsyncClient) -> None:
    detections = await _detect(judge_client, "Contact jane@example.com")
    resp = await judge_client.post(
        "/judge",
        json={"text": "Contact jane@example.com", "detections": detections},
    )
    assert resp.status_code == 200


async def test_judge_response_shape(judge_client: AsyncClient) -> None:
    text = "Jane Smith TFN 123 456 782"
    detections = await _detect(judge_client, text)
    resp = await judge_client.post("/judge", json={"text": text, "detections": detections})
    assert resp.status_code == 200
    body = resp.json()
    assert "adjusted" in body
    assert "removed" in body
    assert "added" in body
    assert "reasoning" in body
    assert isinstance(body["removed"], list)
    assert isinstance(body["added"], list)


async def test_judge_with_context(judge_client: AsyncClient) -> None:
    text = "Account BSB 062-000"
    detections = await _detect(judge_client, text)
    resp = await judge_client.post(
        "/judge",
        json={
            "text": text,
            "detections": detections,
            "context": "Australian retail banking document",
        },
    )
    assert resp.status_code == 200


async def test_judge_not_configured_returns_503(anonymise_client: AsyncClient) -> None:
    """Client without judge injected — app.state.judge is None — expect 503."""
    text = "Contact jane@example.com"
    detections = await _detect(anonymise_client, text)
    resp = await anonymise_client.post(
        "/judge",
        json={"text": text, "detections": detections},
    )
    assert resp.status_code == 503
    assert "ALIAS_JUDGE_MODEL" in resp.json()["detail"]


async def test_judge_empty_text_returns_422(judge_client: AsyncClient) -> None:
    resp = await judge_client.post(
        "/judge",
        json={"text": "", "detections": {"entities": [], "input_hash": "abc", "language": "en"}},
    )
    assert resp.status_code == 422


# ── POST /judge/stream ────────────────────────────────────────────────────────

async def test_judge_stream_returns_sse(judge_client: AsyncClient) -> None:
    text = "Contact jane@example.com"
    detections = await _detect(judge_client, text)
    resp = await judge_client.post(
        "/judge/stream",
        json={"text": text, "detections": detections},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]


async def test_judge_stream_contains_events(judge_client: AsyncClient) -> None:
    text = "TFN is 123 456 782"
    detections = await _detect(judge_client, text)
    resp = await judge_client.post(
        "/judge/stream",
        json={"text": text, "detections": detections},
    )
    content = resp.text
    assert "event: reasoning_chunk" in content
    assert "event: result" in content


async def test_judge_stream_result_event_is_valid_json(judge_client: AsyncClient) -> None:
    import json

    text = "Email alice@corp.com or call 0412 345 678"
    detections = await _detect(judge_client, text)
    resp = await judge_client.post(
        "/judge/stream",
        json={"text": text, "detections": detections},
    )
    # Extract the data line after "event: result"
    lines = resp.text.splitlines()
    result_data: str | None = None
    for i, line in enumerate(lines):
        if line == "event: result" and i + 1 < len(lines):
            result_data = lines[i + 1].removeprefix("data: ")
            break
    assert result_data is not None
    body = json.loads(result_data)
    assert "adjusted" in body
    assert "reasoning" in body
