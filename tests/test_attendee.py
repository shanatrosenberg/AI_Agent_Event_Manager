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


def test_register_additional_seats_appends_to_booking(client, attendee_headers, created_event):
    first = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seat_ids": ["A1"]},
        headers=attendee_headers,
    )
    second = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seat_ids": ["B2", "B3"]},
        headers=attendee_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    body = second.get_json()
    assert body["id"] == first.get_json()["id"]
    assert body["additional"] is True
    assert body["added_seat_ids"] == ["B2", "B3"]
    assert body["seat_ids"] == ["A1", "B2", "B3"]
    assert body["seats"] == 3
    assert body["remaining_seats"] == created_event["capacity"] - 3


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
    assert "Upcoming sessions, closest date first. Reserve a seat while the hall is still open." in html
    assert "User Name" in html
    assert "Display name" not in html
    assert "USER NAME" not in html
    assert "Username" not in html
    assert 'id="talk-search"' not in html
    assert "Search talks by topic" not in html
    assert "Filter by topic" in html
    assert "Filter by speaker" in html
    assert "Reset Filters" in html
    assert 'id="talk-search-button"' in html
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
    assert 'id="talk-search"' not in html
    assert "Event sourcing with CQRS" in html
    assert "Sourdough baking for beginners" in html
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
    assert "LAST SEATS" in html
    assert "Last seats!" not in html
    assert "Only 3 left" not in html
    assert "seats open" not in html
    assert f"{last_seats['date']} | {last_seats['start_time']}" in html
    assert f"{sold_out['date']} | {sold_out['start_time']}" in html
    assert "Sold Out" in html
    assert "Join Waitlist" in html
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
    assert 'id="seat-map"' in html
    assert "Choose your seats" in html
    assert "Hall seating map" in html
    assert "Optional seating agent" in html
    assert "Seat us together" in html
    assert "I'll pick seats myself" in html
    assert "Accept layout" in html
    assert "Your tickets" in html
    assert 'data-state="owned"' in html


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
    assert "User Name" in html
    assert "Display name" not in html
    assert 'name="name"' not in html
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
    assert "Seat A1" in html
    assert "Seat A2" in html
    assert "Seat A3" in html
    assert f"{created_event['date']} | {created_event['start_time']}" in html
    assert 'id="tickets-grid"' in html
    assert bought.get_json()["id"] in html or created_event["id"] in html
    assert "seats held for you" not in html
    assert "seats open" not in html
    assert created_event["hall_label"] not in html
    assert "Your tickets" in html
    assert "Buy more tickets" in html
    assert f"/events?buy={created_event['id']}" in html
    assert 'class="cancel-seat-btn' not in html
    assert 'class="cancel-registration-btn' not in html
    assert "Held" in html
    assert "Cancellations are only allowed up to 48 hours before the event." in html
    assert 'data-cancellable="false"' in html


def test_seat_map_matches_hall_capacity(client, created_event):
    response = client.get(f"/api/attendee/events/{created_event['id']}/seats")
    assert response.status_code == 200
    body = response.get_json()
    assert body["capacity"] == 50
    assert body["rows"] == 5
    assert body["cols"] == 10
    assert len(body["seats"]) == 50
    assert body["seats"][0]["id"] == "A1"
    assert body["seats"][-1]["id"] == "E10"
    assert body["taken"] == []
    assert body["aisles_after"] == [5]
    assert [section["name"] for section in body["sections"]] == ["Left", "Right"]
    assert all(seat["available"] for seat in body["seats"])


