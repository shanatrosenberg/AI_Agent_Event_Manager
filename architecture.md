# Architecture & Technical Design - Smart Event Management System

## 1. System Overview
The system is built using a Python Flask backend, structured around clean architecture principles, and integrates advanced AI agents with cloud persistence.

## 2. Backend & Architecture Patterns
* **Framework:** Python Flask (handling routing, business logic, and API endpoints).
* **Architectural Pattern:** MVC (Model-View-Controller) / CQRS (Command Query Responsibility Segregation) to separate data reads from state-changing commands (e.g., booking seats, submitting talks).
* **Event Sourcing:** Every talk state change is appended immutably to `stored_events` (`TalkProposed`, `TalkInnovationReviewed`, `TalkApproved`, `TalkRejected`, plus related domain events). `cqrs/projections.py` rebuilds current talk state by folding that stream. Organizers inspect the chronological audit trail on the dashboard Event Log (`GET /api/organizer/event-log`). Speakers see declined proposals in Your Submissions → Rejected Proposals.

## 3. Database & Cloud Persistence
* **Relational Database (Cloud):** Hosted on **Somee.com** (SQL-based cloud hosting) to manage core entities: Users (Organizers, Speakers, Attendees), Events, Sessions, and Bookings.
* **Vector Database (RAG):** Talk titles, abstracts, and speaker bios are embedded and stored as JSON vectors in `talk_embeddings` (Somee / SQL). A local hashing embedder is the default; Hugging Face feature-extraction can be enabled with `EMBEDDING_PROVIDER=huggingface`. Semantic search is a CQRS query used by `/api/search`, organizer, and attendee routes.

## 4. AI & MCP Integration
* **Autonomous Deep Agent:** `services/deep_agent.py` scans pending talk proposals on submit and on a background interval (also `python scripts/run_assessment_agent.py`). It acts as an Innovation & Uniqueness Reviewer: RAG compares the new title/abstract against all approved and pending talks, then stores `innovation_score`, `innovation_badge`, overlapping talks, and a uniqueness explanation on `talk_submissions.ai_assessment` (also surfaced on the proposal payload). Recorded as a `TalkInnovationReviewed` event.
* **Vector DB / RAG:** `compare_against_program` ranks the proposal against the full approved/pending catalog so high overlap lowers novelty and unique angles raise the Innovation Score.
* **Model Context Protocol (MCP):** An in-process MCP server/client (`mcp/`) exposes tools the Deep Agent can invoke. `tavily_web_speaker_search` runs a live Tavily query of speaker name + talk title (`services/tavily.py`, `TAVILY_API_KEY`) and stores snippets plus a "Verified via Tavily Web Search" badge on the proposal. `venue_capacity_validator` checks hall sizes (50/100/300) and schedule conflicts. `python scripts/run_mcp_server.py` serves the same tools over stdio JSON-RPC. Pytest stays offline.