-- Builds one row per order from the nine raw Olist tables.
-- Run by analysis/01_build.py, which registers the raw CSV files as views first.

create or replace table order_items_agg as
select
    i.order_id,
    count(*)                                   as n_items,
    count(distinct i.seller_id)                as n_sellers,
    count(distinct i.product_id)               as n_products,
    sum(i.price)                               as gmv,
    sum(i.freight_value)                       as freight,
    max(i.shipping_limit_date)                 as ship_limit_at,
    -- the category and seller of the most expensive line stand for the order
    arg_max(coalesce(t.product_category_name_english, p.product_category_name, 'unknown'), i.price) as category,
    arg_max(i.seller_id, i.price)              as seller_id,
    arg_max(s.seller_state, i.price)           as seller_state,
    sum(p.product_weight_g) / 1000.0           as weight_kg
from items i
left join products p using (product_id)
left join cat t on t.product_category_name = p.product_category_name
left join sellers s using (seller_id)
group by 1;

create or replace table order_payments_agg as
select
    order_id,
    sum(payment_value)                         as paid,
    arg_max(payment_type, payment_value)       as pay_type,
    max(payment_installments)                  as installments
from pay
group by 1;

-- A few orders carry more than one review; keep the most recent answer.
create or replace table order_reviews_one as
select order_id, review_score, review_creation_date, review_answer_timestamp,
       (review_comment_message is not null and length(trim(review_comment_message)) > 0) as has_comment
from (
    select *, row_number() over (partition by order_id order by review_answer_timestamp desc) as rn
    from reviews
)
where rn = 1;

create or replace table fact_orders as
select
    o.order_id,
    c.customer_unique_id                       as customer_id,
    c.customer_state                           as cust_state,
    c.customer_city                            as cust_city,
    o.order_status                             as status,
    o.order_purchase_timestamp                 as purchased_at,
    o.order_approved_at                        as approved_at,
    o.order_delivered_carrier_date             as carrier_at,
    o.order_delivered_customer_date            as delivered_at,
    o.order_estimated_delivery_date            as promised_at,
    date_trunc('month', o.order_purchase_timestamp)::date as month,
    ia.n_items, ia.n_sellers, ia.n_products, ia.gmv, ia.freight, ia.ship_limit_at,
    ia.category, ia.seller_id, ia.seller_state, ia.weight_kg,
    pa.paid, pa.pay_type, pa.installments,
    r.review_score, r.has_comment, r.review_creation_date,
    -- delivery measures, in days
    date_diff('minute', o.order_purchase_timestamp, o.order_delivered_customer_date) / 1440.0 as days_to_deliver,
    date_diff('minute', o.order_purchase_timestamp, o.order_estimated_delivery_date) / 1440.0 as days_promised,
    date_diff('day', o.order_estimated_delivery_date::date, o.order_delivered_customer_date::date) as days_vs_promise,
    (o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date)            as is_late,
    date_diff('minute', o.order_purchase_timestamp, o.order_delivered_carrier_date) / 1440.0  as days_to_handoff,
    date_diff('minute', o.order_delivered_carrier_date, o.order_delivered_customer_date) / 1440.0 as days_in_transit,
    (o.order_delivered_carrier_date > ia.ship_limit_at)                                       as seller_missed_deadline,
    row_number() over (partition by c.customer_unique_id order by o.order_purchase_timestamp) as customer_order_no
from orders o
join customers c using (customer_id)
left join order_items_agg ia using (order_id)
left join order_payments_agg pa using (order_id)
left join order_reviews_one r using (order_id);
