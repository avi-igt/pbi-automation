select 
    right(year(dt.CALENDAR_DAY_DATE),2) || ' / ' || dt.CALENDAR_YEAR_WEEK_NUMBER AS "Calendar Week", 
    prod.product_desc AS "Game Name",
    to_currency_eur(sum(message:command.data.eftWinner.winDet.shareAmt) / 100) AS "Total rounding diference"
from 
    txndtl.transactional_data t
    join draw.draw_information di ON
        di.product_number = t.product_number AND di.draw_number = message:command.data.eftWinner.winDet.draw
    join dimcore.dates dt ON
        dt.date_key = di.date_key
    join dimcore.products prod ON
        prod.product_number = t.product_number AND prod.product_type_code = 0
where 
    transaction_type = 9 -- TT_INCMD
    and message:command.type = 1567 -- FNCT_LOG_SYND_BREAKAGE
    AND t.txn_date >= #StartDate+date# AND t.txn_date <= #EndDate+date#
group by
    dt.CALENDAR_DAY_DATE,
    dt.CALENDAR_YEAR_WEEK_NUMBER,
    prod.product_desc
order by 
    dt.CALENDAR_DAY_DATE,
    dt.CALENDAR_YEAR_WEEK_NUMBER
;
-- Version: 1