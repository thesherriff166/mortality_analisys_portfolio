"""SQLite layer for the mortality project.

    python src/database.py build     create data/mortality.db from the CSVs
    python src/database.py explore   run the queries in sql/explore.sql
    python src/database.py premium   price a policy in pure SQL (sql/premium.sql)
    python src/database.py build-full <raw.csv>   load the full StatCan file (all elements) into life_table
    python src/database.py analyze   validation, provincial and life-expectancy queries on life_table

The CSV-based model in survival_model.py / premium_calculator.py still works on its own;
this module adds a SQL path and lets the SQL results be checked against Python.
"""
import math
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
DB_PATH = ROOT / "data" / "mortality.db"

ELEMENT_CODES = {
    "Number of survivors at age x (lx)": "lx",
    "Number of deaths between age x and x+1 (dx)": "dx",
    "Death probability between age x and x+1 (qx)": "qx",
    "Margin of error of the death probability (m.e.(qx))": "qx_moe",
    "Probability of survival between age x and x+1 (px)": "px",
    "Number of life years lived between age x and x+1 (Lx)": "life_years",
    "Cumulative number of life years lived beyond age x (Tx)": "life_years_beyond",
    "Life expectancy (in years) at age x (ex)": "ex",
    "Margin of error of the life expectancy (m.e.(ex))": "ex_moe",
}
PROVINCES = ["Newfoundland and Labrador", "Nova Scotia", "New Brunswick", "Quebec", "Ontario",
             "Manitoba", "Saskatchewan", "Alberta", "British Columbia"]


def connect(db_path=DB_PATH):
    """Open the database. Registers LN/EXP only if this SQLite build lacks math functions."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("SELECT LN(2.0), EXP(1.0)")
    except sqlite3.OperationalError:
        conn.create_function("LN", 1, lambda v: None if v is None or v <= 0 else math.log(v))
        conn.create_function("EXP", 1, lambda v: None if v is None else math.exp(v))
    return conn


def build_database(qx_csv=None, grid_csv=None, db_path=DB_PATH):
    """Create the schema and load qx (and the sensitivity grid, if present)."""
    qx_csv = Path(qx_csv or ROOT / "data" / "qx_clean.csv")
    grid_csv = Path(grid_csv or ROOT / "data" / "sensitivity_grid.csv")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    conn.executescript((SQL_DIR / "schema.sql").read_text())
    qx = pd.read_csv(qx_csv)
    conn.executemany("INSERT INTO qx VALUES (?,?,?,?,?)", qx.itertuples(index=False, name=None))
    if grid_csv.exists():
        g = pd.read_csv(grid_csv)[["sex", "issue_age", "term", "benefit", "rate",
                                    "net_single_premium", "annual_net_premium"]]
        conn.executemany("INSERT INTO premium_grid VALUES (?,?,?,?,?,?,?)",
                         g.itertuples(index=False, name=None))
    conn.commit()
    return conn


def build_full(raw_csv, db_path=DB_PATH, chunksize=200_000):
    """Load every element of the raw StatCan file into the life_table table."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    conn.executescript((SQL_DIR / "schema_full.sql").read_text())
    cols = ["REF_DATE", "GEO", "Age group", "Sex", "Element", "VALUE"]
    for chunk in pd.read_csv(raw_csv, usecols=cols, chunksize=chunksize, encoding="utf-8-sig"):
        chunk["age"] = chunk["Age group"].str.extract(r"(\d+)")[0].astype(int)
        chunk["element"] = chunk["Element"].map(ELEMENT_CODES)
        if chunk["element"].isna().any():
            raise ValueError("Unrecognised element name in raw file")
        rows = chunk[["REF_DATE", "GEO", "Sex", "age", "element", "VALUE"]]
        conn.executemany("INSERT INTO life_table VALUES (?,?,?,?,?,?)",
                         ((a, b, c, int(d), e, None if pd.isna(f) else float(f))
                          for a, b, c, d, e, f in rows.itertuples(index=False, name=None)))
    conn.commit()
    return conn


