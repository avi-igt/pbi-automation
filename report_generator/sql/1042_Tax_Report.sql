SELECT
  date(BOA_PS.PS_PAYMENT.PAID_DATETIME ) as "Payment Paid Date",
  BOA_PS.PS_PAYMENT.PAYMENT_INSTRUMENT_ID as "Payment CheckNumber",
  PAYMENT_PRODUCT.PRODUCT_TYPE as "Product Type",
  COALESCE(TRIM(CLAIMANT_PLAYER.FIRST_NAME),'') as "Payee Player First Name",
  COALESCE(TRIM(CLAIMANT_PLAYER.LAST_NAME),'') as "Payee Player Last Name",
  COALESCE(TRIM(BOA_PS.PS_PAYMENT_PARTY_ADDRESS.LINE1),'') as "Payee Address Line1",
  ESTYPE_PAYMENT_PARTY_ADDRESS.TYPE_CODE as "Payee Address Type Code",
  ESTYPE_PAYMENT_PARTY_ADDRESS.DISPLAY_TEXT as "Payee Address Type",
  COALESCE(TRIM(BOA_PS.PS_PAYMENT_PARTY_ADDRESS.CITY),'') as "Payee Address City",
  COALESCE(TRIM(BOA_PS.PS_PAYMENT_PARTY_ADDRESS.STATE_CODE),'') as "Payee Address State",
  COALESCE(TRIM(BOA_PS.PS_PAYMENT_PARTY_ADDRESS.POSTAL_CODE),'') as "Payee Address Postal Code",
  COALESCE(TRIM(BOA_PS.DECRYPT_STRING('Ey5OsMWX4JN',PAYMENT_PARTY_PAYEE.TAX_ID)),'') as "Payee Tax ID",
  BOA_PS.PS_WINNING_DETAIL.DRAW_DATE as "Draw Date",
  sum(BOA_PS.PS_PAYMENT.PAYMENT_GROSS_AMOUNT) as "Payment Gross Amount",
  SUM(PAYMENT_DEDUCTIONS.FED_TAX) as "Fed Tax",
  SUM(PAYMENT_DEDUCTIONS.STATE_TAX) as "State Tax"
