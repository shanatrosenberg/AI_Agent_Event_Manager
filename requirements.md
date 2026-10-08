# System Requirements Document (SRD) - Smart Event Management System

## 1. Introduction
This document defines the functional and non-functional requirements for the **Smart Event Management System**, developed under the Specification-Driven Application Development (SDAD) methodology.

## 2. System Actors & Roles
The system supports three primary user roles:
1. **Event Organizer (Admin):** Manages event schedules, creates sessions, views dashboards and the Event Log / audit trail, and reviews automated AI assessments for talk submissions (approving or rejecting proposals).
2. **Speaker:** Registers in the system, submits talk proposals (including titles, abstracts, and bios), and tracks proposal statuses.
3. **Attendee:** Searches for sessions, browses data in clean tabular views, and books or reserves seats for events.

## 3. Functional Requirements
1. **Authentication & User Management:** Secure user registration and login with distinct role-based permissions (Organizer, Speaker, Attendee).
2. **Data Search & Details:** 
   * Users must be able to search for sessions, talks, or speakers using keywords.
   * The system must allow viewing detailed information for any selected result.
3. **Tabular Data Views:** System data (such as session schedules, booking lists, and user directories) must be presented in structured tables.
4. **Management Dashboard:** A dedicated dashboard displaying key metrics, such as open sessions, total registrations, and seat capacity.
5. **Data Entry (Command Model):** Authorized users can input new data, such as booking a seat, submitting a talk proposal, or creating a new session.
6. **Autonomous AI Assessment Agent:** A background process reads speaker submissions, queries a vector database (RAG style), and performs external checks via MCP tools (e.g., Tavily search) to evaluate talk relevance.

## 4. Non-Functional & Architecture Requirements
1. **Methodology:** Developed using structured Markdown documentation and SDAD.
2. **Framework & Architecture:** Built on a **Flask** application server, structured with **MVC / CQRS** patterns, and implementing **Event Sourcing** for state management.
3. **Database & Deployment:** Data persistence managed via a cloud database (e.g., Somee.com).
4. **AI & MCP:** Integration with a vector database for semantic matching and external tool integration via **Model Context Protocol (MCP)**.
5. **Version Control:** Fully tracked and managed in a GitHub repository.
6. **Development Standards:** Clean, modular Flask/CQRS code, descriptive commits, and a polished professional UI/UX.