SELECT 
    TO_CHAR(txn.TXN_DATE,'DD.MM.YYYY') AS "Transaction Date",
    txn.TXN_TIME AS "Transaction time",
    txn.CLERK_NUMBER AS "Clerk No",
    txn.EXTERNAL_SERIAL_NUMBER_FORMATTED AS "Transaction ESN",
    CASE txn.ID_CARD_NUMBER
        WHEN -1 THEN NULL
        ELSE txn.ID_CARD_NUMBER
    END AS "Customer Card ID",
    txn.TXN_TYPE_DESC AS "Transaction Type",
    CASE prod.PRODUCT_NUMBER
        WHEN 61 THEN 'Instant'
        ELSE prod.PRODUCT_TYPE_DESC 
    END AS "Product Type",
    prod.PRODUCT_DESC AS "Product Name",
    CASE wag.ADDON_PRODUCT_NUMBER
        WHEN 28 THEN 67
        WHEN 27 THEN 69
        WHEN 25 THEN 76
        ELSE NULL
    END AS ADDON_NO,
    CASE wag.ADDON_PRODUCT_NUMBER
        WHEN 28 THEN 68
        ELSE NULL
    END AS ADDON_NO2,
    wag_det.BOARD_ADDON_NUMBER AS TICKET_NO,
    CASE txn.FREE_TICKET_IND
        WHEN 'T' THEN 'X'
        ELSE ''
    END AS FREE_TICKET,
    txn.RESULT_DESC AS Result,
    CASE txn.TXN_CANCELLED_IND
        WHEN 'T' THEN 'X'
        ELSE ''
    END AS CANCELLED,
    to_currency_eur(wag.TICKET_CHARGE_AMOUNT) AS "Ticket Charge Amount",
    to_currency_eur(txn.TXN_AMOUNT) AS "Total Amount"

FROM
    TXNDTL.MAIN_TXN txn
    JOIN DIMCORE.PRODUCTS prod ON
        prod.PRODUCT_KEY = txn.PRODUCT_KEY
    LEFT JOIN TXNDTL.DRAW_WAGER wag ON
        wag.DATE_KEY = txn.DATE_KEY AND wag.PRODUCT_NUMBER = txn.PRODUCT_NUMBER AND wag.SERIAL_NUMBER = txn.SERIAL_NUMBER
    LEFT JOIN TXNDTL.DRAW_WAGER_DETAIL wag_det ON
        wag_det.DATE_KEY = txn.DATE_KEY AND wag_det.PRODUCT_NUMBER = txn.PRODUCT_NUMBER AND wag_det.SERIAL_NUMBER = txn.SERIAL_NUMBER AND wag_det.BOARD_NUMBER = 1

WHERE
    txn.TXN_AMOUNT > 0
    AND txn.TXN_DATE >= #StartDate+date# AND txn.TXN_DATE <= #EndDate+date#
    ?AND TO_CHAR(txn.LOCATION_NUMBER) IN (#LocationNumbers+string#)?

ORDER BY
    txn.TXN_DATE,
    txn.TXN_TIME
;
-- Version: 1