def test_register_specific_seats_and_mark_them_taken(client, attendee_headers, created_event):
    booked = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seat_ids": ["B3", "C4"]},
        headers=attendee_headers,
    )
    assert booked.status_code == 201
    body = booked.get_json()
    assert body["seats"] == 2
    assert body["seat_ids"] == ["B3", "C4"]
    assert body["remaining_seats"] == created_event["capacity"] - 2

    hall = client.get(f"/api/attendee/events/{created_event['id']}/seats")
    assert hall.status_code == 200
    payload = hall.get_json()
    assert payload["taken"] == ["B3", "C4"]
    assert payload["owned"] == []
    by_id = {seat["id"]: seat for seat in payload["seats"]}
    assert by_id["B3"]["available"] is False
    assert by_id["C4"]["available"] is False
    assert by_id["A1"]["available"] is True

    mine = client.get(
        f"/api/attendee/events/{created_event['id']}/seats",
        headers=attendee_headers,
    )
    owned_map = mine.get_json()
    assert owned_map["owned"] == ["B3", "C4"]
    owned_by_id = {seat["id"]: seat for seat in owned_map["seats"]}
    assert owned_by_id["B3"]["owned"] is True
    assert owned_by_id["C4"]["owned"] is True
    assert owned_by_id["A1"]["owned"] is False


def test_register_rejects_taken_and_unknown_seats(client, attendee_headers, created_event):
    first = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seat_ids": ["A1"]},
        headers=attendee_headers,
    )
    assert first.status_code == 201

    taken = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seat_ids": ["A1"]},
        headers={"X-Attendee-Id": "att-second"},
    )
    assert taken.status_code == 409
    assert "already reserved" in taken.get_json()["error"]

    unknown = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seat_ids": ["Z99"]},
        headers={"X-Attendee-Id": "att-third"},
    )
    assert unknown.status_code == 400
    assert "unknown seat" in unknown.get_json()["error"]


def test_additional_purchase_rejects_owned_seats(client, attendee_headers, created_event):
    first = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seat_ids": ["A1", "A2"]},
        headers=attendee_headers,
    )
    assert first.status_code == 201
    again = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seat_ids": ["A1", "C3"]},
        headers=attendee_headers,
    )
    assert again.status_code == 409
    assert "already hold" in again.get_json()["error"]
    hall = client.get(
        f"/api/attendee/events/{created_event['id']}/seats",
        headers=attendee_headers,
    )
    assert hall.get_json()["owned"] == ["A1", "A2"]
    assert hall.get_json()["available_count"] == created_event["capacity"] - 2


def test_signed_in_attendee_sees_buy_more_tickets(client, created_event):
    client.post(
        "/register",
        json={"user_id": "att-more-tickets", "password": "SecurePass1", "role": "attendee"},
    )
    bought = client.post(
        "/api/attendee/tickets",
        json={"event_id": created_event["id"], "seat_ids": ["C1"]},
    )
    assert bought.status_code == 201
    page = client.get("/events")
    html = page.get_data(as_text=True)
    assert "Buy more tickets" in html
    assert 'data-already-booked="true"' in html
    assert "Buy Tickets" in html


def test_tickets_buy_more_appends_new_seats(client, created_event):
    client.post(
        "/register",
        json={"user_id": "att-buy-more", "password": "SecurePass1", "role": "attendee"},
    )
    first = client.post(
        "/api/attendee/tickets",
        json={"event_id": created_event["id"], "seat_ids": ["D5", "D6"]},
    )
    second = client.post(
        "/api/attendee/tickets",
        json={"event_id": created_event["id"], "seat_ids": ["E1"]},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    body = second.get_json()
    assert body["additional"] is True
    assert body["added_seat_ids"] == ["E1"]
    assert body["seat_ids"] == ["D5", "D6", "E1"]
    page = client.get("/my-tickets")
    html = page.get_data(as_text=True)
    assert "3 tickets" in html
    assert "Seat E1" in html
    assert "Buy more tickets" in html


def test_tickets_accept_selected_seat_ids(client, created_event):
    client.post(
        "/register",
        json={
            "user_id": "att-seat-picker",
            "password": "SecurePass1",
            "role": "attendee",
            "name": "Seat Picker",
        },
    )
    bought = client.post(
        "/api/attendee/tickets",
        json={"event_id": created_event["id"], "seat_ids": ["D5", "D6"]},
    )
    assert bought.status_code == 201
    assert bought.get_json()["seat_ids"] == ["D5", "D6"]
    assert bought.get_json()["remaining_seats"] == created_event["capacity"] - 2


def test_quantity_booking_auto_assigns_open_seats(client, attendee_headers, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seats": 2},
        headers=attendee_headers,
    )
    assert response.status_code == 201
    assert response.get_json()["seat_ids"] == ["A1", "A2"]


def test_seat_map_for_large_hall(client, speaker_headers, event_payload):
    from tests.conftest import approve_talk_event

    event = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Arena Keynote",
        date="2026-12-01",
        start_time="15:00",
        end_time="16:00",
        capacity=300,
    )
    response = client.get(f"/api/attendee/events/{event['id']}/seats")
    assert response.status_code == 200
    body = response.get_json()
    assert body["capacity"] == 300
    assert body["rows"] == 15
    assert body["cols"] == 20
    assert body["aisles_after"] == [6, 14]
    assert body["row_aisles_after"] == [7]
    assert [section["name"] for section in body["sections"]] == ["Left", "Center", "Right"]
    assert len(body["seats"]) == 300
    assert body["seats"][-1]["id"] == "O20"


