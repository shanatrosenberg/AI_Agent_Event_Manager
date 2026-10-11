# Architecture & Technical Design - Smart Event Management System

## 1. System Overview
The system is built using a Python Flask backend, structured around clean architecture principles, and integrates advanced AI agents with cloud persistence.

## 2. Backend & Architecture Patterns
* **Framework:** Python Flask (handling routing, business logic, and API endpoints).
* **Architectural Pattern:** MVC (Model-View-Controller) / CQRS (Command Query Responsibility Segregation) to separate data reads from state-changing commands (e.g., booking seats, submitting talks).
* **Event Sourcing:** Every talk state change is appended immutably to `stored_events` (`TalkProposed`, `TalkInnovationReviewed`, `TalkApproved`, `TalkRejected`, plus related domain events). `cqrs/projections.py` rebuilds current talk state by folding that stream. Organizers inspect the chronological audit trail on the dashboard Event Log (`GET /api/organizer/event-log`). Speakers see declined proposals in Your Submissions → Rejected Proposals.

## 3. Database & Cloud Persistence
* **Relational Database (Cloud):** Hosted on **Somee.com** (SQL-based cloud hosting) to manage core entities: Users (Organizers, Speakers, Attendees), Events, Sessions, and Bookings.
* **Vector Database (RAG):** Talk titles, abstracts, and speaker bios are embedded and stored as JSON vectors in `talk_embeddings` (Somee / SQL). A local hashing embedder is used for semantic search (`/api/search`, organizer, and attendee routes).

## 4. AI & MCP Integration
* **Autonomous Deep Agent:** `services/deep_agent.py` scans pending talk proposals on submit and on a background interval (also `python scripts/run_assessment_agent.py`). It acts as an Innovation & Uniqueness Reviewer: RAG compares the new title/abstract against all approved and pending talks, then stores `innovation_score`, `innovation_badge`, overlapping talks, and a uniqueness explanation on `talk_submissions.ai_assessment` (also surfaced on the proposal payload). Recorded as a `TalkInnovationReviewed` event.
* **AI Innovation Ideas Hub:** Speakers search any topic (`POST /api/speaker/innovation-ideas` with `query`) and local Ollama (`services/idea_hub.py`, `POST http://127.0.0.1:11434/api/generate`, model `llama3` or `OLLAMA_MODEL`) drafts tailored talk concepts. Empty search shows the trending board. Offline or empty Ollama responses fall back to curated ideas for that topic.
* **Abstract enhancer:** `POST /api/speaker/enhance-abstract` sends the speaker draft to local Ollama with a conference-writer prompt and returns the generated 3–4 sentence abstract. If Ollama is offline, the original draft is returned unchanged so the speaker UI does not crash.
* **Vector DB / RAG:** `compare_against_program` ranks the proposal against the full approved/pending catalog so high overlap lowers novelty and unique angles raise the Innovation Score.
* **Model Context Protocol (MCP):** An in-process MCP server/client (`mcp/`) exposes tools the Deep Agent can invoke. `tavily_web_speaker_search` runs a live Tavily query of speaker name + talk title (`services/tavily.py`, `TAVILY_API_KEY`) and stores snippets plus a "Verified via Tavily Web Search" badge on the proposal. `venue_capacity_validator` checks hall sizes (50/100/300) and schedule conflicts. `python scripts/run_mcp_server.py` serves the same tools over stdio JSON-RPC. Pytest stays offline.

## 5. Attendee Hall Seating
* **Layout:** `services/seating.py` builds a grid from hall capacity (50 = 5×10, 100 = 10×10, 300 = 15×20) with labels such as `A1`.
* **Read model:** `GET /api/attendee/events/<id>/seats` returns the map plus taken IDs from confirmed bookings.
* **Command:** `RegisterAttendee` accepts `seat_ids`, rejects unknown or already reserved seats, stores them on `bookings.seat_labels`, and increments `events.seats_booked`. Quantity-only bookings auto-assign the next open seats. `SeatReserved` includes the seat IDs.

## 6. Event program states
* Approved events stay on the attendee catalog. Remaining seats drive **Last seats!** (1–10 open) and **Sold Out** (0 open).
* `events.status` also stores `cancelled` and `deleted`. Attendee browse hides both. Organizers keep them for history. `DELETE /api/organizer/events/<id>` is a soft delete (`status=deleted`) rather than a hard row remove.
* `python scripts/seed.py --reset` (or `flask --app main seed`) loads a realistic program covering open, last-seat, sold-out, cancelled, and deleted sessions.