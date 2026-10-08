def test_list_active_events_includes_created_event(client, created_event):
    response = client.get("/api/attendee/events")

    assert response.status_code == 200
    events = response.get_json()
    assert len(events) == 1
    assert events[0]["id"] == created_event["id"]
    assert events[0]["available"] is True


def test_list_active_events_is_empty_when_none_exist(client):
    response = client.get("/api/attendee/events")

    assert response.status_code == 200
    assert response.get_json() == []


def test_register_with_header_identity(client, attendee_headers, attendee_id, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seats": 2},
        headers=attendee_headers,
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["attendee_id"] == attendee_id
    assert body["event_id"] == created_event["id"]
    assert body["seats"] == 2
    assert body["status"] == "confirmed"
    assert "id" in body


def test_register_with_body_identity(client, attendee_id, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "attendee_id": attendee_id},
    )

    assert response.status_code == 201
    assert response.get_json()["attendee_id"] == attendee_id
    assert response.get_json()["seats"] == 1


def test_register_with_query_identity(client, attendee_id, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"]},
        query_string={"attendee_id": attendee_id},
    )

    assert response.status_code == 201
    assert response.get_json()["attendee_id"] == attendee_id


def test_register_prefers_header_over_body(client, attendee_headers, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "attendee_id": "att-from-body"},
        headers=attendee_headers,
    )

    assert response.status_code == 201
    assert response.get_json()["attendee_id"] == attendee_headers["X-Attendee-Id"]


def test_register_requires_identity(client, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"]},
    )

    assert response.status_code == 400
    assert "attendee_id" in response.get_json()["error"]


def test_register_requires_json_body(client, attendee_headers):
    response = client.post("/api/attendee/register", headers=attendee_headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON body is required"


def test_register_rejects_missing_event_id(client, attendee_headers):
    response = client.post(
        "/api/attendee/register",
        json={"seats": 1},
        headers=attendee_headers,
    )

    assert response.status_code == 400
    assert "event_id" in response.get_json()["error"]


def test_register_rejects_invalid_seats(client, attendee_headers, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seats": "many"},
        headers=attendee_headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "seats must be an integer"


def test_register_unknown_event_returns_404(client, attendee_headers):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": "missing-event"},
        headers=attendee_headers,
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "event not found"


def test_register_duplicate_returns_409(client, attendee_headers, created_event):
    first = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"]},
        headers=attendee_headers,
    )
    second = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"]},
        headers=attendee_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert "already registered" in second.get_json()["error"]


def test_register_reduces_remaining_seats(client, attendee_headers, created_event):
    client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seats": 5},
        headers=attendee_headers,
    )

    events = client.get("/api/attendee/events").get_json()
    matching = next(event for event in events if event["id"] == created_event["id"])
    assert matching["seats_booked"] == 5
    assert matching["remaining_seats"] == created_event["capacity"] - 5
    assert matching["last_seats"] is False
    assert matching["sold_out"] is False


def test_browse_events_page_sorts_closest_first(client, speaker_headers, event_payload):
    from tests.conftest import approve_talk_event

    later = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Later Summit",
        date="2026-12-20",
        start_time="14:00",
        end_time="15:00",
    )
    earlier = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Sooner Summit",
        date="2026-11-02",
        start_time="09:00",
        end_time="10:00",
    )
    page = client.get("/events")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Find a talk that feels like an invitation" in html
    assert 'id="talk-search"' in html
    assert "Search talks by topic" in html
    assert 'id="filter-topic"' in html
    assert 'id="filter-speaker"' in html
    assert "Reset Filters" in html
    assert html.index("Sooner Summit") < html.index("Later Summit")
    assert f"{earlier['date']} | {earlier['start_time']}" in html
    assert f"{later['date']} | {later['start_time']}" in html
    assert earlier["id"] in html
    assert later["id"] in html
    alias = client.get("/browse")
    assert alias.status_code == 200
    assert b"Sooner Summit" in alias.data