def test_seat_map_for_medium_hall(client, speaker_headers, event_payload):
    from tests.conftest import approve_talk_event

    event = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Studio Workshop",
        date="2026-12-02",
        start_time="11:00",
        end_time="12:00",
        capacity=100,
    )
    response = client.get(f"/api/attendee/events/{event['id']}/seats")
    assert response.status_code == 200
    body = response.get_json()
    assert body["capacity"] == 100
    assert body["rows"] == 10
    assert body["cols"] == 10
    assert body["aisles_after"] == []
    assert body["row_aisles_after"] == [5]
    assert body["sections"] == []
    assert len(body["seats"]) == 100
    assert body["seats"][-1]["id"] == "J10"


def _session_on_day(days_ahead: int) -> tuple[str, str, str]:
    from datetime import timedelta

    from services.scheduling import session_end_time, utc_now

    start = "09:00"
    date = (utc_now() + timedelta(days=days_ahead)).date().isoformat()
    return date, start, session_end_time(start)


def _book_session(client, speaker_headers, event_payload, user_id, *, days_ahead, seat_ids=None, seats=2, title=None):
    from tests.conftest import approve_talk_event

    date, start_time, end_time = _session_on_day(days_ahead)
    event = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title=title or f"Registration window {user_id}",
        date=date,
        start_time=start_time,
        end_time=end_time,
    )
    client.post(
        "/register",
        json={"user_id": user_id, "password": "SecurePass1", "role": "attendee"},
    )
    payload = {"event_id": event["id"]}
    if seat_ids:
        payload["seat_ids"] = seat_ids
    else:
        payload["seats"] = seats
    bought = client.post("/api/attendee/tickets", json=payload)
    assert bought.status_code == 201, bought.get_json()
    return event, bought.get_json()


def test_cancel_registration_within_48_hours_is_blocked(client, speaker_headers, event_payload):
    from services.scheduling import CANCELLATION_POLICY

    event, booking = _book_session(
        client,
        speaker_headers,
        event_payload,
        "att-cancel-soon",
        days_ahead=1,
        seats=2,
        title="Starts tomorrow",
    )
    blocked = client.post(f"/api/attendee/tickets/{booking['id']}/cancel")
    assert blocked.status_code == 403
    assert blocked.get_json()["error"] == CANCELLATION_POLICY

    hall = client.get(f"/api/attendee/events/{event['id']}/seats")
    assert hall.status_code == 200
    assert hall.get_json()["taken"] == sorted(booking["seat_ids"])
    assert hall.get_json()["available_count"] == event["capacity"] - 2

    page = client.get("/my-tickets")
    html = page.get_data(as_text=True)
    assert event["title"] in html
    assert "Seat A1" in html
    assert 'class="cancel-seat-btn' not in html
    assert 'class="cancel-registration-btn' not in html
    assert "Held" in html
    assert CANCELLATION_POLICY in html
    assert 'data-cancellable="false"' in html
    blocked_seat = client.post(
        f"/api/attendee/tickets/{booking['id']}/cancel",
        json={"seat_ids": [booking["seat_ids"][0]]},
    )
    assert blocked_seat.status_code == 403
    assert blocked_seat.get_json()["error"] == CANCELLATION_POLICY