FROM
  BOA_PS.PS_PAYMENT_PARTY_ADDRESS LEFT OUTER JOIN ( 
  select
    type_code,
    c.path,
    display_text
from
    boa_dictionary.dict_type_code c,
    boa_dictionary.dict_type_code_i18n t
where
    c.path like 'common.address.type%'
    and c.path = t.path
    and active_flag = 1
    and locale = 'en_US'
  ) AS ESTYPE_PAYMENT_PARTY_ADDRESS ON BOA_PS.PS_PAYMENT_PARTY_ADDRESS.ADDRESS_TYPE=ESTYPE_PAYMENT_PARTY_ADDRESS.TYPE_CODE,
  BOA_PS.PS_PAYMENT LEFT OUTER JOIN ( 
  select
    type_code,
    c.path,
    display_text
from
    boa_dictionary.dict_type_code c,
    boa_dictionary.dict_type_code_i18n t
where
    c.path like 'ps.payment.status.%'
    and c.path = t.path
    and active_flag = 1
    and locale = 'en_US'
  ) AS ESTYPE_PMT_STATUS ON BOA_PS.PS_PAYMENT.STATUS=ESTYPE_PMT_STATUS.TYPE_CODE LEFT OUTER JOIN ( 
  select
        a.payment_oid,
        coalesce(sum(case when ag.tax_type in (1,2) then a.adjustment_amount + a.additional_withholding_amount end), 0) FED_TAX,
        coalesce(sum(case when ag.tax_type in (3,4) then a.adjustment_amount + a.additional_withholding_amount end), 0) STATE_TAX,
        coalesce(sum(case when a.adjustment_context_type = 6 then a.adjustment_amount + a.additional_withholding_amount end), 0) DEBT_SETOFF,
        coalesce(sum(case when a.adjustment_context_type = 1 then a.adjustment_amount + a.additional_withholding_amount end), 0) PRIZEAMT,
        coalesce(sum(case when a.adjustment_context_type = 1 and coalesce((a.adjustment_amount + a.additional_withholding_amount),0) >= 600  then a.adjustment_amount + a.additional_withholding_amount end), 0) REPORTABLE_PRIZEAMT,
        coalesce(sum(case when a.adjustment_context_type = 2  then a.adjustment_amount + a.additional_withholding_amount end), 0) NONPRIZEAMT,
        coalesce(sum(case when a.adjustment_context_type in ('1','2') then a.adjustment_amount + a.additional_withholding_amount end), 0) AS TOTALPRIZEAMT,
        coalesce(sum(case when a.adjustment_context_type = 2 and coalesce((a.adjustment_amount + a.additional_withholding_amount),0) >= 600  then a.adjustment_amount + a.additional_withholding_amount end), 0) REPORTABLE_NONPRIZEAMT,
        coalesce(sum(case when a.adjustment_context_type = 5 and a.adjustment_operation_type = 1 then a.adjustment_amount + a.additional_withholding_amount end), 0) Fed_Tax_Corrected
from
        boa_ps.ps_payment_adjustment a
        left outer join boa_ps.ps_agency as ag on (ag.agency_oid = a.agency_oid)
group by
        a.payment_oid
  ) AS PAYMENT_DEDUCTIONS ON PAYMENT_DEDUCTIONS.PAYMENT_OID=BOA_PS.PS_PAYMENT.PAYMENT_OID LEFT OUTER JOIN ( 
  select
    p.payment_oid,
    prod.product_id,
    prod.product_name,
    prod.product_type as product_type_code,
    tct.display_text product_type,
	(case when prod.product_type = 1 Then 'Scratch Tickets' Else prod.product_name end) as winning_product_type
from
    boa_ps.ps_payment p,
    boa_ps.ps_claim c,
    boa_ps.ps_ticket t,
    boa_ps.ps_product prod 
    left outer join (SELECT DISTINCT tc.type_code, tc.path,  tct.display_text
    FROM boa_dictionary.dict_type_code tc, boa_dictionary.dict_type_code_I18N tct
    where tc.path like 'ps.product.type.%' and tc.active_flag = 1 and tct.path = tc.path
    and tct.locale = 'en_US') tct on tct.type_code = prod.product_type
where
    --p.payment_source_type = 1 and
    c.claim_oid = p.claim_oid
    and t.claim_oid = c.claim_oid
    and prod.product_oid = t.product_oid
union all
select
    p.payment_oid,
    prod.product_id,
    prod.product_name, 
    prod.product_type as product_type_code,
    tct.display_text product_type,
	(case when prod.product_type = 1 Then 'Scratch Tickets' Else prod.product_name end) as winning_product_type
from
    boa_ps.ps_payment p,
    boa_ps.ps_annuity a,
    boa_ps.ps_winning_detail w,
    boa_ps.ps_ticket t,
    boa_ps.ps_product prod 
    left outer join (SELECT DISTINCT tc.type_code, tc.path,  tct.display_text
    FROM boa_dictionary.dict_type_code tc, boa_dictionary.dict_type_code_I18N tct
    where tc.path like 'ps.product.type.%' and tc.active_flag = 1 and tct.path = tc.path
    and tct.locale = 'en_US') tct on tct.type_code = prod.product_type 
where
    p.payment_source_type = 3
    and a.annuity_id = p.payment_source_id
    and w.winning_detail_oid = a.winning_detail_oid
    and t.ticket_oid = w.ticket_oid
    and prod.product_oid = t.product_oid
  ) AS PAYMENT_PRODUCT ON PAYMENT_PRODUCT.PAYMENT_OID=BOA_PS.PS_PAYMENT.PAYMENT_OID LEFT OUTER JOIN BOA_PS.PS_CLAIM ON BOA_PS.PS_PAYMENT.CLAIM_OID=BOA_PS.PS_CLAIM.CLAIM_OID
     LEFT OUTER JOIN BOA_PS.PS_TICKET ON BOA_PS.PS_TICKET.CLAIM_OID=BOA_PS.PS_CLAIM.CLAIM_OID
     LEFT OUTER JOIN BOA_PS.PS_WINNING_DETAIL ON BOA_PS.PS_WINNING_DETAIL.TICKET_OID=BOA_PS.PS_TICKET.TICKET_OID LEFT OUTER JOIN BOA_PS.PS_CLAIMANT ON BOA_PS.PS_CLAIM.CLAIM_OID=BOA_PS.PS_CLAIMANT.CLAIM_OID
     LEFT OUTER JOIN BOA_PS.PS_PLAYER  CLAIMANT_PLAYER ON BOA_PS.PS_CLAIMANT.PLAYER_OID=CLAIMANT_PLAYER.PLAYER_OID,
  BOA_PS.PS_PAYMENT_PARTY  PAYMENT_PARTY_PAYEE LEFT OUTER JOIN BOA_PS.PS_TAX_CATEGORY ON BOA_PS.PS_TAX_CATEGORY.TAX_CATEGORY_OID=PAYMENT_PARTY_PAYEE.TAX_CATEGORY_OID
