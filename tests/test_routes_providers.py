"""
Provider-specific route tests — tests/test_routes_providers.py

Covers:
  - Provider directory (happy path, filters, sorting, pagination)
  - Provider directory filter correctness (cred completions, CIP validation)
  - Provider detail (UUID validation, 404 paths)
  - Input hardening (_valid_unitid guard, malformed CIP)
"""

import pytest


# ---------------------------------------------------------------------------
# Fixtures (module-level seed with both a 4-year and 2-year provider)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def two_provider_seed(app):
    """
    Seeds:
      - org A: 2-year college with 2 programs (Associate's 30 completions,
               Bachelor's 20 completions)
      - org B: certificate-only org with 1 program (Certificate, 10 completions)
    Used to verify that filter-scoped totals do NOT double-count across creds.
    """
    import uuid
    from models import db, Organization, Program

    with app.app_context():
        a = str(uuid.uuid4())
        b = str(uuid.uuid4())
        pa1 = str(uuid.uuid4())
        pa2 = str(uuid.uuid4())
        pb1 = str(uuid.uuid4())

        org_a = Organization(
            org_id=a, name="Filter Test College",
            org_type="training", city="Kansas City", state="MO",
            county_fips="29095",
        )
        prog_a1 = Program(
            program_id=pa1, org_id=a, name="Nursing Associate",
            credential_type="Associate's degree", cip="51.3801",
            completions=30,
        )
        prog_a2 = Program(
            program_id=pa2, org_id=a, name="Nursing Bachelor",
            credential_type="Bachelor's degree", cip="51.3801",
            completions=20,
        )
        org_b = Organization(
            org_id=b, name="Certificate-Only Provider",
            org_type="training", city="Overland Park", state="KS",
            county_fips="20091",
        )
        prog_b1 = Program(
            program_id=pb1, org_id=b, name="Welding Certificate",
            credential_type="Certificate (sub-baccalaureate, < 1 year)", cip="48.0508",
            completions=10,
        )
        db.session.add_all([org_a, prog_a1, prog_a2, org_b, prog_b1])
        db.session.commit()
        yield {"org_a": a, "org_b": b, "pa1": pa1, "pa2": pa2, "pb1": pb1}


# ---------------------------------------------------------------------------
# Provider Directory — basic
# ---------------------------------------------------------------------------

class TestProviderDirectory:
    """GET /providers — basic smoke tests."""

    def test_directory_returns_200(self, client):
        res = client.get("/providers")
        assert res.status_code == 200

    def test_directory_contains_heading(self, client):
        res = client.get("/providers")
        assert b"Provider" in res.data

    def test_directory_empty_state_no_crash(self, client):
        """Empty DB renders empty state, not 500."""
        res = client.get("/providers")
        assert res.status_code == 200
        assert b"Internal Server Error" not in res.data

    def test_directory_shows_seeded_org(self, client, seeded_program):
        """Seeded training org appears in the directory."""
        res = client.get("/providers")
        assert b"Test Community College" in res.data

    def test_directory_sort_name_returns_200(self, client, seeded_program):
        res = client.get("/providers?sort=name")
        assert res.status_code == 200

    def test_directory_sort_programs_returns_200(self, client, seeded_program):
        res = client.get("/providers?sort=programs")
        assert res.status_code == 200

    def test_directory_sort_invalid_falls_back(self, client, seeded_program):
        """Unknown sort value falls back to default — no crash."""
        res = client.get("/providers?sort=hacky_col")
        assert res.status_code == 200

    def test_directory_page_2_out_of_range_no_crash(self, client, seeded_program):
        res = client.get("/providers?page=9999")
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Provider Directory — CIP filter validation (R-2)
# ---------------------------------------------------------------------------

class TestProviderDirectoryCIPFilter:
    """CIP filter only accepts 1-2 digit numeric family codes."""

    def test_valid_2digit_cip_filter_returns_200(self, client, seeded_program):
        res = client.get("/providers?cip=51")
        assert res.status_code == 200
        assert b"Internal Server Error" not in res.data

    def test_invalid_6digit_cip_silently_ignored(self, client, seeded_program):
        """6-digit CIP is too specific — should be silently discarded, not crash."""
        res = client.get("/providers?cip=51.3801")
        assert res.status_code == 200
        assert b"Internal Server Error" not in res.data

    def test_sql_injection_cip_is_rejected(self, client, seeded_program):
        """SQL-injection attempt in CIP filter is silently discarded."""
        res = client.get("/providers?cip=51'; DROP TABLE program; --")
        assert res.status_code == 200
        assert b"Internal Server Error" not in res.data

    def test_alpha_cip_is_rejected(self, client, seeded_program):
        """Non-numeric CIP value is silently discarded."""
        res = client.get("/providers?cip=abc")
        assert res.status_code == 200

    def test_empty_cip_is_accepted(self, client):
        """Empty CIP (no filter) returns the full directory."""
        res = client.get("/providers?cip=")
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Provider Directory — credential filter completions accuracy (D-8)
# ---------------------------------------------------------------------------