def test_cancel_registration_before_48_hours_releases_seats(client, speaker_headers, event_payload):
    event, booking = _book_session(
        client,
        speaker_headers,
        event_payload,
        "att-cancel-early",
        days_ahead=5,
        seat_ids=["B3", "C4"],
        title="Far enough to cancel",
    )
    page = client.get("/my-tickets")
    html = page.get_data(as_text=True)
    assert event["title"] in html
    assert 'class="cancel-seat-btn' in html
    assert 'class="cancel-registration-btn' in html
    assert "Seat B3" in html
    assert "Seat C4" in html
    assert 'data-cancellable="true"' in html
    assert booking["id"] in html

    cancelled = client.post(f"/api/attendee/tickets/{booking['id']}/cancel")
    assert cancelled.status_code == 200
    body = cancelled.get_json()
    assert body["id"] == booking["id"]
    assert body["status"] == "cancelled"
    assert body["seats"] == 2
    assert body["seat_ids"] == ["B3", "C4"]
    assert body["remaining_seats"] == event["capacity"]
    assert body["seats_booked"] == 0

    hall = client.get(f"/api/attendee/events/{event['id']}/seats")
    assert hall.status_code == 200
    payload = hall.get_json()
    assert payload["taken"] == []
    assert payload["available_count"] == event["capacity"]
    by_id = {seat["id"]: seat for seat in payload["seats"]}
    assert by_id["B3"]["available"] is True
    assert by_id["C4"]["available"] is True

    from services.auth import admin_organizer_id

    admin_view = client.get(
        f"/api/organizer/events/{event['id']}",
        headers={"X-Organizer-Id": admin_organizer_id()},
    )
    assert admin_view.status_code == 200
    assert admin_view.get_json()["open_seats"] == event["capacity"]
    assert admin_view.get_json()["sold_seats"] == 0

    tickets = client.get("/my-tickets")
    tickets_html = tickets.get_data(as_text=True)
    assert event["title"] not in tickets_html
    assert "You haven't registered for any events yet." in tickets_html

    again = client.post(
        "/api/attendee/tickets",
        json={"event_id": event["id"], "seat_ids": ["B3", "C4"]},
    )
    assert again.status_code == 201
    assert again.get_json()["seat_ids"] == ["B3", "C4"]


def test_cancel_single_seat_keeps_remaining_tickets(client, speaker_headers, event_payload):
    event, booking = _book_session(
        client,
        speaker_headers,
        event_payload,
        "att-cancel-one-seat",
        days_ahead=5,
        seat_ids=["B3", "C4", "D5"],
        title="Partial seat cancel",
    )
    unknown = client.post(
        f"/api/attendee/tickets/{booking['id']}/cancel",
        json={"seat_ids": ["Z9"]},
    )
    assert unknown.status_code == 400
    assert "not on this registration" in unknown.get_json()["error"]

    partial = client.post(
        f"/api/attendee/tickets/{booking['id']}/cancel",
        json={"seat_ids": ["C4"]},
    )
    assert partial.status_code == 200
    body = partial.get_json()
    assert body["status"] == "confirmed"
    assert body["seats"] == 2
    assert body["seat_ids"] == ["B3", "D5"]
    assert body["remaining_seats"] == event["capacity"] - 2
    assert body["seats_booked"] == 2

    hall = client.get(f"/api/attendee/events/{event['id']}/seats")
    payload = hall.get_json()
    assert payload["taken"] == ["B3", "D5"]
    assert payload["available_count"] == event["capacity"] - 2
    by_id = {seat["id"]: seat for seat in payload["seats"]}
    assert by_id["C4"]["available"] is True
    assert by_id["B3"]["available"] is False
    assert by_id["D5"]["available"] is False

    from services.auth import admin_organizer_id

    admin_view = client.get(
        f"/api/organizer/events/{event['id']}",
        headers={"X-Organizer-Id": admin_organizer_id()},
    )
    assert admin_view.get_json()["sold_seats"] == 2
    assert admin_view.get_json()["open_seats"] == event["capacity"] - 2

    page = client.get("/my-tickets")
    html = page.get_data(as_text=True)
    assert event["title"] in html
    assert "2 tickets" in html
    assert "Seat B3" in html
    assert "Seat D5" in html
    assert "Seat C4" not in html

    last = client.post(
        f"/api/attendee/tickets/{booking['id']}/cancel",
        json={"seat_ids": ["B3", "D5"]},
    )
    assert last.status_code == 200
    assert last.get_json()["status"] == "cancelled"
    assert last.get_json()["seats"] == 0
    assert last.get_json()["remaining_seats"] == event["capacity"]
    leftover = client.get("/my-tickets")
    assert event["title"] not in leftover.get_data(as_text=True)


