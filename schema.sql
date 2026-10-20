-- Mortality database schema (SQLite). Built by src/database.py from data/qx_clean.csv.

DROP TABLE IF EXISTS qx;
CREATE TABLE qx (
    period TEXT    NOT NULL,   -- three-year window, e.g. '2022/2024'
    geo    TEXT    NOT NULL,   -- 'Canada' or a province
    sex    TEXT    NOT NULL,   -- 'Males', 'Females', 'Both sexes'
    age    INTEGER NOT NULL,   -- 0..110
    qx     REAL    NOT NULL CHECK (qx >= 0 AND qx <= 1),
    PRIMARY KEY (period, geo, sex, age)
);

DROP TABLE IF EXISTS premium_grid;
CREATE TABLE premium_grid (
    sex                TEXT    NOT NULL,
    issue_age          INTEGER NOT NULL,
    term               INTEGER NOT NULL,
    benefit            INTEGER NOT NULL,
    rate               REAL    NOT NULL,
    net_single_premium REAL    NOT NULL,
    annual_net_premium REAL    NOT NULL,
    PRIMARY KEY (sex, issue_age, term, benefit, rate)
);
