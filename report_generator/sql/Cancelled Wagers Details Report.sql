SELECT 
    txn_can.LOCATION_NUMBER AS "Location No",
    loc_can.REGION_CODE AS REGIONAL_CENTER,
    link.EXTERNAL_SERIAL_NUMBER_FORMATTED AS "Cancellation ESN",
    txn.EXTERNAL_SERIAL_NUMBER_FORMATTED AS "Wager ESN",
    TO_CHAR(txn_can.TXN_DATE,'DD.MM.YYYY') AS "Cancellation Date",
    txn_can.TXN_TIME AS "Cancellation time",
    TO_CHAR(dt.CALENDAR_DAY_DATE,'DD.MM.YYYY') AS FIRST_DRAW_DATE,
    to_currency_eur(txn.TXN_AMOUNT) AS "Wager Amount",
    CASE txn_can.ENTRY_TYPE_DESC 
        WHEN 'Manual' THEN 'X'
        ELSE ''
    END AS Corrected,
    CASE trm_can.TERMINAL_TYPE_CODE 
        WHEN 255 THEN 'X'
        ELSE ''
    END AS Hotline

FROM
    TXNDTL.MAIN_TXN txn
    INNER JOIN TXNDTL.TXN_LNKG AS link ON
        link.DATE_KEY = txn.DATE_KEY AND link.PRODUCT_NUMBER = txn.PRODUCT_NUMBER AND link.SERIAL_NUMBER = txn.SERIAL_NUMBER AND
        link.effective_ind = 'T' AND link.lnkg_txn_type_code IN (-200) -- (Wag->Can)
    LEFT JOIN TXNDTL.MAIN_TXN AS txn_can ON
        txn_can.DATE_KEY = link.LNKG_DATE_KEY AND txn_can.PRODUCT_NUMBER = link.LNKG_PRODUCT_NUMBER AND txn_can.SERIAL_NUMBER = link.LNKG_SERIAL_NUMBER
    JOIN DIMCORE.LOCATIONS loc_can ON
        txn_can.LOCATION_KEY = loc_can.LOCATION_KEY
    JOIN DIMCORE.TERMINALS trm_can ON
        txn_can.TERMINAL_KEY = trm_can.TERMINAL_KEY
    JOIN DRAW.DRAW_INFORMATION di ON
        txn.PRODUCT_NUMBER = di.PRODUCT_NUMBER AND txn.BEGIN_DRAW_NUMBER = di.DRAW_NUMBER
    JOIN DIMCORE.DATES dt ON
        di.DATE_KEY = dt.DATE_KEY

WHERE
    txn.TXN_TYPE_CODE = 1
    AND txn.TXN_CANCELLED_IND = 'T'
    AND txn.TXN_DATE >= #StartDate+date# AND txn.TXN_DATE <= #EndDate+date#
    ?AND txn_can.LOCATION_NUMBER IN (#LocationNumber+number#)?
    ?AND loc_can.REGION_CODE IN (#RegionalCenter+string#)?

ORDER BY
    txn.TXN_DATE,
    txn.TXN_TIME
;
