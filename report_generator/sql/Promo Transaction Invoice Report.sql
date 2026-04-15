SELECT
    TO_CHAR(txn.TXN_DATE,'DD.MM.YYYY') AS "Txn Date",
    txn.TXN_TIME AS "Txn Time",
    CASE 
        WHEN txn.txn_cancelled_ind = 'T' THEN 'Cancelled'
        WHEN txn.txn_hold_ind = 'T' THEN 'Hold'
        WHEN txn.txn_undone_ind = 'T' THEN 'Undone'
        ELSE ''
    END AS "Txn Status",
    txn.EXTERNAL_SERIAL_NUMBER_FORMATTED AS "Wager ESN",
    txn.LOCATION_NUMBER AS LOCATION_NO,
    loc.REGION_CODE AS REGIONAL_CENTER,
    promo.PROMO_NUMBER AS PROMOTION_ID,
    promo.PRIZE_COUPON_NUMBER AS COUPON_NO,
    prod.PRODUCT_DESC AS Product,
    to_currency_eur(promo.PRIZE_MAINGAME_AMOUNT) AS DISCOUNT_MAIN_GAME,
    to_currency_eur(CASE
        WHEN txn.PRODUCT_NUMBER <> 15 THEN promo.PRIZE_ADDON1_AMOUNT
        ELSE 0
    END) AS DISCOUNT_SPIEL_77,
    to_currency_eur(CASE
        WHEN txn.PRODUCT_NUMBER <> 15 THEN promo.PRIZE_ADDON2_AMOUNT
        ELSE 0
    END) AS DISCOUNT_SUPER_6,
    to_currency_eur(CASE
        WHEN txn.PRODUCT_NUMBER = 15 THEN promo.PRIZE_ADDON1_AMOUNT
        ELSE 0
    END) AS DISCOUNT_PLUS_5,
    to_currency_eur(promo.PRIZE_BONUS_AMOUNT) AS DISCOUNT_DSC,
    to_currency_eur(promo.PRIZE_TKTCHARGE_AMOUNT) AS DISCOUNT_TICKET_CHARGE,
    to_currency_eur(promo.PRIZE_AMOUNT) AS DISCOUNT_TOTAL,
    to_currency_eur(txn.TXN_AMOUNT) AS WAGER_AMOUNT_BEFORE_DISCOUNT,
    to_currency_eur(txn.TXN_AMOUNT - promo.PRIZE_AMOUNT) AS WAGER_AMOUNT_AFTER_DISCOUNT,
    CASE txn.RESULT_CODE
        WHEN 0 THEN ''
        ELSE txn.RESULT_DESC
    END AS REJECTION_REASON
FROM
    TXNDTL.MAIN_TXN txn
    JOIN TXNDTL.PROMOTION promo ON
        promo.DATE_KEY = txn.DATE_KEY AND promo.PRODUCT_KEY = txn.PRODUCT_KEY AND promo.SERIAL_NUMBER = txn.SERIAL_NUMBER
    JOIN DIMCORE.LOCATIONS loc ON
        txn.LOCATION_KEY = loc.LOCATION_KEY
    JOIN DIMCORE.PRODUCTS prod ON
        txn.PRODUCT_KEY = prod.PRODUCT_KEY
WHERE
    txn.TXN_TYPE_CODE = 1
    AND txn.PRODUCT_NUMBER < 25.
    AND txn.TXN_DATE >= #StartDate+date# AND txn.TXN_DATE <= #EndDate+date#
    ?AND txn.txn_cancelled_ind = #CalcelledAnyOf_T_F_Empty+string#?
    ?AND TO_CHAR(promo.PRIZE_COUPON_NUMBER) IN (#CouponNumbers+string#)?
    ?AND TO_CHAR(txn.LOCATION_NUMBER) IN (#LocationNumbers+string#)?
    ?AND txn.EXTERNAL_SERIAL_NUMBER_FORMATTED LIKE (#WagerSerial+string# || '%')?
ORDER BY
    txn.DATE_KEY,
    txn.TXN_TIME
;
-- Version: 1