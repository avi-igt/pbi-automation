SELECT
    txn.LOCATION_NUMBER AS "Location No",
    loc.REGION_CODE AS REGIONAL_CENTER,
    txn.DATE_KEY AS CDC_VALIDATION,
    txn.TXN_TIME AS TIME_OF_VALIDATION,
    txn.EXTERNAL_SERIAL_NUMBER_FORMATTED AS VALIDATION_ESN,
    link.EXTERNAL_SERIAL_NUMBER_FORMATTED AS WAGER_ESN,
    to_currency_eur(txn.TXN_AMOUNT) AS AMOUNT,
    txn.RESULT_DESC AS RESULT_CODE,
    prod.PRODUCT_DESC AS GAME_NAME
FROM
    TXNDTL.MAIN_TXN txn
    LEFT JOIN TXNDTL.TXN_LNKG AS link ON
        link.DATE_KEY = txn.DATE_KEY AND link.PRODUCT_NUMBER = txn.PRODUCT_NUMBER AND link.SERIAL_NUMBER = txn.SERIAL_NUMBER AND
        link.lnkg_txn_type_code IN (300, 301, 302) -- (Val->Wag, Inq->Wag, Clm->Wag)
    JOIN DIMCORE.LOCATIONS loc ON
        txn.LOCATION_KEY = loc.LOCATION_KEY
    JOIN DIMCORE.PRODUCTS prod ON
        txn.PRODUCT_KEY = prod.PRODUCT_KEY
WHERE
    txn.TXN_TYPE_CODE = 3
    AND (txn.RESULT_DESC like 'Previously%' OR txn.RESULT_DESC like '%VAL_REJ_AL%' OR txn.TXN_REJECTED_FLAG = 'T')
    AND txn.TXN_DATE >= #StartDate+date# AND txn.TXN_DATE <= #EndDate+date#
    ?AND TO_CHAR(txn.LOCATION_NUMBER) IN (#LocationNumbers+string#)?
    ?AND loc.REGION_CODE IN (#RegionalCenterNo+string#)?
ORDER BY
    txn.LOCATION_NUMBER,
    link.EXTERNAL_SERIAL_NUMBER_FORMATTED,
    txn.DATE_KEY,
    txn.TXN_TIME
;
-- Version: 1
