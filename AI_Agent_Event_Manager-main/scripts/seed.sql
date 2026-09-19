-- Sample data for the Event Management System on Somee MS SQL (AiEventsDB).
-- Run in Somee Control Panel → MS SQL → Query / SQL Manager, or any SSMS session
-- connected to AiEventsDB.mssql.somee.com.
--
-- Safe to re-run: MERGE updates existing seed IDs instead of duplicating them.
-- JSON columns are stored as NVARCHAR, matching SQLAlchemy's MS SQL mapping.

SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRANSACTION;

MERGE organizers AS target
USING (VALUES
    (N'org-summit', N'Tech Summit Israel'),
    (N'org-meetup', N'Haifa Dev Meetup'),
    (N'org-campus', N'Campus Innovation Lab')
) AS source (id, name)
ON target.id = source.id
WHEN MATCHED THEN UPDATE SET name = source.name
WHEN NOT MATCHED THEN INSERT (id, name) VALUES (source.id, source.name);

MERGE speakers AS target
USING (VALUES
    (N'spk-maya', N'Maya Cohen'),
    (N'spk-daniel', N'Daniel Levi'),
    (N'spk-noa', N'Noa Ben-David'),
    (N'spk-omar', N'Omar Hassan')
) AS source (id, name)
ON target.id = source.id
WHEN MATCHED THEN UPDATE SET name = source.name
WHEN NOT MATCHED THEN INSERT (id, name) VALUES (source.id, source.name);

MERGE attendees AS target
USING (VALUES
    (N'att-noah', N'Noah Adler'),
    (N'att-lia', N'Lia Mizrahi'),
    (N'att-yonatan', N'Yonatan Peretz'),
    (N'att-sara', N'Sara Klein'),
    (N'att-amir', N'Amir Dahan')
) AS source (id, name)
ON target.id = source.id
WHEN MATCHED THEN UPDATE SET name = source.name
WHEN NOT MATCHED THEN INSERT (id, name) VALUES (source.id, source.name);

MERGE events AS target
USING (VALUES
    (N'a1e00000-0000-4000-8000-000000000001', N'org-summit', N'AI Agents Summit 2026',
     N'A full-day program on autonomous agents, CQRS, and production event systems.',
     N'2026-10-15', 80, 5, N'active'),
    (N'a1e00000-0000-4000-8000-000000000002', N'org-meetup', N'Building Event Systems with Flask',
     N'Hands-on workshop covering commands, queries, and an SQLAlchemy event store.',
     N'2026-10-22', 40, 3, N'active'),
    (N'a1e00000-0000-4000-8000-000000000003', N'org-campus', N'Campus AI Night',
     N'Lightning talks from students and local engineers building AI-assisted products.',
     N'2026-11-03', 50, 1, N'active'),
    (N'a1e00000-0000-4000-8000-000000000004', N'org-campus', N'Intro to RAG',
     N'A compact session on retrieval-augmented generation for conference abstracts.',
     N'2026-09-30', 12, 12, N'active'),
    (N'a1e00000-0000-4000-8000-000000000005', N'org-meetup', N'Legacy Monoliths Workshop',
     N'Cancelled due to speaker travel issues. Use this row to test inactive events.',
     N'2026-11-05', 30, 0, N'cancelled')
) AS source (id, organizer_id, title, description, date, capacity, seats_booked, status)
ON target.id = source.id
WHEN MATCHED THEN UPDATE SET
    organizer_id = source.organizer_id,
    title = source.title,
    description = source.description,
    date = source.date,
    capacity = source.capacity,
    seats_booked = source.seats_booked,
    status = source.status
WHEN NOT MATCHED THEN INSERT (id, organizer_id, title, description, date, capacity, seats_booked, status)
VALUES (source.id, source.organizer_id, source.title, source.description, source.date, source.capacity, source.seats_booked, source.status);

