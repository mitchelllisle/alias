"""Integration tests for AU recognisers via POST /detect.

Uses detect_client (real engine with en_core_web_sm + AU recognisers).
Validates that AU-specific entity types are detected and classified correctly.
"""

from httpx import AsyncClient


async def test_tfn_detected_with_context(detect_client: AsyncClient) -> None:
    resp = await detect_client.post(
        "/detect", json={"text": "Customer TFN is 123 456 782 for the tax return."}
    )
    assert resp.status_code == 200
    types = {e["entity_type"] for e in resp.json()["entities"]}
    assert "AU_TFN" in types


async def test_tfn_is_critical_pii(detect_client: AsyncClient) -> None:
    resp = await detect_client.post(
        "/detect", json={"text": "TFN 123 456 782"}
    )
    tfns = [e for e in resp.json()["entities"] if e["entity_type"] == "AU_TFN"]
    assert len(tfns) > 0
    assert all(e["sensitivity"] == "critical" for e in tfns)
    assert all(e["is_pii"] for e in tfns)


async def test_invalid_tfn_not_detected(detect_client: AsyncClient) -> None:
    # 123 456 789 fails the TFN checksum — should not appear as AU_TFN
    resp = await detect_client.post(
        "/detect", json={"text": "TFN 123 456 789"}
    )
    types = {e["entity_type"] for e in resp.json()["entities"]}
    assert "AU_TFN" not in types


async def test_abn_detected_with_context(detect_client: AsyncClient) -> None:
    resp = await detect_client.post(
        "/detect", json={"text": "ABN 51 824 753 556 is the business number."}
    )
    types = {e["entity_type"] for e in resp.json()["entities"]}
    assert "AU_ABN" in types


async def test_abn_is_not_pii(detect_client: AsyncClient) -> None:
    resp = await detect_client.post(
        "/detect", json={"text": "ABN 51 824 753 556"}
    )
    abns = [e for e in resp.json()["entities"] if e["entity_type"] == "AU_ABN"]
    assert all(not e["is_pii"] for e in abns)


async def test_bsb_detected_with_context(detect_client: AsyncClient) -> None:
    resp = await detect_client.post(
        "/detect", json={"text": "Please use BSB 062-000 for the transfer."}
    )
    types = {e["entity_type"] for e in resp.json()["entities"]}
    assert "AU_BSB" in types


async def test_bsb_is_high_sensitivity(detect_client: AsyncClient) -> None:
    resp = await detect_client.post(
        "/detect", json={"text": "BSB 062-000 account"}
    )
    bsbs = [e for e in resp.json()["entities"] if e["entity_type"] == "AU_BSB"]
    assert all(e["sensitivity"] == "high" for e in bsbs)


async def test_clean_financial_text_no_au_pii(detect_client: AsyncClient) -> None:
    resp = await detect_client.post(
        "/detect",
        json={"text": "The variable rate is 6.49% p.a. Minimum repayment $1,200/month."},
    )
    au_critical = [
        e for e in resp.json()["entities"]
        if e["entity_type"] in {"AU_TFN", "AU_MEDICARE"} or e["sensitivity"] == "critical"
    ]
    assert len(au_critical) == 0
