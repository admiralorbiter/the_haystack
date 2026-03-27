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


# ---------------------------------------------------------------------------
# Admin routes (Epic 2.5)
# ---------------------------------------------------------------------------
class TestAdminDashboard:
    """Admin dashboard — /admin (no auth, local dev only)."""

    def test_admin_dashboard_returns_200(self, client):
        """Happy path: the admin dashboard loads."""
        res = client.get("/admin/")
        assert res.status_code == 200

    def test_admin_dashboard_contains_row_counts(self, client):
        """Dashboard renders the row count section."""
        res = client.get("/admin/")
        assert b"Live Row Counts" in res.data

    def test_admin_dashboard_contains_dataset_sources(self, client):
        """Dataset sources section is present (may be empty in test DB)."""
        res = client.get("/admin/")
        assert b"Dataset Sources" in res.data

    def test_admin_dashboard_contains_loader_runner(self, client):
        """Loader runner section is present."""
        res = client.get("/admin/")
        assert b"Run a Loader" in res.data


class TestAdminDataExplorer:
    """Raw data explorer — /admin/data/<table_slug>."""

    def test_organizations_table_returns_200(self, client):
        """Happy path: organizations table page loads."""
        res = client.get("/admin/data/organizations")
        assert res.status_code == 200

    def test_programs_table_returns_200(self, client):
        """Happy path: programs table page loads."""
        res = client.get("/admin/data/programs")
        assert res.status_code == 200

    def test_occupations_table_returns_200(self, client):
        """Happy path: occupations table page loads."""
        res = client.get("/admin/data/occupations")
        assert res.status_code == 200

    def test_program_occupations_table_returns_200(self, client):
        """Happy path: program-occupations table page loads."""
        res = client.get("/admin/data/program-occupations")
        assert res.status_code == 200

    def test_empty_db_shows_empty_state_not_500(self, client):
        """Edge case: empty test DB renders the empty state, never 500."""
        res = client.get("/admin/data/organizations")
        assert res.status_code == 200
        # Ensure we didn't get an internal server error template
        assert b"Internal Server Error" not in res.data

    def test_out_of_range_page_renders_200(self, client):
        """Edge case: a page number far beyond the last page clamps safely."""
        res = client.get("/admin/data/organizations?page=9999")
        assert res.status_code == 200

    def test_invalid_sort_column_falls_back_gracefully(self, client):
        """Edge case: unknown sort column falls back to PK sort — no crash."""
        res = client.get("/admin/data/organizations?sort=nonexistent_column")
        assert res.status_code == 200

    def test_sort_direction_asc_returns_200(self, client):
        """Happy path: explicit sort with a valid column and direction."""
        res = client.get("/admin/data/organizations?sort=name&dir=asc")
        assert res.status_code == 200

    def test_sort_direction_desc_returns_200(self, client):
        """Happy path: descending sort works."""
        res = client.get("/admin/data/organizations?sort=name&dir=desc")
        assert res.status_code == 200

    def test_invalid_table_slug_returns_404(self, client):
        """Error path: unknown table slug → 404, never 500."""
        res = client.get("/admin/data/not-a-real-table")
        assert res.status_code == 404

    def test_sql_injection_slug_returns_404(self, client):
        """Error path: SQL-injection-style slug is rejected cleanly."""
        res = client.get("/admin/data/'; DROP TABLE organization; --")
        assert res.status_code in (404, 308)


# ---------------------------------------------------------------------------
# Program routes (Epic 4)
# ---------------------------------------------------------------------------

class TestProgramDirectory:
    """Program directory — GET /programs"""

    def test_programs_directory_returns_200(self, client):
        """Happy path: directory loads with empty test DB."""
        res = client.get("/programs")
        assert res.status_code == 200

    def test_programs_directory_contains_heading(self, client):
        """Page contains the expected page heading."""
        res = client.get("/programs")
        assert b"Training Programs" in res.data

    def test_programs_directory_empty_db_shows_empty_state(self, client):
        """Edge case: empty DB renders empty state, never 500."""
        res = client.get("/programs")
        assert res.status_code == 200
        assert b"500" not in res.data

    def test_programs_directory_shows_programs_when_seeded(self, client, seeded_program):
        """Happy path: seeded program appears in the directory."""
        res = client.get("/programs")
        assert res.status_code == 200
        assert b"Nursing" in res.data

    def test_programs_directory_search_returns_200(self, client, seeded_program):
        """Happy path: search query param is accepted and returns 200."""
        res = client.get("/programs?q=nursing")
        assert res.status_code == 200

    def test_programs_directory_search_empty_result(self, client, seeded_program):
        """Edge case: search with no matches renders empty state, not 500."""
        res = client.get("/programs?q=xyznonexistentprogram999")
        assert res.status_code == 200
        assert b"No programs" in res.data

    def test_programs_directory_filter_by_cred(self, client, seeded_program):
        """Happy path: filter by credential type is accepted."""
        res = client.get("/programs?cred=Associate%27s+degree")
        assert res.status_code == 200

    def test_programs_directory_filter_by_cip(self, client, seeded_program):
        """Happy path: filter by CIP family is accepted."""
        res = client.get("/programs?cip=51")
        assert res.status_code == 200

    def test_programs_directory_filter_completions_high(self, client, seeded_program):
        """Happy path: completions=high filter is accepted."""
        res = client.get("/programs?comp=high")
        assert res.status_code == 200

    def test_programs_directory_filter_completions_suppressed(self, client, seeded_program):
        """Edge case: suppressed filter shows suppressed programs."""
        res = client.get("/programs?comp=suppressed")
        assert res.status_code == 200

    def test_programs_directory_sort_name(self, client, seeded_program):
        """Happy path: sort by name is accepted."""
        res = client.get("/programs?sort=name")
        assert res.status_code == 200

    def test_programs_directory_sort_provider(self, client, seeded_program):
        """Happy path: sort by provider is accepted."""
        res = client.get("/programs?sort=provider")
        assert res.status_code == 200

    def test_programs_directory_invalid_sort_falls_back(self, client, seeded_program):
        """Edge case: unknown sort param falls back to default — no crash."""
        res = client.get("/programs?sort=nonexistent_column")
        assert res.status_code == 200

    def test_programs_directory_page_2_returns_200(self, client, seeded_program):
        """Edge case: out-of-range page number clamps gracefully."""
        res = client.get("/programs?page=9999")
        assert res.status_code == 200