def test_cancel_registration_requires_owner(client, speaker_headers, event_payload):
    event, booking = _book_session(
        client,
        speaker_headers,
        event_payload,
        "att-cancel-owner",
        days_ahead=5,
        seats=1,
        title="Owner only cancel",
    )
    client.post(
        "/register",
        json={"user_id": "att-cancel-other", "password": "SecurePass1", "role": "attendee"},
    )
    stolen = client.post(f"/api/attendee/tickets/{booking['id']}/cancel")
    assert stolen.status_code == 403
    assert "does not belong" in stolen.get_json()["error"]

    hall = client.get(f"/api/attendee/events/{event['id']}/seats")
    assert hall.get_json()["available_count"] == event["capacity"] - 1


def test_cancel_registration_requires_attendee_identity(client, speaker_headers, event_payload):
    _event, booking = _book_session(
        client,
        speaker_headers,
        event_payload,
        "att-cancel-anon",
        days_ahead=5,
        seats=1,
        title="Needs sign in",
    )
    client.post("/logout")
    response = client.post(f"/api/attendee/tickets/{booking['id']}/cancel")
    assert response.status_code == 400
    assert "attendee" in response.get_json()["error"].lower()


def test_waitlist_requires_sold_out_event(client, speaker_headers, event_payload):
    event, _booking = _book_session(
        client,
        speaker_headers,
        event_payload,
        "att-wait-open",
        days_ahead=5,
        seats=1,
        title="Still has seats",
    )
    blocked = client.post(
        "/api/attendee/waitlist",
        json={"event_id": event["id"], "seats": 2},
        headers={"X-Attendee-Id": "att-wait-open-other"},
    )
    assert blocked.status_code == 409
    assert "open seats" in blocked.get_json()["error"]


