from services.event_covers import cover_image_url, cover_keyword


def test_cover_keyword_maps_topics():
    assert cover_keyword("ai") == "ai"
    assert cover_keyword("architecture") == "architecture"
    assert cover_keyword("community") == "community"
    assert cover_keyword("Zero-Trust Ticketing") == "technology"
    assert cover_keyword("Hands-on workshop") == "workshop"
    assert cover_keyword("community", "AI Ethics Roundtable") == "community"
    assert cover_keyword("unknown") == "technology"


def test_cover_image_url_uses_unsplash_cdn():
    url = cover_image_url("ai", seed="evt-open-keynote")
    assert url.startswith("https://images.unsplash.com/photo-")
    assert "topic=ai" in url
    assert cover_image_url("ai", seed="evt-open-keynote") == url