def test_browse_semantic_search_ranks_matching_talks(client, speaker_headers, event_payload):
    from tests.conftest import approve_talk_event

    cqrs = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Event sourcing with CQRS",
        abstract="Commands, queries, and an event store for Flask conference platforms.",
        date="2026-11-04",
        start_time="10:00",
        end_time="11:00",
    )
    approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Sourdough baking for beginners",
        abstract="A hands-on kitchen workshop about bread, pastry, and fermentation.",
        date="2026-11-05",
        start_time="13:00",
        end_time="14:00",
    )
    response = client.get(
        "/api/attendee/search",
        query_string={"q": "event sourcing CQRS flask queries", "limit": 8},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] >= 1
    assert body["results"][0]["id"] == cqrs["id"]
    assert body["results"][0]["title"] == "Event sourcing with CQRS"
    page = client.get("/events", query_string={"q": "event sourcing CQRS"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'id="talk-search"' in html
    assert "event sourcing CQRS" in html
    assert "Event sourcing with CQRS" in html
    assert cqrs["id"] in html


def test_browse_filters_by_topic_and_speaker(client, event_payload):
    from tests.conftest import approve_talk_event

    client.post(
        "/register",
        json={"user_id": "spk-ada", "password": "SecurePass1", "role": "speaker", "name": "Ada Architect"},
    )
    client.post(
        "/register",
        json={"user_id": "spk-remy", "password": "SecurePass1", "role": "speaker", "name": "Remy Baker"},
    )
    architecture = approve_talk_event(
        client,
        {"X-Speaker-Id": "spk-ada"},
        event_payload,
        title="CQRS Workshop",
        abstract="Commands and queries for conference platforms.",
        category="architecture",
        date="2026-11-06",
        start_time="09:00",
        end_time="10:00",
    )
    food = approve_talk_event(
        client,
        {"X-Speaker-Id": "spk-remy"},
        event_payload,
        title="Bread Lab",
        abstract="A kitchen workshop on sourdough and pastry.",
        category="food",
        date="2026-11-07",
        start_time="11:00",
        end_time="12:00",
    )

    by_topic = client.get("/api/attendee/approved", query_string={"topic": "architecture"})
    assert by_topic.status_code == 200
    topic_ids = [item["id"] for item in by_topic.get_json()]
    assert architecture["id"] in topic_ids
    assert food["id"] not in topic_ids

    by_speaker = client.get("/api/attendee/approved", query_string={"speaker": "spk-remy"})
    assert by_speaker.status_code == 200
    speaker_ids = [item["id"] for item in by_speaker.get_json()]
    assert food["id"] in speaker_ids
    assert architecture["id"] not in speaker_ids

    page = client.get("/events", query_string={"topic": "architecture", "speaker": "spk-ada"})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "CQRS Workshop" in html
    assert "Bread Lab" not in html
    assert 'id="reset-filters"' in html
    assert "Ada Architect" in html


def test_browse_events_last_seats_and_sold_out_badges(client, attendee_headers, speaker_headers, event_payload):
    from tests.conftest import approve_talk_event

    last_seats = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Almost Full Talk",
        date="2026-11-08",
        start_time="11:00",
        end_time="12:00",
    )
    sold_out = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Packed Hall Talk",
        date="2026-11-09",
        start_time="13:00",
        end_time="14:00",
    )
    assert client.post(
        "/api/attendee/register",
        json={"event_id": last_seats["id"], "seats": last_seats["capacity"] - 3},
        headers=attendee_headers,
    ).status_code == 201
    assert client.post(
        "/api/attendee/register",
        json={"event_id": sold_out["id"], "seats": sold_out["capacity"]},
        headers={"X-Attendee-Id": "att-sold-out"},
    ).status_code == 201

    page = client.get("/events")
    html = page.get_data(as_text=True)
    assert "Last seats!" in html
    assert "Only 3 left" not in html
    assert "seats open" not in html
    assert f"{last_seats['date']} | {last_seats['start_time']}" in html
    assert f"{sold_out['date']} | {sold_out['start_time']}" in html
    assert "Sold Out" in html
    assert "Buy Tickets" in html
    assert "Existing Customer" in html
    assert "New Customer" in html
    assert "הירשם" not in html
    assert "Almost Full Talk" in html
    assert "Packed Hall Talk" in html
    assert 'id="join-as-attendee"' in html
    assert "join=1" in html
    assert 'href="/register"' not in html
    assert 'id="join-modal"' in html
    assert "This portal is for attendees only" in html


def test_join_as_attendee_opens_attendee_only_portal(client):
    page = client.get("/events?join=1")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Join as attendee" in html
    assert "Existing Customer" in html
    assert "New Customer" in html
    assert "This portal is for attendees only" in html
    assert 'value="speaker"' not in html
    assert "Create speaker account" not in html
    assert "Speaker portal" not in html


def test_attendee_login_get_stays_on_attendee_portal(client):
    response = client.get("/attendee/login")
    assert response.status_code == 302
    assert "/events" in response.headers["Location"]
    assert "join=1" in response.headers["Location"]


def test_locked_attendee_register_page_hides_speaker_option(client):
    page = client.get("/register?role=attendee")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Create your attendee account" in html
    assert 'value="speaker"' not in html
    assert "Create speaker account" not in html
    created = client.post(
        "/register?role=attendee",
        json={
            "user_id": "att-locked",
            "password": "SecurePass1",
            "role": "speaker",
            "locked_role": "attendee",
            "name": "Locked Attendee",
        },
    )
    assert created.status_code == 201
    assert created.get_json()["role"] == "attendee"


