from flask import Blueprint, jsonify, request

from cqrs import SemanticSearchQuery, semantic_search_handler
from cqrs.errors import DomainError

search_bp = Blueprint("search", __name__, url_prefix="/api")


def _validation_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _search_payload() -> dict:
    body = request.get_json(silent=True) or {}
    query = request.args.get("q") or request.args.get("query") or body.get("query") or body.get("q") or ""
    limit = request.args.get("limit", body.get("limit", 5))
    source = request.args.get("type") or body.get("type") or body.get("source_type") or ""
    source_types = None
    cleaned = str(source).strip().lower()
    if cleaned in {"proposal", "proposals", "talk", "talks"}:
        source_types = ("proposal",)
    elif cleaned in {"speaker", "speakers"}:
        source_types = ("speaker",)
    return {"query": str(query).strip(), "limit": limit, "source_types": source_types}


def run_semantic_search():
    payload = _search_payload()
    try:
        results = semantic_search_handler.handle(
            SemanticSearchQuery(
                query=payload["query"],
                limit=payload["limit"],
                source_types=payload["source_types"],
            )
        )
    except DomainError as exc:
        return _validation_error(exc.message, status=exc.status)
    return jsonify({"query": payload["query"], "count": len(results), "results": results}), 200


@search_bp.route("/search", methods=["GET", "POST"])
def semantic_search():
    return run_semantic_search()
