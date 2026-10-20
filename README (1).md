# Life Insurance Mortality Risk and Premium Pricing

An educational actuarial portfolio project: how do mortality rates vary by age and sex, and how can those differences be used to estimate the cost of a term life insurance policy?

> **Educational illustration.** All premiums here are *net* premiums built from Canadian population mortality. They are not insurance quotes and are not observed Canadian pricing.

## What this project does

1. Cleans the Statistics Canada complete life table into a tidy `qx` table.
2. Computes survival probabilities and the expected present value (EPV) of an end-of-year term life death benefit.
3. Prices a term policy: net single premium and level annual net premium, payable at the start of each year while alive.
4. Tests sensitivity to issue age (20-65), term (10/15/20 years), benefit ($100K-$1M) and interest rate (1%-7%).
5. Validates selected results independently in Excel, plus unit and consistency tests.
6. Provides an interactive Streamlit dashboard, the "Life Insurance Pricing Explorer".
7. Adds a SQLite layer: the mortality table and sensitivity grid are loaded into a database, explored with SQL (joins, window functions, `LAG`, aggregation), and the premium is recomputed in pure SQL as a third independent check.

## Data

- **Source:** Statistics Canada, Table 13-10-0114-01, *Life expectancy and other elements of the complete life table, three-year estimates, Canada, all provinces except Prince Edward Island*.
- **Periods:** 43 overlapping three-year windows, 1980/1982 to 2022/2024. The main results use **2022/2024**.
- **Geography:** Canada, plus nine provinces. PEI and the territories are not in this table.
- **Ages:** 0 to 110, single year. **Sex:** Males, Females, Both sexes.
- **Measure used:** `qx`, the probability of dying between age x and x+1. This is a **period** life table (a snapshot of mortality conditions), not a cohort table and not a forecast.
- See `data/data_source.md` for download instructions and access notes.

Cleaning checks on `qx`: 143,190 rows, no missing values, no duplicates, all values within [0, 1], all ages 0-110 present. The raw file is never modified.

## Model

For an n-year term policy with benefit B, annual effective interest rate i, issued at age x:

```
EPV (= net single premium) = sum_{t=1..n} B * (1+i)^(-t) * (t-1)p_x * q_{x+t-1}
annuity-due                = sum_{t=0..n-1} (1+i)^(-t) * t p_x
annual net premium         = EPV / annuity-due
```

where `(t-1)p_x` is the product of (1 - q) over the preceding years.

## Example results

Canada, 2022/2024, $250,000 benefit, 3% interest, annual net premium:

| Sex | Issue age | 10-year | 15-year | 20-year |
|---|---|---|---|---|
| Male | 25 | $280 | $314 | $349 |
| Male | 35 | $444 | $505 | $590 |
| Male | 45 | $790 | $958 | $1,176 |
| Male | 55 | $1,719 | $2,145 | $2,696 |
| Female | 25 | $143 | $161 | $182 |
| Female | 35 | $234 | $275 | $330 |
| Female | 45 | $460 | $567 | $710 |
| Female | 55 | $1,055 | $1,345 | $1,737 |

Patterns: premiums rise steeply with issue age and with term length; female premiums are lower than male premiums at every age shown; premiums scale in direct proportion to the benefit; moving the interest rate from 1% to 7% lowers the premium (for example, about 18.5% lower for a male aged 45 on a 20-year term). These are descriptions of the population life table, not causal claims, and sensitivity is not evidence of predictive accuracy.

## Repository structure

```
README.md
requirements.txt
data/
  data_source.md            download instructions and access notes
  raw/                      raw StatCan CSV goes here (not committed)
  qx_clean.csv              cleaned output of src/clean_data.py
  sensitivity_grid.csv      full sensitivity grid (7,728 rows)
  mortality.db              SQLite database built by src/database.py (not committed)
  excel_cross_check.xlsx    independent Excel recalculation
notebooks/
  mortality_analysis.ipynb  exploration and visualizations (outputs included)
src/
  clean_data.py             reproducible cleaning
  survival_model.py         loading qx and survival probabilities
  premium_calculator.py     EPV, annuity and premium calculations
  sensitivity.py            sensitivity grid and charts
  database.py               builds the SQLite database; SQL helpers
sql/
  schema.sql                tables, keys and CHECK constraints
  explore.sql               exploration queries (joins, window functions, LAG, GROUP BY)
  premium.sql               term premium computed entirely in SQL
tests/
  test_premiums.py          unit and consistency checks
  test_sql.py               SQL results compared with the Python results
dashboard/
  app.py                    Streamlit dashboard
figures/                    generated plots
reports/
  actuarial_project_report.pdf   3-page report
```


