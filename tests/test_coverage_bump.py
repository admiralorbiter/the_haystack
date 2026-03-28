from unittest.mock import patch
from routes.providers import _get_ipeds_enrichment, _ipeds_outcome_measures, _ipeds_enrollment_demographics
from routes.programs import _scorecard_fos_for_program

@patch("routes.providers.db.engine.connect")
def test_ipeds_enrichment_coverage(mock_connect, app):
    with app.app_context():
        if hasattr(_get_ipeds_enrichment, "cache_clear"):
            _get_ipeds_enrichment.cache_clear()
        
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.mappings.return_value.first.return_value = {
            "CALSYS": "1", "OPENADMP": "1", "FT_UG": "1", "PT_UG": "0",
            "CHG1AT0": 5000, "CHG2AT0": 6000, "CHG4AY0": 1000, "CHG5AY0": 8000,
            "TUITVARY": "1", "NPIST2": 12000,
            "APPLCN": 1000, "ADMSSN": 500, "SATVR75": 700, "SATMT75": 750, "ACTCM75": 30,
            "EFYTOTLT": 2000, "EFYTOTLM": 1000, "EFYTOTLW": 1000, "EFYDEEXC": 500,
            "RET_PCF": 80, "RET_NMP": 70, "STUFACR": 15.5,
            "gr_150": 300, "gr_150_cohort": 500,
            "gr_pell_comp": 100, "gr_pell_adj": 200,
            "gr200_cohort": 400, "gr200_comp": 250,
            "grl2_cohort": 100, "grl2_comp": 50, "grl2_pell_cohort": 50, "grl2_pell_comp": 20,
            "sfa24_any_grant_pct": 80, "sfa24_any_grant_avg": 5000,
            "sfa24_pell_pct": 40, "sfa24_pell_avg": 4000,
            "sfa24_loan_pct": 60, "sfa24_loan_avg": 10000,
            "vet_gi_n": 50, "vet_gi_avg": 20000,
            "faculty_total": 200, "faculty_avg_salary": 90000,
            "exp_i": 1000000, "exp_a": 500000, "exp_s": 250000, "exp_finance_type": "public"
        }
        res = _get_ipeds_enrichment("123456")
        assert res["instate_tuition"] == 5000
        assert res["acceptance_rate"] == 50.0

@patch("routes.providers.db.engine.connect")
def test_ipeds_outcome_measures_coverage(mock_connect, app):
    with app.app_context():
        if hasattr(_ipeds_outcome_measures, "cache_clear"):
            _ipeds_outcome_measures.cache_clear()
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.mappings.return_value.fetchall.return_value = [
            {"OMCHRT": "1", "OMRCHRT": 100, "OMACHRT": 100, "OMAWDP8": 40},
            {"OMCHRT": "2", "OMRCHRT": 50, "OMACHRT": 50, "OMAWDP8": 20}
        ]
        res = _ipeds_outcome_measures("123456")
        assert res is not None

@patch("routes.providers.db.engine.connect")
def test_ipeds_enrollment_coverage(mock_connect, app):
    with app.app_context():
        if hasattr(_ipeds_enrollment_demographics, "cache_clear"):
            _ipeds_enrollment_demographics.cache_clear()
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_conn.execute.return_value.mappings.return_value.fetchall.return_value = [
            {"EFALEVEL": "1", "EFTOTLT": 1000, "EFTOTLM": 400, "EFTOTLW": 600, 
             "EFAIANT": 10, "EFASIAT": 50, "EFBKAAT": 100, "EFHISPT": 200, 
             "EFNHPIT": 5, "EFWHITT": 500, "EF2MORT": 50, "EFUNKNT": 50, "EFNRALT": 35}
        ]
        res = _ipeds_enrollment_demographics("123456")
        assert res is not None

@patch("routes.programs.sqlite3.connect")
def test_scorecard_fos_coverage(mock_connect, app):
    with app.app_context():
        if hasattr(_scorecard_fos_for_program, "cache_clear"):
            _scorecard_fos_for_program.cache_clear()
        mock_conn = mock_connect.return_value
        mock_cur = mock_conn.execute.return_value
        mock_cur.fetchone.return_value = (
            "51.38", "Nursing", "2", "Associate's Degree",
            50000, 55000, 100, 56000, 200, 15000, 12000, 50, 60
        )
        res = _scorecard_fos_for_program("123456", "51.3801", "Associate's degree")
        assert res is not None
        assert res["earn_1yr"] == 50000
