from models.stored_event import StoredEvent
from models.submission import TalkSubmission
from services.ai_assessment import (
    BADGE_HIGH_INNOVATION,
    BADGE_MODERATE_NOVELTY,
    BADGE_REDUNDANT,
    dedupe_overlap_talks,
    innovation_badge,
    innovation_score_from_overlap,
    recommend_status,
    score_rationale,
)
from services.deep_agent import assess_pending_talks


def _register_speaker(client, user_id="spk-assess", name="Ada Lovelace"):
    return client.post(
        "/register",
        json={
            "user_id": user_id,
            "password": "SecurePass1",
            "role": "speaker",
            "name": name,
        },
    )


def _login_speaker(client, user_id="spk-assess"):
    return client.post("/speaker/login", json={"user_id": user_id, "password": "SecurePass1"})


def _login_admin(client):
    return client.post("/login", json={"user_id": "admin", "password": "AdminPass!2026"})


def _submit_talk(client, **overrides):
    payload = {
        "title": "Event sourcing for conference programs",
        "abstract": (
            "A practical walkthrough of commands, queries, and event sourcing for "
            "talk proposals, including how organizers review AI assessments."
        ),
        "category": "architecture",
        "date": "2026-11-18",
        "start_time": "10:00",
        "end_time": "11:00",
        "capacity": 100,
    }
    payload.update(overrides)
    return client.post("/api/submit", json=payload)


def test_dedupe_overlap_talks_keeps_highest_score():
    cleaned = dedupe_overlap_talks(
        [
            {"id": "evt-1", "title": "Confirmed Lecture After Accept", "overlap": 0.28},
            {"id": "sub-1", "title": "Confirmed Lecture After Accept", "overlap": 0.35},
            {"id": "sub-2", "title": "  confirmed lecture after accept ", "score": 0.22},
            {"id": "sub-3", "title": "Table Layout Submission", "overlap": 0.43},
        ]
    )
    titles = [item["title"] for item in cleaned]
    assert titles == ["Confirmed Lecture After Accept", "Table Layout Submission"]
    assert cleaned[0]["overlap"] == 0.35
    assert cleaned[0]["id"] == "sub-1"


def test_organizer_payload_strips_duplicate_overlap_names(client, app):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client).get_json()
    from extensions import db

    submission = db.session.get(TalkSubmission, created["id"])
    assessment = dict(submission.ai_assessment or {})
    assessment["overlapping_talks"] = [
        {"id": "a", "title": "123", "overlap": 0.28},
        {"id": "b", "title": "123", "overlap": 0.28},
        {"id": "c", "title": "test221", "overlap": 0.31},
    ]
    assessment["similar_talks"] = assessment["overlapping_talks"]
    submission.ai_assessment = assessment
    db.session.add(submission)
    db.session.commit()

    payload = db.session.get(TalkSubmission, created["id"]).to_dict()
    names = [item["title"] for item in payload["ai_assessment"]["overlapping_talks"]]
    assert names == ["123", "test221"]


def test_score_rationale_mentions_overlap():
    text = score_rationale(
        6,
        BADGE_REDUNDANT,
        [{"title": "Kelp Forest Acoustics for Live Stages", "overlap": 1.0}],
    )
    assert "Low novelty" in text
    assert "Kelp Forest Acoustics for Live Stages" in text
    assert "100%" in text


def test_innovation_thresholds():
    assert innovation_score_from_overlap(0.0, 0, 0) >= 85
    assert innovation_badge(innovation_score_from_overlap(0.05, 0, 1)) == BADGE_HIGH_INNOVATION
    assert 51 <= innovation_score_from_overlap(0.30, 0, 1) <= 84
    assert innovation_badge(innovation_score_from_overlap(0.30, 0, 1)) == BADGE_MODERATE_NOVELTY
    assert innovation_score_from_overlap(0.72, 2, 3) <= 50
    assert innovation_badge(innovation_score_from_overlap(0.72, 2, 3)) == BADGE_REDUNDANT
    assert recommend_status(90) == BADGE_HIGH_INNOVATION
    assert recommend_status(60) == BADGE_MODERATE_NOVELTY
    assert recommend_status(40) == BADGE_REDUNDANT


