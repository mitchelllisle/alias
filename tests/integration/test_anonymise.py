"""Integration tests for POST /anonymise."""

from httpx import AsyncClient


async def test_anonymise_auto_detects_email(anonymise_client: AsyncClient) -> None:
    """Omitting detections triggers auto-detection."""
    resp = await anonymise_client.post(
        "/anonymise", json={"text": "Contact billing@acme.com for invoices"}
    )
    assert resp.status_code == 200
    assert "billing@acme.com" not in resp.json()["anonymised_text"]


async def test_anonymise_with_prior_detections(anonymise_client: AsyncClient) -> None:
    """Passing pre-computed detections skips re-detection."""
    text = "My TFN is 123 456 782"
    detect_resp = await anonymise_client.post("/detect", json={"text": text})
    assert detect_resp.status_code == 200

    anon_resp = await anonymise_client.post(
        "/anonymise", json={"text": text, "detections": detect_resp.json()}
    )
    assert anon_resp.status_code == 200
    body = anon_resp.json()
    assert "123 456 782" not in body["anonymised_text"]
    assert "***-***-***" in body["anonymised_text"]


async def test_anonymise_response_shape(anonymise_client: AsyncClient) -> None:
    resp = await anonymise_client.post(
        "/anonymise", json={"text": "Jane Smith jane@example.com"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "anonymised_text" in body
    assert "entity_map" in body
    assert isinstance(body["entity_map"], dict)


async def test_anonymise_operator_override_redact(anonymise_client: AsyncClient) -> None:
    text = "Contact Alice Smith about the loan"
    detect_resp = await anonymise_client.post("/detect", json={"text": text})
    anon_resp = await anonymise_client.post(
        "/anonymise",
        json={
            "text": text,
            "detections": detect_resp.json(),
            "operator_overrides": {"PERSON": "redact"},
        },
    )
    assert anon_resp.status_code == 200
    assert "Alice Smith" not in anon_resp.json()["anonymised_text"]


async def test_anonymise_clean_text_unchanged(anonymise_client: AsyncClient) -> None:
    text = "Fixed home loan repayments are calculated monthly."
    resp = await anonymise_client.post("/anonymise", json={"text": text})
    assert resp.status_code == 200
    assert "***-***-***" not in resp.json()["anonymised_text"]
    assert "XXX-XXX" not in resp.json()["anonymised_text"]


async def test_anonymise_au_bsb_replaced(anonymise_client: AsyncClient) -> None:
    text = "Please use BSB 062-000 for transfers"
    detect_resp = await anonymise_client.post("/detect", json={"text": text})
    anon_resp = await anonymise_client.post(
        "/anonymise", json={"text": text, "detections": detect_resp.json()}
    )
    assert anon_resp.status_code == 200
    assert "062-000" not in anon_resp.json()["anonymised_text"]
    assert "XXX-XXX" in anon_resp.json()["anonymised_text"]


async def test_anonymise_empty_text_returns_422(anonymise_client: AsyncClient) -> None:
    resp = await anonymise_client.post("/anonymise", json={"text": ""})
    assert resp.status_code == 422
