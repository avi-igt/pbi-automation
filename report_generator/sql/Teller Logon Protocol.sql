SELECT
    txn.location_number AS LOCATION_NO,
    to_char(txn.txn_date,'DD.MM.YYYY') AS DATE,
    txn.clerk_number AS CLERK_NO,
    txn.terminal_number AS TERMINAL_NO,
    min(iff(txn.txn_sub_type_code = 1, txn.txn_time, '23:59:59')) AS LOGIN_TIME,
    CASE max(iff(txn.txn_sub_type_code = 2, txn.txn_time, '00:00:00')) 
        WHEN '00:00:00' THEN '23:59:59'
        ELSE max(iff(txn.txn_sub_type_code = 2, txn.txn_time, '00:00:00')) 
    END AS LOGOUT_TIME,
    to_char(time_from_parts(0, TIMEDIFF(minute, LOGIN_TIME, LOGOUT_TIME), 0), 'hh24:mi') AS "Session duration(hh:mm)",
    CASE
        WHEN sum(t.message:signon.fingerChksum) > 0 THEN 'Yes'
        ELSE 'No'
    END AS FINGERPRINT,
    coalesce(
        (
        SELECT to_currency_eur(sum(fd.sales_amount + fd.tktchg_amount))
            FROM financial.financial_daily fd
            WHERE fd.date_key = txn.date_key 
                AND fd.location_key = txn.location_key
                AND fd.clerk_key = txn.clerk_key
                AND fd.terminal_key = txn.terminal_key
        ),
        to_currency_eur(0)
    ) AS GROSS_SALES
FROM
    txndtl.main_txn txn
    JOIN txndtl.transactional_data t ON
        t.date_key = txn.date_key AND t.product_number = txn.product_number AND t.message:logkey.serial::INT = txn.serial_number
    JOIN dimcore.terminals ter ON
        ter.terminal_key = txn.terminal_key
WHERE
    txn.txn_type_code = 0 -- TT_ACCESS
    AND txn.txn_sub_type_code in (1,2) -- (TS_SIGNON, TS_SIGNOFF)
    AND ter.terminal_type_code < 100
    AND txn.TXN_DATE >= #StartDate+date# AND txn.TXN_DATE <= #EndDate+date#
    ?AND TO_CHAR(txn.location_number) IN (#LocationNumbers+string#)?
    ?AND TO_CHAR(txn.clerk_number) IN (#ClerkNumbers+string#)?
GROUP BY
    txn.location_number, txn.location_key,
    txn.clerk_number, txn.clerk_key,
    txn.terminal_number, txn.terminal_key,
    txn.txn_date, txn.date_key
HAVING GROSS_SALES <> '0,00 €' OR LOGOUT_TIME <> '23:59:59'
ORDER BY 
    LOCATION_NO,
    txn.txn_date,
    CLERK_NO,
    LOGIN_TIME
;
-- Version: 2