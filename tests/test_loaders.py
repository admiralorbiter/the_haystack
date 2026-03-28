"""
Tests for Epic 2 data loaders.

All tests use an in-memory SQLite database and fixture CSV/xlsx files.
The loaders are called directly (not via subprocess) so we can pass in
a controlled session and fixture paths, keeping tests fast and isolated.
"""

import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Project root for resolving fixture paths
FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# In-memory DB fixture shared across loader tests
# We use function scope so each test starts with a clean database.
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """Provide a fresh in-memory SQLite session for each test."""
    from models import db, Base, Region, RegionCounty

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Seed the KC MSA region so loaders can resolve county FIPS
        session.add(Region(
            region_id="kc-msa",
            name="Kansas City MSA",
            slug="kansas-city",
            default_lat=39.0997,
            default_lon=-94.5786,
            default_zoom=9,
        ))
        # Only the counties present in our fixture file
        session.add(RegionCounty(region_id="kc-msa", county_fips="29095", county_name="Jackson", state="MO"))
        session.add(RegionCounty(region_id="kc-msa", county_fips="20091", county_name="Johnson", state="KS"))
        session.commit()
        yield session


# ===========================================================================
# utils.py — unit tests
# ===========================================================================

class TestNormalizeCip:
    def test_standard_format(self):
        from loaders.utils import normalize_cip
        assert normalize_cip("51.3801") == "51.3801"

    def test_float_input(self):
        from loaders.utils import normalize_cip
        assert normalize_cip(51.3801) == "51.3801"

    def test_six_digit_no_decimal(self):
        from loaders.utils import normalize_cip
        assert normalize_cip("513801") == "51.3801"

    def test_aggregate_total_returns_none(self):
        from loaders.utils import normalize_cip
        assert normalize_cip("99") is None
        assert normalize_cip("99.0000") is None

    def test_none_input(self):
        from loaders.utils import normalize_cip
        assert normalize_cip(None) is None

    def test_float_trailing_zero(self):
        from loaders.utils import normalize_cip
        # pandas may read some CIPs as 51.38 (float) losing trailing zeros
        assert normalize_cip("51.38") == "51.38"


class TestParseCompletions:
    def test_valid_integer(self):
        from loaders.utils import parse_completions
        assert parse_completions("87") == 87

    def test_blank_string_is_null(self):
        from loaders.utils import parse_completions
        assert parse_completions("") is None

    def test_period_is_null(self):
        from loaders.utils import parse_completions
        assert parse_completions(".") is None

    def test_na_string_is_null(self):
        from loaders.utils import parse_completions
        assert parse_completions("N/A") is None

    def test_none_is_null(self):
        from loaders.utils import parse_completions
        assert parse_completions(None) is None

    def test_bad_string_is_null(self):
        from loaders.utils import parse_completions
        assert parse_completions("BAD_VALUE") is None

    def test_zero_completions_is_null(self):
        from loaders.utils import parse_completions
        # Zero completions are treated as suppressed (same as blank for our purposes)
        assert parse_completions("0") is None


class TestPadCountyFips:
    def test_standard_string(self):
        from loaders.utils import pad_county_fips
        assert pad_county_fips("29095") == "29095"

    def test_float_input(self):
        from loaders.utils import pad_county_fips
        assert pad_county_fips(29095.0) == "29095"

    def test_int_input(self):
        from loaders.utils import pad_county_fips
        assert pad_county_fips(29095) == "29095"

    def test_none_returns_none(self):
        from loaders.utils import pad_county_fips
        assert pad_county_fips(None) is None

    def test_short_code_returns_none(self):
        from loaders.utils import pad_county_fips
        assert pad_county_fips("291") is None


