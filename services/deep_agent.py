from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from models.submission import PENDING_STATUSES, TalkSubmission
from services.ai_assessment import AIAssessmentAgent

logger = logging.getLogger(__name__)

_worker_started = False
_worker_lock = threading.Lock()


def needs_assessment(submission: TalkSubmission, force: bool = False) -> bool:
    if submission.status not in PENDING_STATUSES:
        return False
    if force:
        return True
    assessment = submission.ai_assessment or {}
    if not isinstance(assessment, dict):
        return True
    if (
        assessment.get("agent_status") == "complete"
        and assessment.get("innovation_score") is not None
        and assessment.get("innovation_badge")
    ):
        web = assessment.get("web_check") or {}
        if web.get("enabled") or web.get("verified"):
            return False
        try:
            from services.tavily import tavily_api_key

            if tavily_api_key():
                return True
        except Exception:
            return False
        return False
    return True


def persist_assessment(submission: TalkSubmission, assessment: dict[str, Any], store=None) -> TalkSubmission:
    submission.ai_assessment = assessment
    if submission.status == "pending_assessment":
        submission.status = "under_review"
    flag_modified(submission, "ai_assessment")
    if store is None:
        from cqrs.store import EventStore

        store = EventStore()
    store.append("TalkInnovationReviewed", submission.to_dict())
    store.save_submission(submission)
    return submission


def assess_submission(
    submission: TalkSubmission,
    assessor: AIAssessmentAgent | None = None,
    store=None,
    force: bool = False,
) -> dict[str, Any] | None:
    if submission is None or not needs_assessment(submission, force=force):
        return submission.ai_assessment if submission is not None else None
    agent = assessor or AIAssessmentAgent()
    assessment = agent.enqueue(submission)
    persist_assessment(submission, assessment, store=store)
    return assessment


def assess_pending_talks(
    submission_id: str | None = None,
    force: bool = False,
    assessor: AIAssessmentAgent | None = None,
    store=None,
) -> list[dict[str, Any]]:
    """Scan pending proposals and persist Deep Agent evaluations."""
    if store is None:
        from cqrs.store import EventStore

        store = EventStore()
    agent = assessor or AIAssessmentAgent()
    if submission_id:
        submission = store.get_submission(str(submission_id).strip())
        rows = [submission] if submission is not None else []
    else:
        rows = store.list_submissions_for_assessment()

    assessed: list[dict[str, Any]] = []
    for submission in rows:
        if submission is None:
            continue
        result = assess_submission(submission, assessor=agent, store=store, force=force)
        if result is not None:
            assessed.append(
                {
                    "id": submission.id,
                    "title": submission.title,
                    "status": submission.status,
                    "ai_assessment": submission.ai_assessment or {},
                }
            )
    return assessed


def start_assessment_agent(app) -> None:
    """Start a daemon thread that periodically scans pending talk proposals."""
    global _worker_started
    if app.config.get("TESTING"):
        return
    if not app.config.get("ASSESSMENT_AGENT_AUTOSTART", True):
        return
    if os.environ.get("WERKZEUG_RUN_MAIN") == "false":
        return
    interval = int(app.config.get("ASSESSMENT_AGENT_INTERVAL", 45))
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    def _loop() -> None:
        while True:
            time.sleep(max(10, interval))
            try:
                with app.app_context():
                    assess_pending_talks()
            except Exception:
                logger.exception("Background AI assessment agent failed")

    thread = threading.Thread(target=_loop, name="deep-assessment-agent", daemon=True)
    thread.start()
    logger.info("Background AI assessment agent started (interval=%ss)", interval)