def test_submit_persists_innovation_assessment(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client).get_json()

    assessment = created["ai_assessment"]
    assert created["status"] == "under_review"
    assert created["innovation_score"] == assessment["innovation_score"]
    assert created["innovation_badge"] == assessment["innovation_badge"]
    assert assessment["queued_for_background_agent"] is True
    assert assessment["agent_status"] == "complete"
    assert assessment["innovation_badge"] in {
        BADGE_HIGH_INNOVATION,
        BADGE_MODERATE_NOVELTY,
        BADGE_REDUNDANT,
    }
    assert 0 <= assessment["innovation_score"] <= 100
    assert assessment["innovation_score"] == assessment["quality_score"]
    assert 20 <= assessment["confidence_score"] <= 98
    assert assessment["hooks"]["vector_rag"]["enabled"] is True
    assert "uniqueness_summary" in assessment
    assert StoredEvent.query.filter_by(event_name="TalkInnovationReviewed").count() >= 1


def test_first_talk_is_high_innovation(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(
        client,
        title="Quantum fermentation for pastry chefs",
        abstract="A kitchen science talk about using quantum sensors to time laminated dough.",
        category="food",
    ).get_json()
    assert created["innovation_score"] >= 85
    assert created["innovation_badge"] == BADGE_HIGH_INNOVATION
    assert "fresh" in created["ai_assessment"]["uniqueness_summary"].lower() or "unique" in created["ai_assessment"]["uniqueness_summary"].lower()


def test_duplicate_talk_is_flagged_redundant(client):
    _register_speaker(client)
    _login_speaker(client)
    original = _submit_talk(
        client,
        title="Building CQRS with Flask",
        abstract="A practical walkthrough of commands, queries, and event sourcing for conference systems.",
    ).get_json()
    duplicate = _submit_talk(
        client,
        title="Building CQRS with Flask",
        abstract="A practical walkthrough of commands, queries, and event sourcing for conference systems.",
        date="2026-11-19",
        start_time="15:00",
        end_time="16:00",
    ).get_json()

    assert original["innovation_badge"] == BADGE_HIGH_INNOVATION
    assert duplicate["innovation_score"] <= 50
    assert duplicate["innovation_badge"] == BADGE_REDUNDANT
    overlaps = duplicate["ai_assessment"]["overlapping_talks"]
    assert any(hit["id"] == original["id"] or hit["title"] == original["title"] for hit in overlaps)
    assert "overlap" in duplicate["ai_assessment"]["uniqueness_summary"].lower()


def test_organizer_proposals_include_innovation_fields(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client).get_json()
    client.post("/logout")
    _login_admin(client)

    pending = client.get("/api/organizer/proposals")
    assert pending.status_code == 200
    match = next(item for item in pending.get_json() if item["id"] == created["id"])
    assert match["innovation_score"] == created["innovation_score"]
    assert match["innovation_badge"] == created["innovation_badge"]
    assert match["ai_assessment"]["uniqueness_summary"]


def test_background_scan_assesses_pending_submission(client, app):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client).get_json()
    from extensions import db

    submission = db.session.get(TalkSubmission, created["id"])
    submission.status = "pending_assessment"
    submission.ai_assessment = {}
    db.session.add(submission)
    db.session.commit()

    with app.app_context():
        assessed = assess_pending_talks(force=True)
    assert any(item["id"] == created["id"] for item in assessed)
    refreshed = db.session.get(TalkSubmission, created["id"])
    assert refreshed.status == "under_review"
    assert refreshed.ai_assessment["innovation_badge"]
    assert refreshed.ai_assessment["innovation_score"] >= 0


def test_organizer_can_rerun_assessment(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client).get_json()
    client.post("/logout")
    _login_admin(client)

    response = client.post(f"/api/organizer/proposals/{created['id']}/assess")
    assert response.status_code == 200
    body = response.get_json()
    assert body["innovation_badge"]
    assert body["innovation_score"] >= 0
