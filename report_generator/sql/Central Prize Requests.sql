SELECT 
    TO_CHAR(txn.TXN_DATE,'DD.MM.YYYY') AS "Validation Date",
    txn.TXN_TIME AS "Validation time",
    txn.LOCATION_NUMBER AS "Location No",
    txn.EXTERNAL_SERIAL_NUMBER_FORMATTED AS "Validation ESN",
    link.EXTERNAL_SERIAL_NUMBER_FORMATTED AS "Wager ESN",
    to_currency_eur(txn.TXN_AMOUNT) as "Winning Amount"

FROM
    TXNDTL.MAIN_TXN txn
    LEFT OUTER JOIN TXNDTL.TXN_LNKG AS link ON
        link.DATE_KEY = txn.DATE_KEY AND link.PRODUCT_NUMBER = txn.PRODUCT_NUMBER AND link.SERIAL_NUMBER = txn.SERIAL_NUMBER AND
        link.effective_ind = 'T' AND link.lnkg_txn_type_code IN (300,302) -- (Val->Wag, Clm->Wag)

WHERE
    txn.TXN_TYPE_CODE = 3
    AND txn.ERROR_CODE = 1
    AND txn.RESULT_CODE = 0
    AND (txn.ticket_cashed_ind = 'F' OR txn.ticket_claimed_ind = 'T')
    AND txn.cash_prize_won_ind = 'T'
    AND txn.TXN_DATE >= #StartDate+date# AND txn.TXN_DATE <= #EndDate+date#

ORDER BY
    txn.TXN_DATE,
    txn.TXN_TIME
-- Version: 1
