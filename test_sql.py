"""Checks that the SQL path agrees with the CSV/Python path."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from database import build_database, load_qx_sql, sql_premium
from survival_model import load_qx
from premium_calculator import (net_single_premium, level_annual_net_premium,
                                temp_annuity_due)

CSV = ROOT / "data" / "qx_clean.csv"
pytestmark = pytest.mark.skipif(not CSV.exists(), reason="data/qx_clean.csv not found")


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    conn = build_database(qx_csv=CSV, grid_csv=tmp_path_factory.mktemp("g") / "none.csv", db_path=path)
    conn.close()
    return path


def test_load_qx_sql_matches_csv(db):
    for sex in ["Males", "Females"]:
        a = load_qx(str(CSV), "Canada", sex, "2022/2024")
        b = load_qx_sql(db, "Canada", sex, "2022/2024")
        assert list(a.index) == list(b.index)
        np.testing.assert_allclose(a.values, b.values)


@pytest.mark.parametrize("sex,age,term,rate,benefit", [
    ("Males", 35, 10, 0.03, 250_000),
    ("Females", 45, 20, 0.03, 250_000),
    ("Males", 25, 15, 0.01, 100_000),
    ("Females", 65, 20, 0.07, 1_000_000),
])
def test_sql_premium_matches_python(db, sex, age, term, rate, benefit):
    from database import connect
    conn = connect(db)
    q = load_qx(str(CSV), "Canada", sex, "2022/2024")
    got = sql_premium(conn, age, term, rate, benefit, sex=sex)
    assert got["net_single_premium"] == pytest.approx(net_single_premium(q, age, term, rate, benefit))
    assert got["annuity_due"] == pytest.approx(temp_annuity_due(q, age, term, rate))
    assert got["annual_net_premium"] == pytest.approx(level_annual_net_premium(q, age, term, rate, benefit))
    conn.close()


def test_database_rejects_invalid_qx(db):
    import sqlite3
    from database import connect
    conn = connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO qx VALUES ('x','x','x',0,1.5)")
    conn.close()
