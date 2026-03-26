"""
Route smoke tests — tests/test_routes.py

These are the foundational pattern tests. Every new route added to the app
should have a corresponding block here following this structure:

    HAPPY PATH  → the route works and returns 200 / expected content
    EDGE CASES  → things that should work but might not (empty results, long IDs, special chars)
    ERROR PATHS → things that should return 404, 400, or a user-readable error (not 500)

To run:
    pytest -v
    pytest -v --cov=. --cov-report=term-missing
"""


# ---------------------------------------------------------------------------
# Homepage
# ---------------------------------------------------------------------------
class TestHomepage:
    def test_homepage_returns_200(self, client):
        """Happy path: the homepage loads."""
        res = client.get("/")
        assert res.status_code == 200

    def test_homepage_contains_region_heading(self, client):
        """The regional dashboard headline is present."""
        res = client.get("/")
        assert b"Kansas City" in res.data

    def test_homepage_contains_explore_section(self, client):
        """The entity gateway section exists so users can navigate."""
        res = client.get("/")
        assert b"Explore the Region" in res.data


# ---------------------------------------------------------------------------
# 404 / Error handling
# ---------------------------------------------------------------------------
class TestErrorHandlers:
    def test_unknown_route_returns_404(self, client):
        """Any unrecognised URL returns a 404, not a 500."""
        res = client.get("/this-route-does-not-exist")
        assert res.status_code == 404

    def test_404_page_contains_back_link(self, client):
        """The 404 page renders the full error template (not a bare string)."""
        res = client.get("/nonexistent")
        assert b"404" in res.data
        assert b"Back to Home" in res.data

    def test_deeply_nested_unknown_route_returns_404(self, client):
        """Deeply nested unknown paths also return 404, not 500."""
        res = client.get("/providers/9999/programs/8888/outcomes")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Provider routes (stub — these will expand in Epic 3 when DB is wired up)
# ---------------------------------------------------------------------------
class TestProviderRoutes:
    def test_providers_mock_returns_200(self, client):
        """The mock provider detail page renders without errors."""
        res = client.get("/providers/mock")
        assert res.status_code == 200

    def test_provider_detail_missing_id_returns_404(self, client):
        """A provider with a totally unknown ID returns 404, not 500."""
        res = client.get("/providers/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404

    def test_provider_id_with_special_chars_returns_404(self, client):
        """SQL injection or malformed IDs are handled cleanly — never cause 500."""
        res = client.get("/providers/'; DROP TABLE organization; --")
        assert res.status_code in (404, 308)  # 308 if Flask redirects trailing slash

    def test_provider_id_too_long_returns_404(self, client):
        """Arbitrarily long IDs don't cause a crash."""
        long_id = "x" * 500
        res = client.get(f"/providers/{long_id}")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# Stub routes (Epic 0 stubs — confirm they exist and don't 500)
# ---------------------------------------------------------------------------
class TestStubRoutes:
    """
    Stub routes return simple text until their epic is implemented.
    These tests exist to confirm the routes are registered and don't error out.
    They will be upgraded to full tests when each epic ships.
    """

    def test_guided_search_stub_returns_200(self, client):
        res = client.get("/search/guided")
        assert res.status_code == 200

    def test_briefing_page_stub_returns_200(self, client):
        res = client.get("/briefing")
        assert res.status_code == 200

    def test_briefing_add_stub_accepts_post(self, client):
        """The briefing add endpoint accepts POST and returns 200 (stub behaviour)."""
        res = client.post("/briefing/add", data={"entity_type": "org", "entity_id": "abc"})
        assert res.status_code == 200

    def test_map_route_returns_200(self, client):
        res = client.get("/map")
        assert res.status_code == 200

    def test_compare_route_returns_200(self, client):
        res = client.get("/compare/providers")
        assert res.status_code == 200
