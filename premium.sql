-- Net premiums for an n-year term policy, computed entirely in SQL.
-- Named parameters: :geo :sex :period :x (issue age) :n (term) :i (interest rate) :benefit
--
-- surv      = (t-1)p_x = product of (1 - q) over earlier policy years,
--             computed as EXP(running SUM of LN(1 - q)) with a window function.
-- EPV       = sum_{t=1..n} B * v^t * (t-1)p_x * q_{x+t-1}      (= net single premium)
-- annuity   = sum_{t=1..n} v^(t-1) * (t-1)p_x                  (temporary annuity-due)
WITH policy AS (
    SELECT age, qx, age - :x + 1 AS t
    FROM qx
    WHERE geo = :geo AND sex = :sex AND period = :period
      AND age BETWEEN :x AND :x + :n - 1
),
surv AS (
    SELECT t, qx,
           EXP(COALESCE(SUM(LN(1 - qx)) OVER (
                   ORDER BY t ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)) AS tm1_px
    FROM policy
)
SELECT
    SUM(:benefit * EXP(-t * LN(1 + :i)) * tm1_px * qx)              AS net_single_premium,
    SUM(EXP(-(t - 1) * LN(1 + :i)) * tm1_px)                        AS annuity_due,
    SUM(:benefit * EXP(-t * LN(1 + :i)) * tm1_px * qx)
      / SUM(EXP(-(t - 1) * LN(1 + :i)) * tm1_px)                    AS annual_net_premium
FROM surv;
