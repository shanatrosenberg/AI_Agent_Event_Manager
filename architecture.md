# Architecture & Technical Design - Smart Event Management System

## 1. System Overview
The system is built using a Python Flask backend, structured around clean architecture principles, and integrates advanced AI agents with cloud persistence.

## 2. Backend & Architecture Patterns
* **Framework:** Python Flask (handling routing, business logic, and API endpoints).
* **Architectural Pattern:** MVC (Model-View-Controller) / CQRS (Command Query Responsibility Segregation) to separate data reads from state-changing commands (e.g., booking seats, submitting talks).
* **Event Sourcing:** State changes in the system (such as seat reservations or proposal updates) are recorded as immutable events in an Event Store.

## 3. Database & Cloud Persistence
* **Relational Database (Cloud):** Hosted on **Somee.com** (SQL-based cloud hosting) to manage core entities: Users (Organizers, Speakers, Attendees), Events, Sessions, and Bookings.
* **Vector Database (RAG):** Used for embedding speaker bios and abstracts to enable semantic similarity searches for the AI assessment agent.

## 4. AI & MCP Integration
* **Autonomous Deep Agent:** Runs as a background background/service process to review speaker submissions.
* **Model Context Protocol (MCP):** Connects the AI agent to external tools, such as web search (e.g., Tavily API) to verify speaker credentials and trends.