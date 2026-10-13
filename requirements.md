# System Requirements Document (SRD) - Smart Event Management System

## 1. Introduction
This document defines the functional and non-functional requirements for the **Smart Event Management System**, developed under the Specification-Driven Application Development (SDAD) methodology.

## 2. System Actors & Roles
The system supports three primary user roles:
1. **Event Organizer (Admin):** Manages event schedules, creates sessions, views dashboards and the Event Log / audit trail, reviews automated AI assessments for talk submissions (approving or rejecting proposals), and can cancel an approved event.
2. **Speaker:** Registers in the system, submits talk proposals (including titles, abstracts, and bios), tracks proposal statuses, sees only approved events in My Events, and can cancel an approved event.
3. **Attendee:** Searches for sessions, browses data in clean tabular views, and books or reserves seats for events.

## 3. Functional Requirements
1. **Authentication & User Management:** Secure user registration and login with distinct role-based permissions (Organizer, Speaker, Attendee).
2. **Data Search & Details:** 
   * Users must be able to search for sessions, talks, or speakers using keywords.
   * The system must allow viewing detailed information for any selected result.
3. **Tabular Data Views:** System data (such as session schedules, booking lists, and user directories) must be presented in structured tables. Organizer and lecturer My Events tables match the Approved events columns (Event, Speaker, Date, Time, Hall, Open/Sold Seats, Status). More Details opens a cinematic modal that shows only the lecture summary (abstract).
4. **Management Dashboard:** A dedicated dashboard displaying key metrics, such as open sessions, total registrations, and seat capacity.
5. **Data Entry (Command Model):** Authorized users can input new data, such as booking a seat, submitting a talk proposal, or creating a new session. Organizer and lecturer schedule pickers allow start times on the hour or half-hour only; the end time is set automatically to 90 minutes later and is not edited by hand. Date fields use a custom calendar styled to the product palette (rounded days, hover and selected states). Action buttons show a spinner while the request is processing. Status banners and action alerts fade out automatically after 6 seconds. Organizers and lecturers can cancel an approved event; the session is removed from the active program immediately and moved to Trash / Recycling Bin (`status=cancelled`). Ticket holders receive an automated chat notice that the event is cancelled and a full refund will be issued. Lecturer and organizer dashboards share a two-way chat: a green unread-count badge sits at the top-right of the chat icon, opening the panel shows an email-style thread, and either side can type and send a custom reply. The organizer inbox lists one conversation per lecturer, titled with that lecturer's name rather than a generic cancellation heading. An admin cancellation notifies the lecturer; a lecturer cancellation notifies the organizer. Organizer and lecturer More Details views show only the lecture summary (abstract).
6. **Autonomous AI Assessment Agent:** A background process reads speaker submissions, queries a vector database (RAG style), and performs external checks via MCP tools (e.g., Tavily search) to evaluate talk relevance.
7. **AI Innovation Ideas Hub:** Speakers can search a topic or keyword, browse Ollama-generated talk concepts tailored to that query, and convert an idea into a talk proposal. If the local model is offline, curated fallback ideas stay on screen.
8. **Hall Seat Selection:** When booking a session, attendees see a visual seating map sized to the named hall (Conference Room 50, Grand Hall 100, Main Auditorium 300), click available seats to select or deselect them, and reserve those seat IDs. Taken seats are disabled; the booking updates remaining capacity. Hall pickers and tables show the hall name with capacity in parentheses.

## 4. Non-Functional & Architecture Requirements
1. **Methodology:** Developed using structured Markdown documentation and SDAD.
2. **Framework & Architecture:** Built on a **Flask** application server, structured with **MVC / CQRS** patterns, and implementing **Event Sourcing** for state management.
3. **Database & Deployment:** Data persistence managed via a cloud database (e.g., Somee.com).
4. **AI & MCP:** Integration with a vector database for semantic matching and external tool integration via **Model Context Protocol (MCP)**.
5. **Version Control:** Fully tracked and managed in a GitHub repository.
6. **Development Standards:** Clean, modular Flask/CQRS code, descriptive commits, and a polished professional UI/UX.