class TestMakeProgramName:
    def test_composes_name_from_cip_title(self):
        from loaders.utils import make_program_name
        titles = {"51.3801": "Registered Nursing/Registered Nurse"}
        name = make_program_name("51.3801", "3", titles)
        assert "Registered Nursing" in name
        assert "Associate" in name

    def test_fallback_when_cip_not_in_titles(self):
        from loaders.utils import make_program_name
        name = make_program_name("99.9999", "5", {})
        assert "CIP 99.9999" in name
        assert "Bachelor" in name


# ===========================================================================
# load_ipeds_institutions.py — integration tests
# ===========================================================================

class TestLoadInstitutions:
    """
    Tests call load_institutions() directly, injecting the fixture CSV path
    via a patched IPEDS_DIR within loaders.utils before each call.
    """

    def _run(self, session, fixture_csv=None, dry_run=False, verbose=False):
        import shutil, tempfile
        import loaders.utils as utils_mod

        fixture = fixture_csv or FIXTURES / "sample_hd.csv"
        with tempfile.TemporaryDirectory() as tmpdir:
            year_dir = Path(tmpdir) / "2023"
            year_dir.mkdir()
            shutil.copy(fixture, year_dir / "hd2023.csv")

            orig = utils_mod.IPEDS_DIR
            utils_mod.IPEDS_DIR = Path(tmpdir)
            # Force reimport of the path inside the loader function
            import importlib
            import loaders.load_ipeds_institutions as inst_mod
            orig_inst = inst_mod.IPEDS_DIR
            inst_mod.IPEDS_DIR = Path(tmpdir)
            try:
                from loaders.load_ipeds_institutions import load_institutions
                return load_institutions(
                    session, year=2023, region_slug="kansas-city",
                    dry_run=dry_run, verbose=verbose,
                )
            finally:
                utils_mod.IPEDS_DIR = orig
                inst_mod.IPEDS_DIR = orig_inst

    def test_loads_only_kc_institutions(self, db_session):
        from models import Organization
        counts = self._run(db_session)
        orgs = db_session.query(Organization).all()
        assert len(orgs) == 3
        assert counts["loaded"] == 3

    def test_out_of_region_excluded(self, db_session):
        from models import Organization
        self._run(db_session)
        names = [o.name for o in db_session.query(Organization).all()]
        assert "University of Nebraska" not in names
        assert "Iowa State University" not in names

    def test_org_alias_written(self, db_session):
        from models import OrgAlias
        self._run(db_session)
        aliases = db_session.query(OrgAlias).filter_by(source="ipeds").all()
        assert len(aliases) == 3

    def test_idempotent(self, db_session):
        from models import Organization
        self._run(db_session)
        counts2 = self._run(db_session)
        assert db_session.query(Organization).count() == 3
        assert counts2["updated"] == 3
        assert counts2["loaded"] == 0

    def test_dataset_source_written(self, db_session):
        from models import DatasetSource
        self._run(db_session)
        ds = db_session.query(DatasetSource).filter(
            DatasetSource.source_id.like("ipeds_hd_%")
        ).first()
        assert ds is not None
        assert ds.record_count == 3

    def test_dry_run_writes_nothing(self, db_session):
        from models import Organization
        self._run(db_session, dry_run=True)
        assert db_session.query(Organization).count() == 0


# ===========================================================================
# load_ipeds_programs.py — integration tests
# ===========================================================================

