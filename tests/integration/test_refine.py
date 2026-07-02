"""Integration tests for mode='judge'/'fast' on /detect and /pseudonymise.

Tests use the refined_client fixture which has a TestModel refiner injected.
TestModel returns empty lists (no FPs, no FNs), so the detection result is
unchanged — but the mode='judge' refiner path runs end-to-end without error.
"""

from httpx import AsyncClient

# ── /detect with mode ────────────────────────────────────────────────────────


async def test_detect_refine_true_runs_without_error(refined_client: AsyncClient) -> None:
    resp = await refined_client.post("/detect", json={"text": "Jane Smith jane@example.com", "mode": "judge"})
    assert resp.status_code == 200
    assert "entities" in resp.json()["data"]
    assert resp.json()["data"]["judge_applied"] is True


async def test_detect_refine_false_skips_refiner(refined_client: AsyncClient) -> None:
    """refine=false must work even when refiner is configured."""
    resp = await refined_client.post("/detect", json={"text": "Jane Smith", "mode": "fast"})
    assert resp.status_code == 200
    assert resp.json()["data"]["judge_applied"] is False


async def test_detect_no_refiner_refine_true_silently_skips(detect_client: AsyncClient) -> None:
    """When no refiner is configured, mode="judge" is silently ignored."""
    resp = await detect_client.post("/detect", json={"text": "Jane Smith jane@example.com", "mode": "judge"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]["entities"]) > 0
    assert resp.json()["data"]["judge_applied"] is False


async def test_detect_mode_defaults_to_judge(detect_client: AsyncClient) -> None:
    """Omitting mode should default to 'judge' (silently skipped without refiner)."""
    resp = await detect_client.post("/detect", json={"text": "jane@example.com"})
    assert resp.status_code == 200


# ── /pseudonymise with mode ───────────────────────────────────────────────────


async def test_pseudonymise_refine_true_runs_without_error(refined_client: AsyncClient) -> None:
    resp = await refined_client.post("/pseudonymise", json={"text": "Jane Smith TFN 123 456 782", "mode": "judge"})
    assert resp.status_code == 200
    assert "anonymised_text" in resp.json()["data"]
    assert resp.json()["data"]["judge_applied"] is True


async def test_pseudonymise_refine_false_skips_refiner(refined_client: AsyncClient) -> None:
    resp = await refined_client.post("/pseudonymise", json={"text": "Jane Smith", "mode": "fast"})
    assert resp.status_code == 200
    assert resp.json()["data"]["judge_applied"] is False


async def test_pseudonymise_no_refiner_refine_true_silently_skips(pseudonymise_client: AsyncClient) -> None:
    resp = await pseudonymise_client.post("/pseudonymise", json={"text": "jane@example.com", "mode": "judge"})
    assert resp.status_code == 200
    assert "jane@example.com" not in resp.json()["data"]["anonymised_text"]
    assert resp.json()["data"]["judge_applied"] is False
