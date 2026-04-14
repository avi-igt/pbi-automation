-- 1042 Tax Report
-- Hand-authored SQL for DB2/ARDB (BOA_PS schema)
-- Parameters are positional (?); order must match the ReportParameters sequence:
--   ? 1 → StartDate
--   ? 2 → EndDate
SELECT
    W.WINNER_ID,
    W.FIRST_NAME,
    W.LAST_NAME,
    W.SSN,
    W.PRIZE_AMOUNT,
    W.WITHHOLDING_AMOUNT,
    W.PAYMENT_DATE,
    W.GAME_NAME
FROM
    BOA_PS.WINNERS W
WHERE
    W.PAYMENT_DATE BETWEEN ? AND ?
    AND W.WITHHOLDING_AMOUNT > 0
ORDER BY
    W.PAYMENT_DATE,
    W.LAST_NAME,
    W.FIRST_NAME
