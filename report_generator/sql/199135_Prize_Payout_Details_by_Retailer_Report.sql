SELECT 
    txn.DATE_KEY AS CDC,
    txn.LOCATION_NUMBER AS "Location No",
    loc.REGION_CODE AS REGIONAL_CENTER,
    txn.EXTERNAL_SERIAL_NUMBER_FORMATTED AS "Validation ESN",
    txn_wag.EXTERNAL_SERIAL_NUMBER_FORMATTED AS "Wager ESN",
    TO_CHAR(dt.CALENDAR_DAY_DATE,'DD.MM.YYYY') AS "Win Draw Date",
    TO_CHAR(txn.TXN_DATE,'DD.MM.YYYY') AS "Validation Date",
    txn.TXN_TIME AS "Validation time",
    to_currency_eur(val.WIN_DETAIL_AMOUNT) AS "Winning Amount",
    CASE txn.ENTRY_TYPE_DESC 
        WHEN 'Manual' THEN 'X'
        ELSE ''
    END AS Corrected,
    to_currency_eur(txn_wag.TXN_AMOUNT) AS "Wager Amount"

FROM
    TXNDTL.DRAW_VALIDATION val
    JOIN TXNDTL.MAIN_TXN txn ON
        txn.DATE_KEY = val.DATE_KEY AND txn.PRODUCT_NUMBER = val.PRODUCT_NUMBER AND txn.SERIAL_NUMBER = val.SERIAL_NUMBER 
    INNER JOIN TXNDTL.TXN_LNKG AS link ON
        link.DATE_KEY = txn.DATE_KEY AND link.PRODUCT_NUMBER = txn.PRODUCT_NUMBER AND link.SERIAL_NUMBER = txn.SERIAL_NUMBER AND
        link.effective_ind = 'T' AND link.lnkg_txn_type_code IN (300) -- (Val->Wag)
    LEFT JOIN TXNDTL.MAIN_TXN AS txn_wag ON
        txn_wag.DATE_KEY = link.LNKG_DATE_KEY AND txn_wag.PRODUCT_NUMBER = link.LNKG_PRODUCT_NUMBER AND txn_wag.SERIAL_NUMBER = link.LNKG_SERIAL_NUMBER
    JOIN DIMCORE.LOCATIONS loc ON
        txn.LOCATION_KEY = loc.LOCATION_KEY
    LEFT JOIN DIMCORE.DATES dt ON
        dt.DATE_KEY = val.WIN_DETAIL_DRAW_DATE_KEY

WHERE
    txn.TXN_TYPE_CODE = 3
    AND txn.TXN_DATE >= #StartDate+date# AND txn.TXN_DATE <= #EndDate+date#
    ?AND txn.LOCATION_NUMBER IN (#LocationNumber+number#)?
    ?AND loc.REGION_CODE IN (#RegionalCenter+string#)?

ORDER BY
    txn.TXN_DATE,
    txn.TXN_TIME,
    dt.CALENDAR_DAY_DATE
;
-- Version: 1
