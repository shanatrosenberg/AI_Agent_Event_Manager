from typing import Any

from models.submission import TalkSubmission


class AIAssessmentAgent:
    """Placeholder for the autonomous AI assessment agent (RAG + MCP)."""

    def evaluate(self, submission: TalkSubmission) -> dict[str, Any]:
        placeholder_score = min(100, max(10, len(submission.abstract.split()) * 2))
        return {
            "status": "queued",
            "quality_score": placeholder_score,
            "summary": (
                "Placeholder assessment only. Abstract length was used as a stand-in "
                "quality signal until the background agent is connected."
            ),
            "hooks": {
                "vector_rag": {
                    "enabled": False,
                    "purpose": "Embed speaker bios and abstracts for semantic similarity search",
                    "next_step": "Index abstract embeddings in the vector database",
                },
                "mcp_tavily": {
                    "enabled": False,
                    "purpose": "Verify speaker credentials and topic relevance via web search",
                    "next_step": "Connect the agent to Tavily through MCP",
                },
            },
        }

    def enqueue(self, submission: TalkSubmission) -> dict[str, Any]:
        """Integration hook for the background Deep Agent process."""
        assessment = self.evaluate(submission)
        assessment["queued_for_background_agent"] = True
        return assessment