WHERE
  ( PAYMENT_PARTY_PAYEE.PAYMENT_OID=BOA_PS.PS_PAYMENT.PAYMENT_OID  )
  AND  ( PAYMENT_PARTY_PAYEE.PAYMENT_PARTY_OID=BOA_PS.PS_PAYMENT_PARTY_ADDRESS.PAYMENT_PARTY_OID  )
  AND  ( PAYMENT_PARTY_PAYEE.PAYMENT_PARTY_ROLE IN (2,3)  )
  AND  
  (
   date(BOA_PS.PS_PAYMENT.PAID_DATETIME )  BETWEEN ?  AND  ?
   AND
   ESTYPE_PMT_STATUS.DISPLAY_TEXT  NOT IN  ( 'Reissued','Void'  )
   AND
   BOA_PS.PS_TAX_CATEGORY.CATEGORY_NAME  NOT IN  ( 'Not Provided','Foreign National'  )
  )
GROUP BY
  date(BOA_PS.PS_PAYMENT.PAID_DATETIME ), 
  BOA_PS.PS_PAYMENT.PAYMENT_INSTRUMENT_ID, 
  PAYMENT_PRODUCT.PRODUCT_TYPE, 
  COALESCE(TRIM(CLAIMANT_PLAYER.FIRST_NAME),''), 
  COALESCE(TRIM(CLAIMANT_PLAYER.LAST_NAME),''), 
  COALESCE(TRIM(BOA_PS.PS_PAYMENT_PARTY_ADDRESS.LINE1),''), 
  ESTYPE_PAYMENT_PARTY_ADDRESS.TYPE_CODE, 
  ESTYPE_PAYMENT_PARTY_ADDRESS.DISPLAY_TEXT, 
  COALESCE(TRIM(BOA_PS.PS_PAYMENT_PARTY_ADDRESS.CITY),''), 
  COALESCE(TRIM(BOA_PS.PS_PAYMENT_PARTY_ADDRESS.STATE_CODE),''), 
  COALESCE(TRIM(BOA_PS.PS_PAYMENT_PARTY_ADDRESS.POSTAL_CODE),''), 
  COALESCE(TRIM(BOA_PS.DECRYPT_STRING('Ey5OsMWX4JN',PAYMENT_PARTY_PAYEE.TAX_ID)),''), 
  BOA_PS.PS_WINNING_DETAIL.DRAW_DATE
HAVING
  sum(BOA_PS.PS_PAYMENT.PAYMENT_GROSS_AMOUNT)  >  600