class TestLoadPrograms:

    def _patch_and_load_institutions(self, session):
        import shutil, tempfile
        import loaders.utils as utils_mod
        import loaders.load_ipeds_institutions as inst_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            year_dir = Path(tmpdir) / "2023"
            year_dir.mkdir()
            shutil.copy(FIXTURES / "sample_hd.csv", year_dir / "hd2023.csv")
            orig_u = utils_mod.IPEDS_DIR
            orig_i = inst_mod.IPEDS_DIR
            utils_mod.IPEDS_DIR = Path(tmpdir)
            inst_mod.IPEDS_DIR = Path(tmpdir)
            try:
                from loaders.load_ipeds_institutions import load_institutions
                load_institutions(session, year=2023, region_slug="kansas-city")
            finally:
                utils_mod.IPEDS_DIR = orig_u
                inst_mod.IPEDS_DIR = orig_i

    def _patch_and_load_programs(self, session):
        import shutil, tempfile
        import loaders.utils as utils_mod
        import loaders.load_ipeds_programs as prog_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            year_dir = Path(tmpdir) / "2023"
            year_dir.mkdir()
            shutil.copy(FIXTURES / "sample_completions.csv", year_dir / "c2023_a.csv")
            orig_u = utils_mod.IPEDS_DIR
            orig_p = prog_mod.IPEDS_DIR
            utils_mod.IPEDS_DIR = Path(tmpdir)
            prog_mod.IPEDS_DIR = Path(tmpdir)

            # Patch cip_titles to avoid needing the xlsx file
            orig_load = utils_mod.load_cip_titles
            utils_mod.load_cip_titles = lambda path=None: {
                "51.3801": "Registered Nursing",
                "11.0701": "Computer Science",
                "52.0201": "Business Administration",
                "27.0101": "Mathematics",
                "51.0000": "Health Professions Other",
            }
            try:
                from loaders.load_ipeds_programs import load_programs
                return load_programs(session, year=2023)
            finally:
                utils_mod.IPEDS_DIR = orig_u
                prog_mod.IPEDS_DIR = orig_p
                utils_mod.load_cip_titles = orig_load

    def test_programs_loaded(self, db_session):
        from models import Program
        self._patch_and_load_institutions(db_session)
        self._patch_and_load_programs(db_session)
        assert db_session.query(Program).count() > 0

    def test_cip99_totals_skipped(self, db_session):
        from models import Program
        self._patch_and_load_institutions(db_session)
        self._patch_and_load_programs(db_session)
        cips = [p.cip for p in db_session.query(Program).all()]
        assert not any(c.startswith("99") for c in cips if c)

    def test_suppressed_stored_as_null(self, db_session):
        from models import Program
        self._patch_and_load_institutions(db_session)
        self._patch_and_load_programs(db_session)
        null_programs = db_session.query(Program).filter(Program.completions.is_(None)).all()
        assert len(null_programs) > 0

    def test_majornum2_excluded(self, db_session):
        from models import Program
        self._patch_and_load_institutions(db_session)
        self._patch_and_load_programs(db_session)
        # MAJORNUM=2 row has completions=12; MAJORNUM=1 row has completions=87
        # Only the 87 row should be in DB
        nursing = db_session.query(Program).filter_by(cip="51.3801").all()
        for p in nursing:
            if p.completions is not None:
                assert p.completions != 12

    def test_out_of_region_skipped(self, db_session):
        from models import OrgAlias
        self._patch_and_load_institutions(db_session)
        self._patch_and_load_programs(db_session)
        alias = db_session.query(OrgAlias).filter_by(source="ipeds", source_id="999001").first()
        assert alias is None

    def test_idempotent(self, db_session):
        from models import Program
        self._patch_and_load_institutions(db_session)
        self._patch_and_load_programs(db_session)
        count1 = db_session.query(Program).count()
        self._patch_and_load_programs(db_session)
        assert db_session.query(Program).count() == count1

    def test_dataset_source_written(self, db_session):
        from models import DatasetSource
        self._patch_and_load_institutions(db_session)
        self._patch_and_load_programs(db_session)
        ds = db_session.query(DatasetSource).filter(
            DatasetSource.source_id.like("ipeds_c_%")
        ).first()
        assert ds is not None


# ===========================================================================
# loaders/utils.py — load_cip_titles tests
# ===========================================================================

