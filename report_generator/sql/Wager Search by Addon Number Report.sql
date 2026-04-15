SELECT
    txn.EXTERNAL_SERIAL_NUMBER_FORMATTED AS "Wager ESN",
    TO_CHAR(txn.TXN_DATE,'DD.MM.YYYY') AS "Wager Date",
    txn.TERMINAL_NUMBER AS "Terminal No",
    wd.BOARD_ADDON_NUMBER AS "Ticket No",
    wag.STATUS AS "Wager Status",
    TO_CHAR(txn_linked.TXN_DATE,'DD.MM.YYYY') AS "Payout Date",
    CASE 
        WHEN txn_linked.TXN_TYPE_CODE = 3 AND txn_linked.validation_from_gui_ind <> 'T' AND link.lnkg_txn_type_code = -300 THEN 'Cashed at Terminal' 
        WHEN txn_linked.TXN_TYPE_CODE = 3 AND txn_linked.validation_from_gui_ind <> 'T' AND link.lnkg_txn_type_code = -302 THEN 'Claimed at Terminal' 
        WHEN txn_linked.TXN_TYPE_CODE = 3 AND txn_linked.validation_from_gui_ind = 'T' THEN 'GUI Payout' 
        WHEN txn_linked.TXN_TYPE_CODE = 8 AND txn_linked.mail_sub_ind = 'T' THEN 'Bank transfer' 
        WHEN txn_linked.TXN_TYPE_CODE = 8 AND txn_linked.id_card_number > 0 THEN 'ID Card transfer' 
        ELSE NULL 
    END AS "Payout Type",
    txn_linked.TERMINAL_NUMBER AS "Payout Terminal No",
    SUBSTR(txn.EXTERNAL_SERIAL_NUMBER_FORMATTED, 1, 17) AS "SPA_SUBS"
FROM
    TXNDTL.DRAW_WAGER_DETAIL wd
    LEFT JOIN TXNDTL.DRAW_WAGER wag ON
        wd.DATE_KEY = wag.DATE_KEY AND wd.PRODUCT_NUMBER = wag.PRODUCT_NUMBER AND wd.SERIAL_NUMBER = wag.SERIAL_NUMBER
    LEFT JOIN TXNDTL.MAIN_TXN txn ON
        wd.DATE_KEY = txn.DATE_KEY AND wd.PRODUCT_NUMBER = txn.PRODUCT_NUMBER AND wd.SERIAL_NUMBER = txn.SERIAL_NUMBER
    LEFT OUTER JOIN TXNDTL.TXN_LNKG AS link ON
        link.DATE_KEY = txn.DATE_KEY AND link.PRODUCT_NUMBER = txn.PRODUCT_NUMBER AND link.SERIAL_NUMBER = txn.SERIAL_NUMBER AND
        link.effective_ind = 'T' AND link.lnkg_txn_type_code IN (-300,-302) -- (Wag->Val, Wag->Clm)
    LEFT OUTER JOIN TXNDTL.MAIN_TXN AS txn_linked ON
        txn_linked.DATE_KEY = link.LNKG_DATE_KEY AND txn_linked.PRODUCT_NUMBER = link.LNKG_PRODUCT_NUMBER AND txn_linked.SERIAL_NUMBER = link.LNKG_SERIAL_NUMBER
--    LEFT OUTER JOIN TXNDTL.DRAW_VALIDATION AS val_linked ON
--        val_linked.DATE_KEY = link.LNKG_DATE_KEY AND val_linked.PRODUCT_NUMBER = link.LNKG_PRODUCT_NUMBER AND val_linked.SERIAL_NUMBER = link.LNKG_SERIAL_NUMBER

WHERE
    txn.TXN_TYPE_CODE = 1
    AND txn.TXN_CANCELLED_IND <> 'T'
    AND txn.TXN_REJECTED_FLAG <> 'T'
    AND txn.TXN_DATE >= #StartDate+date# AND txn.TXN_DATE <= #EndDate+date#
    ?AND wd.BOARD_ADDON_NUMBER = #AddonNumber+number#?
    ?AND txn.LOCATION_NUMBER IN (#LocationNr+number#)?
    ?AND wag.STATUS IN (#WagerStatus+string#)?