MERGE talk_submissions AS target
USING (VALUES
    (N'b2e00000-0000-4000-8000-000000000001', N'spk-maya', N'Building Autonomous Event Agents',
     N'How a background agent can assess talk quality, check topic relevance, and queue human review without blocking the speaker API.',
     N'architecture', N'under_review',
     N'{"status":"queued","quality_score":42,"summary":"Placeholder assessment seeded for local and Somee testing.","queued_for_background_agent":true,"source":"seed"}'),
    (N'b2e00000-0000-4000-8000-000000000002', N'spk-daniel', N'RAG for Conference Abstracts',
     N'A practical retrieval pipeline that embeds speaker bios and abstracts so organizers can find overlapping or complementary talks.',
     N'ai', N'under_review',
     N'{"status":"queued","quality_score":36,"summary":"Placeholder assessment seeded for local and Somee testing.","queued_for_background_agent":true,"source":"seed"}'),
    (N'b2e00000-0000-4000-8000-000000000003', N'spk-noa', N'Inclusive Event Design',
     N'Designing capacity, seating, and session formats so first-time attendees and experienced engineers both get value from the same program.',
     N'community', N'pending_assessment',
     N'{}'),
    (N'b2e00000-0000-4000-8000-000000000004', N'spk-omar', N'From Monolith to CQRS',
     N'A migration story: splitting write commands from read models while keeping a single Flask app and an MS SQL event store.',
     N'architecture', N'under_review',
     N'{"status":"queued","quality_score":38,"summary":"Placeholder assessment seeded for local and Somee testing.","queued_for_background_agent":true,"source":"seed"}')
) AS source (id, speaker_id, title, abstract, category, status, ai_assessment)
ON target.id = source.id
WHEN MATCHED THEN UPDATE SET
    speaker_id = source.speaker_id,
    title = source.title,
    abstract = source.abstract,
    category = source.category,
    status = source.status,
    ai_assessment = source.ai_assessment
WHEN NOT MATCHED THEN INSERT (id, speaker_id, title, abstract, category, status, ai_assessment)
VALUES (source.id, source.speaker_id, source.title, source.abstract, source.category, source.status, source.ai_assessment);

MERGE bookings AS target
USING (VALUES
    (N'c3e00000-0000-4000-8000-000000000001', N'att-noah', N'a1e00000-0000-4000-8000-000000000001', 2, N'confirmed'),
    (N'c3e00000-0000-4000-8000-000000000002', N'att-lia', N'a1e00000-0000-4000-8000-000000000001', 1, N'confirmed'),
    (N'c3e00000-0000-4000-8000-000000000003', N'att-yonatan', N'a1e00000-0000-4000-8000-000000000001', 2, N'confirmed'),
    (N'c3e00000-0000-4000-8000-000000000004', N'att-sara', N'a1e00000-0000-4000-8000-000000000002', 2, N'confirmed'),
    (N'c3e00000-0000-4000-8000-000000000005', N'att-amir', N'a1e00000-0000-4000-8000-000000000002', 1, N'confirmed'),
    (N'c3e00000-0000-4000-8000-000000000006', N'att-noah', N'a1e00000-0000-4000-8000-000000000003', 1, N'confirmed'),
    (N'c3e00000-0000-4000-8000-000000000007', N'att-lia', N'a1e00000-0000-4000-8000-000000000004', 3, N'confirmed'),
    (N'c3e00000-0000-4000-8000-000000000008', N'att-yonatan', N'a1e00000-0000-4000-8000-000000000004', 3, N'confirmed'),
    (N'c3e00000-0000-4000-8000-000000000009', N'att-sara', N'a1e00000-0000-4000-8000-000000000004', 3, N'confirmed'),
    (N'c3e00000-0000-4000-8000-000000000010', N'att-amir', N'a1e00000-0000-4000-8000-000000000004', 3, N'confirmed')
) AS source (id, attendee_id, event_id, seats, status)
ON target.id = source.id
WHEN MATCHED THEN UPDATE SET
    attendee_id = source.attendee_id,
    event_id = source.event_id,
    seats = source.seats,
    status = source.status
WHEN NOT MATCHED THEN INSERT (id, attendee_id, event_id, seats, status)
VALUES (source.id, source.attendee_id, source.event_id, source.seats, source.status);

COMMIT TRANSACTION;
GO
