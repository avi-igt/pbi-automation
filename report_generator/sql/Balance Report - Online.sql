SELECT
    to_char(dt.calendar_day_date,'DD.MM.YYYY') as Date,
    prod.product_desc AS Game,
    coalesce(sum(fd.sales_count),0) AS Wagers,
    to_currency_eur(coalesce(sum(fd.sales_amount),0)) AS "Wagers Value",
    coalesce(sum(fd.cancel_count),0) AS Cancellations,
    to_currency_eur(coalesce(sum(fd.cancel_amount),0)) AS "Cancellations Value",
    coalesce(sum(fd.validation_count-fd.validation_eft_count),0)  AS "Online Validations",
    to_currency_eur(coalesce(sum(fd.validation_amount-fd.validation_eft_amount),0)) AS "Online Validations Value",
    coalesce(sum(fd.validation_eft_count),0) AS "EFT Validation",
    to_currency_eur(coalesce(sum(fd.validation_eft_amount),0)) AS "EFT Validation Value",
    coalesce(sum(fd.claim_count),0) AS Claims,
    to_currency_eur(coalesce(sum(fd.claim_amount),0)) AS "Claims Value"
FROM 
    dimcore.products prod
    JOIN dimcore.dates dt
    LEFT JOIN financial.financial_daily fd ON
        prod.product_key = fd.product_key AND dt.date_key = fd.date_key
WHERE
    prod.product_type_code = 0
    AND prod.product_number < 59
    AND dt.calendar_day_date >= #StartDate+date# AND dt.calendar_day_date <= #EndDate+date#
GROUP BY
    dt.calendar_day_date, Date,
    prod.product_number, Game
ORDER BY
    dt.calendar_day_date,
    prod.product_number
;
-- Version: 1