class TestProgramDetail:
    """Program detail — GET /programs/<program_id>"""

    def test_program_detail_returns_200(self, client, seeded_program):
        """Happy path: valid program_id renders the detail page."""
        pid = seeded_program["program_id"]
        res = client.get(f"/programs/{pid}")
        assert res.status_code == 200

    def test_program_detail_contains_snapshot(self, client, seeded_program):
        """Happy path: snapshot strip renders with completions data."""
        pid = seeded_program["program_id"]
        res = client.get(f"/programs/{pid}")
        assert b"42" in res.data  # completions value

    def test_program_detail_contains_provider_link(self, client, seeded_program):
        """Happy path: provider name/link is visible in the detail page."""
        pid = seeded_program["program_id"]
        res = client.get(f"/programs/{pid}")
        assert b"Test Community College" in res.data

    def test_program_detail_unknown_id_returns_404(self, client):
        """Error path: unknown program_id → 404, never 500."""
        res = client.get("/programs/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404

    def test_program_detail_sql_injection_id_returns_404(self, client):
        """Error path: SQL-injection-style ID is handled cleanly."""
        res = client.get("/programs/'; DROP TABLE program; --")
        assert res.status_code in (404, 308)

    def test_program_detail_too_long_id_returns_404(self, client):
        """Edge case: arbitrarily long ID doesn't cause a crash."""
        long_id = "x" * 500
        res = client.get(f"/programs/{long_id}")
        assert res.status_code == 404

    def test_suppressed_program_detail_shows_caveat(self, client, seeded_program):
        """Edge case: suppressed completions shows caveat text, not a crash."""
        sid = seeded_program["suppressed_id"]
        res = client.get(f"/programs/{sid}")
        assert res.status_code == 200
        # Page renders without crashing; completions shown as suppressed
        assert b"500" not in res.data


class TestProgramHTMXTabs:
    """HTMX tab fragments — GET /programs/<id>/tab/<tab>"""

    def _htmx_headers(self):
        return {"HX-Request": "true"}

    def test_tab_overview_returns_200(self, client, seeded_program):
        pid = seeded_program["program_id"]
        res = client.get(f"/programs/{pid}/tab/overview", headers=self._htmx_headers())
        assert res.status_code == 200

    def test_tab_occupations_returns_200(self, client, seeded_program):
        """Edge case: occupations tab with zero links renders empty state, not 500."""
        pid = seeded_program["program_id"]
        res = client.get(f"/programs/{pid}/tab/occupations", headers=self._htmx_headers())
        assert res.status_code == 200

    def test_tab_occupations_empty_state(self, client, seeded_program):
        """Edge case: zero occupation links → empty state content, not crash."""
        pid = seeded_program["program_id"]
        res = client.get(f"/programs/{pid}/tab/occupations", headers=self._htmx_headers())
        assert b"500" not in res.data

    def test_tab_outcomes_returns_200(self, client, seeded_program):
        pid = seeded_program["program_id"]
        res = client.get(f"/programs/{pid}/tab/outcomes", headers=self._htmx_headers())
        assert res.status_code == 200

    def test_tab_outcomes_suppressed_renders_notice(self, client, seeded_program):
        """Edge case: suppressed completions on outcomes tab shows notice, not crash."""
        sid = seeded_program["suppressed_id"]
        res = client.get(f"/programs/{sid}/tab/outcomes", headers=self._htmx_headers())
        assert res.status_code == 200
        assert b"500" not in res.data

    def test_tab_geography_returns_200(self, client, seeded_program):
        pid = seeded_program["program_id"]
        res = client.get(f"/programs/{pid}/tab/geography", headers=self._htmx_headers())
        assert res.status_code == 200

    def test_tab_methods_returns_200(self, client, seeded_program):
        pid = seeded_program["program_id"]
        res = client.get(f"/programs/{pid}/tab/methods", headers=self._htmx_headers())
        assert res.status_code == 200

    def test_tab_unknown_program_returns_404(self, client):
        """Error path: tab request for unknown program → 404."""
        res = client.get(
            "/programs/00000000-0000-0000-0000-000000000000/tab/overview",
            headers=self._htmx_headers()
        )
        assert res.status_code == 404