def test_waitlist_join_and_fcfs_claim_after_cancel(client, speaker_headers, event_payload):
    event, booking = _book_session(
        client,
        speaker_headers,
        event_payload,
        "att-wait-full",
        days_ahead=5,
        seats=event_payload["capacity"],
        title="Waitlist packed hall",
    )
    page = client.get("/events")
    assert "Join Waitlist" in page.get_data(as_text=True)
    client.post("/logout")

    first = client.post(
        "/api/attendee/waitlist",
        json={"event_id": event["id"], "seats": 3},
        headers={"X-Attendee-Id": "att-wait-first"},
    )
    assert first.status_code == 201, first.get_json()
    assert first.get_json()["seats_requested"] == 3
    assert first.get_json()["status"] == "waiting"

    second = client.post(
        "/api/attendee/waitlist",
        json={"event_id": event["id"], "seats": 2},
        headers={"X-Attendee-Id": "att-wait-second"},
    )
    assert second.status_code == 201

    duplicate = client.post(
        "/api/attendee/waitlist",
        json={"event_id": event["id"], "seats": 1},
        headers={"X-Attendee-Id": "att-wait-first"},
    )
    assert duplicate.status_code == 409

    released = client.post(
        f"/api/attendee/tickets/{booking['id']}/cancel",
        json={"seat_ids": booking["seat_ids"][:2]},
        headers={"X-Attendee-Id": "att-wait-full"},
    )
    assert released.status_code == 200
    assert released.get_json()["remaining_seats"] == 2

    from models.chat_message import ChatMessage

    notices = ChatMessage.query.filter_by(kind="waitlist_offer", event_id=event["id"]).all()
    assert {row.recipient_id for row in notices} == {"att-wait-first", "att-wait-second"}

    claimed = client.post(
        f"/api/attendee/waitlist/{event['id']}/claim",
        json={"seats": 3},
        headers={"X-Attendee-Id": "att-wait-first"},
    )
    assert claimed.status_code == 201, claimed.get_json()
    assert claimed.get_json()["seats"] == 2
    assert claimed.get_json()["remaining_seats"] == 0
    assert claimed.get_json()["status"] == "confirmed"

    lost = client.post(
        f"/api/attendee/waitlist/{event['id']}/claim",
        json={"seats": 1},
        headers={"X-Attendee-Id": "att-wait-second"},
    )
    assert lost.status_code == 409
    assert "already claimed" in lost.get_json()["error"]

    hall = client.get(f"/api/attendee/events/{event['id']}/seats")
    assert hall.get_json()["available_count"] == 0
    taken = set(hall.get_json()["taken"])
    assert set(claimed.get_json()["seat_ids"]).issubset(taken)

    client.post(
        "/register",
        json={"user_id": "att-wait-first", "password": "SecurePass1", "role": "attendee"},
    )
    mine = client.get("/my-tickets")
    mine_html = mine.get_data(as_text=True)
    assert "Waitlist packed hall" in mine_html
    assert "2 tickets" in mine_html
    assert "Seats available" in mine_html or "Claim seats" in mine_html or "Your tickets" in mine_html


def test_group_seats_suggests_compact_block(client, created_event):
    response = client.post(
        f"/api/attendee/events/{created_event['id']}/group-seats",
        json={"seats": 4},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["mode"] == "block"
    assert body["needs_confirm"] is False
    assert len(body["seat_ids"]) == 4
    numbers = [int("".join(ch for ch in seat if ch.isdigit())) for seat in body["seat_ids"]]
    assert max(numbers) <= 5 or min(numbers) >= 6


def test_group_seats_blocks_oversized_group(client, attendee_headers, created_event):
    booked = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seats": created_event["capacity"] - 2},
        headers=attendee_headers,
    )
    assert booked.status_code == 201
    response = client.post(
        f"/api/attendee/events/{created_event['id']}/group-seats",
        json={"seats": 5},
    )
    assert response.status_code == 409
    assert "enough places" in response.get_json()["error"]


def test_group_seats_prompts_before_dispersed_layout(client, attendee_headers, created_event):
    from services.seating import hall_seat_ids

    keep = {"A1", "A2", "A6", "A7"}
    taken = [seat for seat in hall_seat_ids(created_event["capacity"]) if seat not in keep]
    booked = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seat_ids": taken},
        headers=attendee_headers,
    )
    assert booked.status_code == 201, booked.get_json()
    response = client.post(
        f"/api/attendee/events/{created_event['id']}/group-seats",
        json={"seats": 4},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["mode"] == "dispersed"
    assert body["needs_confirm"] is True
    assert set(body["seat_ids"]) == keep
    assert "block" in body["message"].lower()


def test_group_seats_rejects_single_seat_request(client, created_event):
    response = client.post(
        f"/api/attendee/events/{created_event['id']}/group-seats",
        json={"seats": 1},
    )
    assert response.status_code == 400
    assert "2 or more" in response.get_json()["error"]