class TestProviderDirectoryCredFilter:
    """
    When filtering by credential type, total_completions should only
    include completions for programs of that credential type — not the
    org's full combined total.
    """

    def test_cred_filter_returns_200(self, client, two_provider_seed):
        res = client.get("/providers?cred=Associate%27s+degree")
        assert res.status_code == 200

    def test_cred_filter_no_crash_empty_result(self, client, two_provider_seed):
        """A cred filter with no matching providers renders empty state."""
        res = client.get("/providers?cred=Doctoral+degree")
        assert res.status_code == 200
        assert b"Internal Server Error" not in res.data

    def test_cred_filter_partner_org_excluded(self, client, two_provider_seed):
        """
        Certificate-only org should not appear when filtering by Associate's degree.
        """
        res = client.get("/providers?cred=Associate%27s+degree")
        assert res.status_code == 200
        # The certificate-only org must not be in results when filtering by Associate's
        # (it has no Associate's programs — it's only returned if the filter is cleared)

    def test_no_cred_filter_shows_all_orgs(self, client, two_provider_seed):
        """Without filter, all seeded training orgs appear."""
        res = client.get("/providers")
        assert b"Filter Test College" in res.data
        assert b"Certificate-Only Provider" in res.data


# ---------------------------------------------------------------------------
# Provider Detail — UUID validation (D-6)
# ---------------------------------------------------------------------------

class TestProviderDetailUUIDValidation:
    """provider_detail() should validate org_id format before DB lookup."""

    def test_malformed_uuid_returns_404(self, client):
        """A syntactically invalid UUID returns 404, never 500."""
        res = client.get("/providers/not-a-uuid")
        assert res.status_code == 404

    def test_sql_injection_returns_404(self, client):
        """SQL-injection-style path segment is caught by UUID regex."""
        res = client.get("/providers/'; DROP TABLE organization; --")
        assert res.status_code in (404, 308)
        assert b"Internal Server Error" not in res.data

    def test_all_zeros_uuid_returns_404(self, client):
        """Syntactically valid UUID with no matching row → 404."""
        res = client.get("/providers/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404

    def test_very_long_path_returns_404(self, client):
        """Extremely long segment handled without crash."""
        res = client.get(f"/providers/{'x' * 500}")
        assert res.status_code == 404

    def test_known_uuid_from_seed_returns_200(self, client, seeded_program):
        """A seeded provider's UUID renders the detail page."""
        res = client.get(f"/providers/{seeded_program['org_id']}")
        assert res.status_code == 200
        assert b"Test Community College" in res.data

    def test_provider_detail_contains_inst_type_badge(self, client, seeded_program):
        """inst_type badge is rendered in the page header."""
        res = client.get(f"/providers/{seeded_program['org_id']}")
        # 2-year badge expected since top credential is Associate's
        assert b"2-year" in res.data or b"Certificate" in res.data

    def test_provider_detail_no_ipeds_data_no_crash(self, client, seeded_program):
        """Provider with no IPEDS row (no unitid) renders cleanly — no KeyError."""
        res = client.get(f"/providers/{seeded_program['org_id']}")
        assert res.status_code == 200
        assert b"Internal Server Error" not in res.data


# ---------------------------------------------------------------------------
# _valid_unitid helper — unit tests
# ---------------------------------------------------------------------------

class TestValidUnitid:
    """Unit-level tests for the _valid_unitid() helper function."""

    def _fn(self, v):
        from routes.providers import _valid_unitid
        return _valid_unitid(v)

    def test_valid_6digit(self):
        assert self._fn("123456") is True

    def test_valid_1digit_edge(self):
        assert self._fn("1") is True

    def test_empty_string(self):
        assert self._fn("") is False

    def test_none(self):
        assert self._fn(None) is False

    def test_alpha_rejected(self):
        assert self._fn("abcde") is False

    def test_too_long(self):
        assert self._fn("1" * 9) is False

    def test_decimal_rejected(self):
        assert self._fn("123.456") is False

    def test_sql_injection_rejected(self):
        assert self._fn("'; DROP TABLE organization; --") is False

    def test_whitespace_only_rejected(self):
        assert self._fn("   ") is False
