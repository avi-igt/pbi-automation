SELECT 
    txn.date_key AS CDC,
    loc.region_desc AS REGIONAL_CENTER,
    txn.location_number AS LOCATION_NO,
    sum(iff(txn.entry_type_code = 2, txn.undo_count, 0)) AS SCANNER_CANCELLATIONS,
    sum(iff(txn.entry_type_code = 1, txn.undo_count, 0)) AS MANUAL_CANCELLATIONS,
    coalesce(
        (
        SELECT sum(fb.count) 
            FROM financial.financial_base fb
            WHERE fb.date_key = txn.date_key AND fb.location_key = txn.location_key
                AND fb.act_type_code = 85 -- AT_HOTLINE_VAL_UNDO
        ),
        0
    ) AS HOTLINE_CANCELLATIONS
FROM 
    TXNDTL.MAIN_TXN txn
    JOIN DIMCORE.LOCATIONS loc ON 
        loc.LOCATION_KEY = txn.LOCATION_KEY
WHERE 
    txn.TXN_TYPE_CODE = 7
    AND txn.UNDO_TYPE = 3
    AND txn.TXN_DATE >= #StartDate+date# AND txn.TXN_DATE <= #EndDate+date#
    ?AND txn.LOCATION_NUMBER IN (#LocationNrs+number#)?
GROUP BY all
ORDER BY txn.location_number, txn.date_key
;
-- Version: 1