## Setup and reproducing the results

```bash
pip install -r requirements.txt

# 1. Put the raw file (see data/data_source.md) at data/raw/13100114.csv, then clean it
python src/clean_data.py data/raw/13100114.csv data/qx_clean.csv

# 2. Run the tests
python -m pytest -q tests

# 3. Regenerate the sensitivity grid and figures
python src/sensitivity.py

# 4. Build the SQLite database and run the SQL exploration queries
python src/database.py build
python src/database.py explore
python src/database.py premium     # prices male 35, 10-year, 3% in pure SQL

# 5. Launch the dashboard
streamlit run dashboard/app.py
```

Run every command from the repository root.

## Validation

- **Unit and consistency tests (7):** survival starts at 1, never increases and stays in [0, 1]; zero mortality gives zero EPV; premiums scale proportionally with the benefit; certain death in year one gives a premium of 1/(1+i); the term identity A¹ + vⁿ·ₙp = 1 - d·ä holds; level premium times the annuity equals the net single premium; higher interest lowers the premium. The tests use a hypothetical mortality curve, so they are independent of the data file.
- **SQL tests (6):** reading qx through SQL returns the same values as the CSV path; the premium computed entirely in SQL matches the Python net single premium, annuity-due and annual net premium for four cases (both sexes, ages 25 to 65, terms 10 to 20, rates 1% to 7%); the table's CHECK constraint rejects a qx above 1.
- **Excel cross-check:** `data/excel_cross_check.xlsx` recomputes two cases row by row with spreadsheet formulas (male 35, 10-year, and female 45, 20-year). Both match the Python results to the cent. The qx inputs come from the same cleaned file, so this checks the formulas, not the data.

## SQL layer

`python src/database.py build` creates `data/mortality.db` (SQLite, standard library only) from `data/qx_clean.csv` and `data/sensitivity_grid.csv`. The `qx` table has a primary key on (period, geo, sex, age) and a CHECK constraint keeping qx within [0, 1].

- **Exploration (`sql/explore.sql`):** data checks, a self-join for the male-to-female qx ratio, survival probabilities from a window function (`EXP(SUM(LN(1 - qx)) OVER (...))`), `LAG` to compare qx across periods, and `GROUP BY` summaries of the sensitivity grid by age band and term.
- **Pricing in SQL (`sql/premium.sql`):** survival to the start of each year is a running sum of `LN(1 - qx)` exponentiated, and the EPV, annuity-due and annual net premium are sums over the policy years. For male age 35, 10-year, $250,000 at 3% it returns $3,875.27 and $444.27, matching Python and Excel.
- The model still runs from the CSV on its own; the database is an additional path, not a requirement. The database file is rebuilt from the CSVs, so it is not committed.
- Note: survival is computed through logarithms, which requires qx below 1. This holds for the issue ages and terms used here (the highest age reached is 84); qx equals 1.0 only at age 110.

## Assumptions

- End-of-year death benefit; level premiums at the start of each year while alive.
- Constant annual effective interest rate (default 3%).
- Mortality fixed at the chosen period table for the whole policy term.
- Net premium only.

## Limitations

- **Population is not insured lives.** Insured-life mortality differs because of underwriting, selection and socioeconomic factors. Real premiums are not expected to match these.
- **No mortality improvement.** A period table is a snapshot, so a 20-year policy priced on it ignores changes in future mortality.
- **Old-age estimates are volatile.** Sparse data at the oldest ages makes those rates less reliable.
- **Overlapping windows.** Adjacent three-year periods share two years of data and are not independent observations. The 2020/2022 to 2021/2023 windows include COVID-19 years.
- **Interest rates.** A single constant rate is a simplification; real rates change over a policy's life.
- **Net premium only.** No expenses, profit, lapses, taxes, underwriting adjustments or capital requirements.
- **Coverage.** PEI and the territories are not in the source table.

## Possible extensions

Use an earlier table to project mortality and compare against later observed rates (an out-of-sample test); add a mortality-improvement assumption; compare provinces.
