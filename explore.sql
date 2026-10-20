-- Exploration queries. Run with:  python src/database.py explore
-- Each query starts with a name comment line.

-- name: data_checks
SELECT COUNT(*)                                   AS rows,
       COUNT(DISTINCT period)                     AS periods,
       COUNT(DISTINCT geo)                        AS geographies,
       MIN(age) || '-' || MAX(age)                AS ages,
       SUM(qx < 0 OR qx > 1)                      AS out_of_range
FROM qx;

-- name: selected_ages_male_female_ratio
SELECT m.age,
       m.qx                         AS male_qx,
       f.qx                         AS female_qx,
       ROUND(m.qx / f.qx, 2)        AS male_to_female
FROM qx m
JOIN qx f ON f.period = m.period AND f.geo = m.geo AND f.age = m.age AND f.sex = 'Females'
WHERE m.sex = 'Males' AND m.geo = 'Canada' AND m.period = '2022/2024'
  AND m.age IN (25, 35, 45, 55)
ORDER BY m.age;

-- name: survival_10_and_20_years_from_age_35_males
WITH s AS (
    SELECT age,
           EXP(SUM(LN(1 - qx)) OVER (ORDER BY age ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS cum_from_35
    FROM qx
    WHERE geo = 'Canada' AND sex = 'Males' AND period = '2022/2024' AND age BETWEEN 35 AND 54
)
SELECT ROUND(MAX(CASE WHEN age = 44 THEN cum_from_35 END), 4) AS surv_10yr,
       ROUND(MAX(CASE WHEN age = 54 THEN cum_from_35 END), 4) AS surv_20yr
FROM s;

-- name: male_qx_change_vs_previous_window_age_55
SELECT period,
       qx,
       ROUND(qx - LAG(qx) OVER (ORDER BY period), 5) AS change_vs_previous_window
FROM qx
WHERE geo = 'Canada' AND sex = 'Males' AND age = 55
ORDER BY period DESC
LIMIT 8;

-- name: average_annual_premium_by_age_band_and_term
-- (benefit 250,000 and 3% interest, from the sensitivity grid)
SELECT sex,
       CASE WHEN issue_age < 30 THEN '20-29'
            WHEN issue_age < 40 THEN '30-39'
            WHEN issue_age < 50 THEN '40-49'
            WHEN issue_age < 60 THEN '50-59'
            ELSE '60-65' END                       AS age_band,
       term,
       ROUND(AVG(annual_net_premium), 0)           AS avg_annual_net_premium
FROM premium_grid
WHERE benefit = 250000 AND ABS(rate - 0.03) < 1e-9
GROUP BY sex, age_band, term
ORDER BY sex, age_band, term;