def load_qx_sql(db_path=DB_PATH, geo="Canada", sex="Males", period="2022/2024"):
    """Same output as survival_model.load_qx, but read with a SQL query."""
    conn = connect(db_path)
    df = pd.read_sql_query(
        "SELECT age, qx FROM qx WHERE geo = ? AND sex = ? AND period = ? ORDER BY age",
        conn, params=(geo, sex, period))
    conn.close()
    if df.empty:
        raise ValueError(f"No rows for {geo}, {sex}, {period}")
    return df.set_index("age")["qx"]


def sql_premium(conn, issue_age, term, rate, benefit=250_000,
                geo="Canada", sex="Males", period="2022/2024"):
    """Net single premium, annuity-due and annual net premium computed entirely in SQL."""
    row = conn.execute((SQL_DIR / "premium.sql").read_text(), {
        "geo": geo, "sex": sex, "period": period, "x": issue_age, "n": term,
        "i": rate, "benefit": benefit}).fetchone()
    return {"net_single_premium": row[0], "annuity_due": row[1], "annual_net_premium": row[2]}


def sql_premium_interval(conn, issue_age, term, rate, bound, benefit=250_000,
                         geo="Canada", sex="Males", period="2022/2024"):
    """Annual net premium with qx shifted by `bound` x its 95% margin of error (needs life_table)."""
    return conn.execute((SQL_DIR / "premium_interval.sql").read_text(), {
        "geo": geo, "sex": sex, "period": period, "x": issue_age, "n": term,
        "i": rate, "benefit": benefit, "bound": bound}).fetchone()[0]


def provincial_premiums(conn, issue_age=35, term=10, rate=0.03, benefit=250_000, sex="Males"):
    """Annual net premium by province, with a rough 95%-interval range, all computed in SQL."""
    rows = []
    base_canada = sql_premium_interval(conn, issue_age, term, rate, 0, benefit, "Canada", sex)
    for geo in ["Canada"] + PROVINCES:
        lo, mid, hi = (sql_premium_interval(conn, issue_age, term, rate, b, benefit, geo, sex)
                       for b in (-1, 0, 1))
        rows.append({"geo": geo, "annual_net_premium": round(mid, 2), "low": round(lo, 2),
                     "high": round(hi, 2), "vs_canada": f"{mid / base_canada - 1:+.1%}"})
    return pd.DataFrame(rows)


def run_analysis(conn):
    text = (SQL_DIR / "analysis.sql").read_text()
    for block in re.split(r"^-- name:", text, flags=re.M)[1:]:
        name, _, query = block.partition("\n")
        print(f"\n== {name.strip()} ==")
        print(pd.read_sql_query(query, conn).to_string(index=False))
    for age in (35, 55):
        print(f"\n== provincial annual net premium: male age {age}, 10-year, $250,000, 3% "
              "(low/high = qx at -/+ its 95% margin, all ages together) ==")
        print(provincial_premiums(conn, issue_age=age).to_string(index=False))


def run_explore(conn):
    text = (SQL_DIR / "explore.sql").read_text()
    for block in re.split(r"^-- name:", text, flags=re.M)[1:]:
        name, _, query = block.partition("\n")
        print(f"\n== {name.strip()} ==")
        print(pd.read_sql_query(query, conn).to_string(index=False))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        c = build_database()
        print("qx rows:", c.execute("SELECT COUNT(*) FROM qx").fetchone()[0])
        print("premium_grid rows:", c.execute("SELECT COUNT(*) FROM premium_grid").fetchone()[0])
        print("wrote", DB_PATH)
    elif cmd == "build-full":
        if len(sys.argv) < 3:
            sys.exit("usage: python src/database.py build-full <path to 13100114.csv>")
        c = build_full(sys.argv[2])
        print("life_table rows:", c.execute("SELECT COUNT(*) FROM life_table").fetchone()[0])
    elif cmd == "analyze":
        run_analysis(connect())
    elif cmd == "explore":
        run_explore(connect())
    elif cmd == "premium":
        print(sql_premium(connect(), 35, 10, 0.03))
    else:
        sys.exit(f"unknown command: {cmd}")
