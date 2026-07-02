"""API contract tests + one end-to-end path (RFC-0001 §8)."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_extract_creates_draft_with_computed_level(client):
    resp = client.post(
        "/internal/extract",
        json={
            "text": "A 2021 meta-analysis found creatine improves strength by 8%.",
            "subject": "creatine",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    # meta-analysis -> high, and level is set by the engine, not the caller.
    assert body["evidence_level"] == "high"
    assert body["verified_by"] is None
    assert len(body["sources"]) >= 1


def test_get_missing_claim_returns_404(client):
    resp = client.get("/claims/not-a-real-id")
    assert resp.status_code == 404


def test_end_to_end_extract_verify_ask(client):
    # 1. Extract a draft Claim from raw text.
    draft = client.post(
        "/internal/extract",
        json={
            "text": "A 2021 meta-analysis found creatine improves strength by 8%.",
            "subject": "creatine",
        },
    ).json()
    claim_id = draft["id"]

    # 2. It is a draft and not yet visible as published.
    listed = client.get("/claims", params={"subject": "creatine", "status": "draft"})
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    # 3. Autonomous LLM-ensemble verification (RFC-0002) -> published.
    verified = client.post(f"/claims/{claim_id}/verify")
    assert verified.status_code == 200
    body = verified.json()
    assert body["status"] == "published"
    assert body["verified_by"] == "llm:ensemble"
    assert body["verification"] is not None
    assert body["verification"]["decision_status"] == "auto_verified"

    # 4. Published Claim is now answerable via /ask, with sources attached.
    answer = client.get("/ask", params={"q": "creatine"})
    assert answer.status_code == 200
    payload = answer.json()
    assert len(payload["claims"]) == 1
    assert payload["claims"][0]["id"] == claim_id
    assert "creatine" in payload["answer"].lower()

    # 5. Summary reflects one published Claim.
    summary = client.get("/substances/creatine/summary")
    assert summary.status_code == 200
    assert summary.json()["published_claims"] == 1


def test_verification_holds_when_source_unrelated(client):
    # Subject not present in the source text -> ensemble holds, not published.
    draft = client.post(
        "/internal/extract",
        json={
            "text": "A meta-analysis found iron supplementation improved hemoglobin.",
            "subject": "creatine",
        },
    ).json()
    verified = client.post(f"/claims/{draft['id']}/verify").json()
    assert verified["status"] == "held"

    # Held claims never appear in /ask.
    answer = client.get("/ask", params={"q": "creatine"}).json()
    assert answer["claims"] == []


def test_ask_with_no_match_is_honest(client):
    resp = client.get("/ask", params={"q": "nonexistent-substance-xyz"})
    assert resp.status_code == 200
    assert resp.json()["claims"] == []
