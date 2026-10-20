-- Analysis on the full life_table. Run with:  python src/database.py analyze
-- Each query starts with a name comment line.

-- name: check_our_survival_vs_published_lx
-- Our survival from age 35 (product of 1 - qx) against StatCan's own published survivors column (lx).
-- Canada, 2022/2024. lx is published as a whole number out of 100,000, so tiny rounding gaps are expected.
WITH q AS (
    SELECT sex, age, value AS qx FROM life_table
    WHERE element = 'qx' AND geo = 'Canada' AND period = '2022/2024'
      AND sex IN ('Males', 'Females') AND age BETWEEN 35 AND 54
),
ours AS (
    SELECT sex, age + 1 AS age,
           EXP(SUM(LN(1 - qx)) OVER (PARTITION BY sex ORDER BY age)) AS surv_from_35
    FROM q
),
pub AS (
    SELECT a.sex, a.age, a.value / b.value AS published_surv_from_35
    FROM life_table a
    JOIN life_table b ON b.period = a.period AND b.geo = a.geo AND b.sex = a.sex
                     AND b.element = 'lx' AND b.age = 35
    WHERE a.element = 'lx' AND a.geo = 'Canada' AND a.period = '2022/2024'
      AND a.sex IN ('Males', 'Females')
)
SELECT o.sex,
       o.age - 35                                   AS years,
       ROUND(o.surv_from_35, 5)                     AS ours,
       ROUND(p.published_surv_from_35, 5)           AS published,
       ROUND(ABS(o.surv_from_35 - p.published_surv_from_35), 5) AS abs_gap
FROM ours o JOIN pub p ON p.sex = o.sex AND p.age = o.age
WHERE o.age - 35 IN (10, 20)
ORDER BY o.sex, years;

-- name: provinces_male_qx_at_55
-- Ranked by qx. 'canada_outside_interval' = Canada's value lies outside the province's 95% interval.
WITH p AS (
    SELECT q.geo, q.value AS qx, m.value AS moe
    FROM life_table q
    JOIN life_table m ON m.period = q.period AND m.geo = q.geo AND m.sex = q.sex
                     AND m.age = q.age AND m.element = 'qx_moe'
    WHERE q.element = 'qx' AND q.sex = 'Males' AND q.age = 55 AND q.period = '2022/2024'
),
c AS (SELECT qx AS canada_qx FROM p WHERE geo = 'Canada')
SELECT RANK() OVER (ORDER BY p.qx DESC)        AS rank_high_to_low,
       p.geo,
       p.qx,
       ROUND(p.moe, 5)                         AS margin_95,
       ROUND(p.qx / c.canada_qx, 2)            AS ratio_to_canada,
       CASE WHEN ABS(p.qx - c.canada_qx) > p.moe THEN 'yes' ELSE 'no' END AS canada_outside_interval
FROM p, c
WHERE p.geo <> 'Canada'
ORDER BY p.qx DESC;

-- name: life_expectancy_at_birth_canada_recent
WITH e AS (
    SELECT period,
           MAX(CASE WHEN sex = 'Males'   THEN value END) AS male_ex,
           MAX(CASE WHEN sex = 'Females' THEN value END) AS female_ex
    FROM life_table
    WHERE element = 'ex' AND geo = 'Canada' AND age = 0
    GROUP BY period
)
SELECT period, male_ex, female_ex,
       ROUND(female_ex - male_ex, 2)                           AS gap_years,
       ROUND(male_ex   - LAG(male_ex)   OVER (ORDER BY period), 2) AS male_change,
       ROUND(female_ex - LAG(female_ex) OVER (ORDER BY period), 2) AS female_change
FROM e
ORDER BY period DESC
LIMIT 8;

-- name: windows_where_male_life_expectancy_at_birth_fell
WITH e AS (
    SELECT period, value AS male_ex,
           value - LAG(value) OVER (ORDER BY period) AS change
    FROM life_table
    WHERE element = 'ex' AND geo = 'Canada' AND sex = 'Males' AND age = 0
)
SELECT period, male_ex, ROUND(change, 2) AS change_vs_previous_window
FROM e WHERE change < 0
ORDER BY period;

-- name: life_expectancy_at_65_by_province_both_sexes
SELECT RANK() OVER (ORDER BY e.value DESC) AS rank_high_to_low,
       e.geo,
       e.value                              AS ex_at_65,
       m.value                              AS margin_95
FROM life_table e
JOIN life_table m ON m.period = e.period AND m.geo = e.geo AND m.sex = e.sex
                 AND m.age = e.age AND m.element = 'ex_moe'
WHERE e.element = 'ex' AND e.sex = 'Both sexes' AND e.age = 65 AND e.period = '2022/2024'
  AND e.geo <> 'Canada'
ORDER BY e.value DESC;