class TestLoadCipTitles:
    def test_loads_from_csv(self, tmp_path):
        """load_cip_titles should parse the fixture CSV correctly."""
        import pandas as pd
        from loaders.utils import load_cip_titles

        # Create a minimal xlsx from the CSV fixture
        df = pd.read_csv(FIXTURES / "sample_cip_titles.csv", dtype=str)
        xlsx_path = tmp_path / "cip_titles.xlsx"
        df.to_excel(xlsx_path, index=False)

        titles = load_cip_titles(path=xlsx_path)
        assert "51.3801" in titles
        assert "Nursing" in titles["51.3801"] or "Registered" in titles["51.3801"]

    def test_missing_file_returns_empty_dict(self):
        """If the CIP titles file is absent, return {} without crashing."""
        from loaders.utils import load_cip_titles
        titles = load_cip_titles(path=Path("/nonexistent/path/cip_titles.xlsx"))
        assert titles == {}


# ===========================================================================
# load_cip_soc.py — integration tests
# ===========================================================================

class TestLoadCipSoc:
    def test_load_cip_soc_success(self, db_session):
        import pandas as pd
        from unittest.mock import patch
        from loaders.load_cip_soc import run
        from models import Organization, Program, Occupation, ProgramOccupation

        mock_df = pd.DataFrame({
            "cipcode": ["51.3801", "11.0701", "99.9999", "invalid"],
            "soccode": ["29-1141", "15-1252", "99-9999", ""],
            "soctitle": ["Registered Nurses", "Software Developers", "Unmatched", ""]
        })

        # Base program
        db_session.add(Organization(org_id="org1", name="Test Org", org_type="training", city="KC", state="MO"))
        db_session.add(Program(program_id="prog1", org_id="org1", name="Nursing", cip="51.3801", credential_type="certificate"))
        db_session.add(Program(program_id="prog2", org_id="org1", name="CS", cip="11.0701", credential_type="certificate"))
        db_session.commit()

        from unittest.mock import MagicMock
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = db_session
        
        # Need to patch CROSSWALK_FILE and Session
        with patch("pandas.read_excel", return_value=mock_df), \
             patch("loaders.load_cip_soc.CROSSWALK_FILE") as mock_file, \
             patch("loaders.load_cip_soc.Session", return_value=mock_session_ctx):
            mock_file.exists.return_value = True
            mock_file.name = "mock.xlsx"
            
            # Also test dry-run branch
            run(dry_run=True, verbose=True)
            run(dry_run=False, verbose=True)

            # Idempotency
            run(dry_run=False, verbose=False)

        occs = db_session.query(Occupation).all()
        assert len(occs) == 2

        links = db_session.query(ProgramOccupation).all()
        assert len(links) == 2
        assert len(links) == 2


# ===========================================================================
# load_scorecard.py — integration tests
# ===========================================================================

class TestLoadScorecard:
    def test_load_scorecard_main(self):
        import sys
        import pandas as pd
        from unittest.mock import patch, MagicMock
        from loaders import load_scorecard

        mock_zip_ctx = MagicMock()
        mock_zip = mock_zip_ctx.__enter__.return_value
        mock_zip.namelist.return_value = [load_scorecard.INSTITUTION_FILE, load_scorecard.FOS_FILE]
        
        mock_inst_df = pd.DataFrame({
            "UNITID": ["123456", "999999"],
            "col_good": ["A", "B"],
            "col_bad": ["NULL", "PS"]
        })
        
        mock_fos_df = pd.DataFrame({
            "UNITID": ["123456", "999999"],
            "CIPCODE": ["5101", "1107"],
            "CREDLEV": ["2", "3"]
        })
        
        mock_conn = MagicMock()

        with patch("sys.argv", ["load_scorecard.py", "--zip", "dummy.zip"]), \
             patch("loaders.load_scorecard.Path.exists", return_value=True), \
             patch("loaders.load_scorecard.sqlite3.connect", return_value=mock_conn), \
             patch("loaders.load_scorecard._get_kc_unitids", return_value={"123456"}), \
             patch("loaders.load_scorecard.zipfile.ZipFile", return_value=mock_zip_ctx), \
             patch("pandas.read_csv", side_effect=[mock_inst_df, mock_fos_df]):
             
            load_scorecard.main()
            
        assert mock_conn.close.called