def test_buy_tickets_new_customer_reduces_remaining_seats(client, created_event):
    response = client.post(
        "/api/attendee/tickets",
        json={
            "event_id": created_event["id"],
            "seats": 3,
            "customer": "new",
            "user_id": "att-new-buyer",
            "password": "SecurePass1",
            "name": "New Buyer",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["attendee_id"] == "att-new-buyer"
    assert body["seats"] == 3
    assert body["remaining_seats"] == created_event["capacity"] - 3
    assert body["seats_booked"] == 3
    events = client.get("/api/attendee/approved").get_json()
    matching = next(event for event in events if event["id"] == created_event["id"])
    assert matching["remaining_seats"] == created_event["capacity"] - 3
    with client.session_transaction() as session:
        assert session["user_id"] == "att-new-buyer"
        assert session["role"] == "attendee"


def test_buy_tickets_existing_customer_reduces_remaining_seats(client, created_event):
    created = client.post(
        "/register",
        json={
            "user_id": "att-return",
            "password": "SecurePass1",
            "role": "attendee",
            "name": "Returning Guest",
        },
    )
    assert created.status_code == 201

    response = client.post(
        "/api/attendee/tickets",
        json={
            "event_id": created_event["id"],
            "seats": 2,
            "customer": "existing",
            "user_id": "att-return",
            "password": "SecurePass1",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["attendee_id"] == "att-return"
    assert body["seats"] == 2
    assert body["remaining_seats"] == created_event["capacity"] - 2


def test_buy_tickets_signed_in_attendee_uses_session(client, created_event):
    client.post(
        "/register",
        json={
            "user_id": "att-session",
            "password": "SecurePass1",
            "role": "attendee",
            "name": "Session Buyer",
        },
    )
    response = client.post(
        "/api/attendee/tickets",
        json={"event_id": created_event["id"], "seats": 1},
    )
    assert response.status_code == 201
    assert response.get_json()["attendee_id"] == "att-session"
    assert response.get_json()["remaining_seats"] == created_event["capacity"] - 1


def test_attendee_login_then_buy_tickets(client, created_event):
    client.post(
        "/register",
        json={
            "user_id": "att-login-buy",
            "password": "SecurePass1",
            "role": "attendee",
            "name": "Login Buyer",
        },
    )
    client.post("/logout")
    login = client.post(
        "/attendee/login",
        json={"user_id": "att-login-buy", "password": "SecurePass1"},
    )
    assert login.status_code == 200
    assert login.get_json()["role"] == "attendee"
    bought = client.post(
        "/api/attendee/tickets",
        json={"event_id": created_event["id"], "seats": 4},
    )
    assert bought.status_code == 201
    assert bought.get_json()["seats"] == 4
    assert bought.get_json()["remaining_seats"] == created_event["capacity"] - 4


def test_my_tickets_requires_attendee_login(client):
    response = client.get("/my-events")
    assert response.status_code == 302
    assert "/attendee/login" in response.headers["Location"]
    assert "next=/my-events" in response.headers["Location"]


def test_my_tickets_empty_state_for_new_attendee(client):
    client.post(
        "/register",
        json={
            "user_id": "att-empty-tickets",
            "password": "SecurePass1",
            "role": "attendee",
            "name": "Empty Tickets",
        },
    )
    browse = client.get("/events")
    assert browse.status_code == 200
    assert b"My Tickets" in browse.data
    home = client.get("/")
    assert home.status_code == 200
    assert b"My Tickets" in home.data
    page = client.get("/my-events")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "My Tickets" in html
    assert "You haven't registered for any events yet." in html
    assert "Browse available talks" in html


def test_my_tickets_lists_purchased_events(client, created_event):
    client.post(
        "/register",
        json={
            "user_id": "att-has-tickets",
            "password": "SecurePass1",
            "role": "attendee",
            "name": "Has Tickets",
        },
    )
    bought = client.post(
        "/api/attendee/tickets",
        json={"event_id": created_event["id"], "seats": 3},
    )
    assert bought.status_code == 201
    page = client.get("/my-tickets")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert created_event["title"] in html
    assert "3 tickets" in html
    assert f"{created_event['date']} | {created_event['start_time']}" in html
    assert 'id="tickets-grid"' in html
    assert bought.get_json()["id"] in html or created_event["id"] in html
    assert "seats held for you" not in html
    assert "seats open" not in html
    assert created_event["hall_label"] not in html
