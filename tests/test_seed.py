from models.event import Event
from scripts.seed import seed_database


def test_seed_covers_open_low_sold_out_cancelled_and_deleted(app):
    with app.app_context():
        summary = seed_database(reset=True)
        assert summary["open_events"] >= 3
        assert summary["low_capacity_events"] >= 2
        assert summary["sold_out_events"] >= 2
        assert summary["cancelled_events"] >= 2
        assert summary["deleted_events"] >= 2

        events = Event.query.all()
        by_id = {event.id: event for event in events}
        assert by_id["evt-open-keynote"].remaining_seats > 10
        assert by_id["evt-open-keynote"].title
        assert by_id["evt-open-keynote"].description
        assert by_id["evt-open-keynote"].date
        assert by_id["evt-open-keynote"].start_time
        assert 0 < by_id["evt-low-observability"].remaining_seats <= 10
        assert by_id["evt-sold-memory"].remaining_seats == 0
        assert by_id["evt-sold-memory"].to_dict()["sold_out"] is True
        assert by_id["evt-cancelled-mixer"].status == "cancelled"
        assert by_id["evt-deleted-duplicate"].status == "deleted"


def test_seeded_removed_events_stay_off_the_attendee_catalog(client, app):
    with app.app_context():
        seed_database(reset=True)
    public = client.get("/api/attendee/approved").get_json()
    ids = {item["id"] for item in public}
    assert "evt-open-keynote" in ids
    assert "evt-sold-memory" in ids
    assert "evt-low-observability" in ids
    assert "evt-cancelled-mixer" not in ids
    assert "evt-deleted-duplicate" not in ids
    sold = next(item for item in public if item["id"] == "evt-sold-memory")
    assert sold["sold_out"] is True
    low = next(item for item in public if item["id"] == "evt-low-observability")
    assert low["last_seats"] is True


def test_organizer_my_events_hides_cancelled_and_deleted(client, app):
    with app.app_context():
        seed_database(reset=True)
    from services.auth import admin_organizer_id

    events = client.get("/api/organizer/events", headers={"X-Organizer-Id": admin_organizer_id()}).get_json()
    ids = {item["id"] for item in events}
    assert "evt-open-keynote" in ids
    assert "evt-cancelled-mixer" not in ids
    assert "evt-deleted-walkthrough" not in ids
    assert all(item["status"] in {"approved", "active"} for item in events)
