"""Computes every number and chart series the report uses and writes results/results.json.

Run 01_build.py first. Each block below answers one question from the report, and the
keys it writes are the names the page template refers to.
"""
import json
import numpy as np
import pandas as pd
from db import connect, RESULTS, START, END

con = connect()
R = {}

WIN = f"purchased_at >= '{START}' and purchased_at < '{END}'"
SOLD = WIN + " and status not in ('canceled', 'unavailable')"          # an order that counts as a sale
DELIV = WIN + " and status = 'delivered' and delivered_at is not null"  # an order that reached the customer


def df(sql):
    return con.execute(sql).df()


def one(sql):
    return con.execute(sql).fetchone()


def recs(frame):
    """A dataframe as a list of plain dicts that json can write."""
    out = json.loads(frame.to_json(orient="records", date_format="iso"))
    return out


# ---------------------------------------------------------------------------
# 1. The whole window at a glance
# ---------------------------------------------------------------------------
n_all, n_cust = one(f"select count(*), count(distinct customer_id) from fact_orders where {WIN}")
n_sold, sales, freight = one(f"select count(*), sum(gmv), sum(freight) from fact_orders where {SOLD}")
n_deliv, med_days, avg_days, avg_promised, late_rate, n_late = one(
    f"select count(*), median(days_to_deliver), avg(days_to_deliver), avg(days_promised), avg(is_late::int), sum(is_late::int) from fact_orders where {DELIV}")
n_rev, avg_score, low_rate, n_low, five_rate = one(
    f"select count(*), avg(review_score), avg((review_score <= 2)::int), sum((review_score <= 2)::int), avg((review_score = 5)::int) from fact_orders where {WIN} and review_score is not null")
n_sellers = one(f"select count(distinct i.seller_id) from items i join fact_orders f using (order_id) where {SOLD}")[0]
R["window"] = dict(
    months=20, orders_all=n_all, customers=n_cust, orders_sold=n_sold, sales=sales, freight=freight,
    aov=sales / n_sold, freight_share=freight / sales, delivered=n_deliv, median_days=med_days,
    avg_days=avg_days, avg_promised=avg_promised, late_rate=late_rate, late_orders=n_late,
    reviewed=n_rev, avg_score=avg_score, low_rate=low_rate, low_orders=n_low, five_rate=five_rate,
    sellers=n_sellers, one_in=1 / low_rate,
)

# ---------------------------------------------------------------------------
# 2. Month by month: sales, sellers, delivery, reviews
# ---------------------------------------------------------------------------
con.execute(f"""
create temp table seller_lines as
select i.seller_id, i.order_id, f.month, f.purchased_at, i.price
from items i join fact_orders f using (order_id)
where {SOLD}""")
con.execute("""
create temp table seller_month as
select seller_id, month, sum(price) as sales, count(distinct order_id) as orders
from seller_lines group by 1, 2""")
con.execute("""
create temp table seller_life as
select seller_id, min(month) as first_month, max(month) as last_month, count(*) as months_active,
       sum(sales) as sales, sum(orders) as orders,
       (select min(purchased_at) from seller_lines l where l.seller_id = m.seller_id) as first_sale_at
from seller_month m group by 1""")

monthly = df(f"""
with o as (
    select month, count(*) as orders, sum(gmv) as sales, sum(gmv) / count(*) as aov
    from fact_orders where {SOLD} group by 1),
s as (
    select m.month, count(*) as sellers, sum((l.first_month = m.month)::int) as new_sellers
    from seller_month m join seller_life l using (seller_id) group by 1),
d as (
    select month, median(days_to_deliver) as median_days, avg(days_promised) as promised_days,
           avg(is_late::int) as late_rate,
           avg(is_late::int) filter (where cust_state = 'RJ') as late_rio,
           avg(is_late::int) filter (where cust_state <> 'RJ') as late_rest
    from fact_orders where {DELIV} group by 1),
r as (
    select month, avg((review_score <= 2)::int) as low_rate, avg(review_score) as avg_score,
           avg((status = 'unavailable')::int) as unavailable_rate,
           avg((status <> 'delivered' or delivered_at is null)::int) as not_delivered_rate
    from fact_orders where {WIN} group by 1)
select strftime(o.month, '%Y-%m') as month, o.orders, o.sales, o.aov, s.sellers, s.new_sellers,
       o.sales / s.sellers as sales_per_seller, o.orders * 1.0 / s.sellers as orders_per_seller,
       d.median_days, d.promised_days, d.late_rate, d.late_rio, d.late_rest,
       r.low_rate, r.avg_score, r.unavailable_rate, r.not_delivered_rate
from o join s using (month) join d using (month) join r using (month) order by 1""")
R["monthly"] = recs(monthly)

mm = monthly.set_index("month")
peak_month = mm.sales.idxmax()
R["trend"] = dict(
    peak_month=peak_month, peak_sales=mm.sales.max(),
    jan17_sales=mm.loc["2017-01", "sales"], dec17_sales=mm.loc["2017-12", "sales"],
    aug18_sales=mm.loc["2018-08", "sales"], aug17_sales=mm.loc["2017-08", "sales"],
    aug_yoy=mm.loc["2018-08", "sales"] / mm.loc["2017-08", "sales"] - 1,
    h1_17=mm.loc["2017-01":"2017-03", "sales"].mean(), q4_17=mm.loc["2017-10":"2017-12", "sales"].mean(),
    growth_2017=mm.loc["2017-10":"2017-12", "sales"].mean() / mm.loc["2017-01":"2017-03", "sales"].mean(),
    months_since_peak=int((pd.Period("2018-08") - pd.Period(peak_month)).n),
)


def period(a, b):
    p = mm.loc[a:b]
    k = len(p)
    d = one(f"""select median(days_to_deliver), avg(days_promised), avg(is_late::int) from fact_orders
                where {DELIV} and month >= '{a}-01' and month <= '{b}-01'""")
    r = one(f"""select avg((review_score <= 2)::int), avg(review_score) from fact_orders
                where {WIN} and review_score is not null and month >= '{a}-01' and month <= '{b}-01'""")
    return dict(months=k, sales_pm=p.sales.sum() / k, orders_pm=p.orders.sum() / k, aov=p.sales.sum() / p.orders.sum(),
                sellers=p.sellers.mean(), sales_per_seller=p.sales.sum() / p.sellers.sum(),
                orders_per_seller=p.orders.sum() / p.sellers.sum(), new_sellers_pm=p.new_sellers.mean(),
                median_days=d[0], promised_days=d[1], late_rate=d[2], low_rate=r[0], avg_score=r[1])


P = dict(latest=period("2018-06", "2018-08"), prior=period("2018-03", "2018-05"),
         year_ago=period("2017-06", "2017-08"), q1_18=period("2018-01", "2018-03"),
         jan_may_18=period("2018-01", "2018-05"))
R["periods"] = P
R["stall"] = dict(
    sellers_change=P["latest"]["sellers"] / P["q1_18"]["sellers"] - 1,
    sales_change=P["latest"]["sales_pm"] / P["q1_18"]["sales_pm"] - 1,
    per_seller_change=P["latest"]["sales_per_seller"] / P["q1_18"]["sales_per_seller"] - 1,
    orders_change=P["latest"]["orders_pm"] / P["q1_18"]["orders_pm"] - 1,
    sellers_jan=int(mm.loc["2018-01", "sellers"]), sellers_aug=int(mm.loc["2018-08", "sellers"]),
    per_seller_jan=mm.loc["2018-01", "sales_per_seller"], per_seller_aug=mm.loc["2018-08", "sales_per_seller"],
)

# Why monthly sales fell between January-May and June-August 2018, split by what happened to each seller.
b = one("""
with a as (select seller_id, sum(sales) / 5 as s1 from seller_month where month between '2018-01-01' and '2018-05-01' group by 1),
     z as (select seller_id, sum(sales) / 3 as s2 from seller_month where month >= '2018-06-01' group by 1)
select sum(s1), sum(s2),
       count(*) filter (where s1 is not null and s2 is not null), sum(s1) filter (where s2 is not null), sum(s2) filter (where s1 is not null),
       count(*) filter (where s2 is null), sum(s1) filter (where s2 is null),
       count(*) filter (where s1 is null), sum(s2) filter (where s1 is null)
from a full join z using (seller_id)""")
R["bridge"] = dict(start=b[0], end=b[1], continuing_n=b[2], continuing_before=b[3], continuing_after=b[4],
                   continuing_delta=b[4] - b[3], continuing_pct=b[4] / b[3] - 1,
                   stopped_n=b[5], stopped_delta=-b[6], new_n=b[7], new_delta=b[8], total_delta=b[1] - b[0])

# ---------------------------------------------------------------------------
# 3. Where the one- and two-star reviews come from
# ---------------------------------------------------------------------------
groups = df(f"""
select case when status <> 'delivered' or delivered_at is null then 'never_arrived'
            when is_late then 'late'
            when n_sellers > 1 then 'split_sellers'
            when n_items > 1 then 'several_items'
            else 'ordinary' end as key,
       count(*) as orders, sum((review_score <= 2)::int) as low, avg((review_score <= 2)::int) as low_rate,
       avg(review_score) as avg_score
from fact_orders where {WIN} and review_score is not null group by 1""").set_index("key")
base = groups.loc["ordinary", "low_rate"]
groups["share_orders"] = groups.orders / groups.orders.sum()
groups["share_low"] = groups.low / groups.low.sum()
groups["excess"] = groups.low - base * groups.orders       # low reviews beyond what ordinary orders would produce
order = ["never_arrived", "late", "split_sellers", "several_items", "ordinary"]
R["low_groups"] = [dict(key=k, **groups.loc[k].to_dict()) for k in order]
prob = groups.drop("ordinary")
multi = groups.loc[["split_sellers", "several_items"]]
R["low_summary"] = dict(
    baseline=base, problem_share_orders=prob.orders.sum() / groups.orders.sum(),
    problem_share_low=prob.low.sum() / groups.low.sum(), excess=prob.excess.sum(),
    excess_share=prob.excess.sum() / groups.low.sum(),
    multi_orders=multi.orders.sum(), multi_share_orders=multi.orders.sum() / groups.orders.sum(),
    multi_low_rate=multi.low.sum() / multi.orders.sum(), multi_excess=multi.excess.sum(),
    multi_share_low=multi.low.sum() / groups.low.sum(),
)

R["multi_detail"] = recs(df(f"""
select case when n_items = 1 then 'one' when n_products = 1 then 'same_product'
            when n_sellers = 1 then 'different_products' else 'several_sellers' end as key,
       count(*) as orders, avg((review_score <= 2)::int) as low_rate, avg(review_score) as avg_score,
       avg(has_comment::int) as comment_rate, avg(gmv) as aov
from fact_orders where {DELIV} and not is_late and review_score is not null group by 1 order by 3"""))

# What the written comments on those multi-item orders say. The pattern looks for Portuguese
# phrases that mean "only part of my order came" (so recebi, apenas um, faltou, metade...).
PARTIAL = (r"(s[oó] recebi|recebi (apenas|s[oó]|somente|s[oó]mente)|apenas (um|uma|1|metade)|somente (um|uma|1)"
           r"|falt(ou|a|ando|aram)|incomplet|parcial|metade|n[aã]o recebi (o|a|os|as) (outr|rest|segund)"
           r"|veio (s[oó]|apenas|somente)|chegou (s[oó]|apenas|somente)|entregue (s[oó]|apenas|somente)"
           r"|outro produto|os outros|a outra|o outro|restante)")
cm = df(f"""
select (f.n_items > 1) as multi, lower(r.review_comment_message) as msg
from fact_orders f join order_reviews_one o using (order_id) join reviews r using (order_id)
where {DELIV} and not f.is_late and f.review_score <= 2 and r.review_score <= 2
  and r.review_comment_message is not null and length(trim(r.review_comment_message)) > 0""")
cm["partial"] = cm.msg.str.contains(PARTIAL, regex=True)
R["comments"] = dict(
    multi_n=int(cm.multi.sum()), multi_partial=float(cm[cm.multi].partial.mean()),
    single_n=int((~cm.multi).sum()), single_partial=float(cm[~cm.multi].partial.mean()),
)

# Orders that never reached the customer, and the money customers had paid for them.
und = df(f"""
select status, count(*) as orders, sum(paid) as paid from fact_orders
where {WIN} and (status <> 'delivered' or delivered_at is null) group by 1 order by 2 desc""")
R["undelivered"] = dict(
    by_status=recs(und), orders=int(und.orders.sum()), paid=float(und.paid.sum()),
    share=float(und.orders.sum()) / n_all,
    paid_share=float(und.paid.sum()) / one(f"select sum(paid) from fact_orders where {WIN}")[0],
    rate_2017=one(f"select avg((status <> 'delivered' or delivered_at is null)::int) from fact_orders where {WIN} and month < '2018-01-01'")[0],
    rate_latest=one(f"select avg((status <> 'delivered' or delivered_at is null)::int) from fact_orders where {WIN} and month >= '2018-06-01'")[0],
    unavailable_2017=one(f"select avg((status = 'unavailable')::int) from fact_orders where {WIN} and month < '2018-01-01'")[0],
    unavailable_latest=one(f"select avg((status = 'unavailable')::int) from fact_orders where {WIN} and month >= '2018-06-01'")[0],
)

# ---------------------------------------------------------------------------
# 4. Delivery: speed, the promise, and where lateness comes from
# ---------------------------------------------------------------------------
R["score_by_gap"] = recs(df(f"""
select case when days_vs_promise <= -15 then 0 when days_vs_promise <= -8 then 1 when days_vs_promise <= -3 then 2
            when days_vs_promise <= 0 then 3 when days_vs_promise <= 3 then 4 when days_vs_promise <= 7 then 5
            else 6 end as bucket,
       count(*) as orders, avg(review_score) as avg_score, avg((review_score <= 2)::int) as low_rate
from fact_orders where {DELIV} and review_score is not null group by 1 order by 1"""))

R["score_by_speed"] = recs(df(f"""
select case when days_to_deliver < 4 then 0 when days_to_deliver < 8 then 1 when days_to_deliver < 12 then 2
            when days_to_deliver < 16 then 3 when days_to_deliver < 21 then 4 when days_to_deliver < 30 then 5 else 6 end as bucket,
       count(*) as orders, avg(review_score) as avg_score, avg((review_score <= 2)::int) as low_rate
from fact_orders where {DELIV} and review_score is not null and not is_late and n_items = 1 group by 1 order by 1"""))

sv = df(f"""
select (review_creation_date::date < delivered_at::date) as asked_before,
       case when days_vs_promise <= 3 then 'd1_3' when days_vs_promise <= 7 then 'd4_7' else 'd8' end as lateness,
       count(*) as orders, avg(review_score) as avg_score, avg((review_score <= 2)::int) as low_rate
from fact_orders where {DELIV} and is_late and review_score is not null group by 1, 2""")
late_rev = sv.orders.sum()
s13 = sv[sv.lateness == "d1_3"].set_index("asked_before")
R["survey"] = dict(
    asked_before_share=sv[sv.asked_before].orders.sum() / late_rev,
    d13_before_n=int(s13.loc[True, "orders"]), d13_before_score=s13.loc[True, "avg_score"], d13_before_low=s13.loc[True, "low_rate"],
    d13_after_n=int(s13.loc[False, "orders"]), d13_after_score=s13.loc[False, "avg_score"], d13_after_low=s13.loc[False, "low_rate"],
)

lt = df(f"""
select is_late, seller_missed_deadline as missed, count(*) as orders, median(days_to_handoff) as handoff,
       median(days_in_transit) as transit
from fact_orders where {DELIV} and carrier_at is not null group by 1, 2""")
late = lt[lt.is_late]
legs = df(f"""select is_late, median(days_to_handoff) as handoff, median(days_in_transit) as transit, median(days_promised) as promised
              from fact_orders where {DELIV} and carrier_at is not null group by 1""").set_index("is_late")
bad_months = "('2017-11-01', '2017-12-01', '2018-02-01', '2018-03-01')"
bm = df(f"""select (month in {bad_months}) as bad, count(*) as orders, sum(is_late::int) as late, avg(is_late::int) as rate,
                   avg(is_late::int) filter (where cust_state = 'RJ') as rio_rate
            from fact_orders where {DELIV} group by 1""").set_index("bad")
rio = one(f"""select count(*) filter (where cust_state = 'RJ') * 1.0 / count(*),
                     sum(is_late::int) filter (where cust_state = 'RJ') * 1.0 / sum(is_late::int),
                     avg(is_late::int) filter (where cust_state = 'RJ'), avg(is_late::int) filter (where cust_state <> 'RJ'),
                     sum(is_late::int) filter (where cust_state = 'RJ')
              from fact_orders where {DELIV}""")
ne = "('BA','SE','AL','PE','PB','RN','CE','PI','MA')"
nord = one(f"""select count(*) filter (where cust_state in {ne}) * 1.0 / count(*),
                      sum(is_late::int) filter (where cust_state in {ne}) * 1.0 / sum(is_late::int),
                      avg(is_late::int) filter (where cust_state in {ne}),
                      median(days_to_deliver) filter (where cust_state in {ne}),
                      median(days_to_deliver) filter (where cust_state = 'SP'),
                      sum(freight) filter (where cust_state in {ne}) / sum(gmv) filter (where cust_state in {ne}),
                      sum(freight) filter (where cust_state = 'SP') / sum(gmv) filter (where cust_state = 'SP')
               from fact_orders where {DELIV}""")
conc = one(f"""
with s as (select seller_id, count(*) as orders, sum(seller_missed_deadline::int) as missed
           from fact_orders where {DELIV} and n_sellers = 1 group by 1),
     t as (select *, sum(missed) over (order by missed desc, seller_id) as running, sum(missed) over () as total,
                  row_number() over (order by missed desc, seller_id) as rk from s)
select max(rk) filter (where running <= total * 0.5), count(*), max(total), sum(orders) filter (where running <= total * 0.5), sum(orders)
from t""")
R["late"] = dict(
    carrier_share=float(late[~late.missed].orders.sum() / late.orders.sum()),
    seller_share=float(late[late.missed].orders.sum() / late.orders.sum()),
    missed_but_on_time=int(lt[(~lt.is_late) & (lt.missed)].orders.sum()),
    missed_rate=float(lt[lt.missed].orders.sum() / lt.orders.sum()),
    transit_late=legs.loc[True, "transit"], transit_on_time=legs.loc[False, "transit"],
    handoff_late=legs.loc[True, "handoff"], handoff_on_time=legs.loc[False, "handoff"],
    bad_share_orders=bm.loc[True, "orders"] / bm.orders.sum(), bad_share_late=bm.loc[True, "late"] / bm.late.sum(),
    bad_late_orders=int(bm.loc[True, "late"]),
    bad_rate=bm.loc[True, "rate"], normal_rate=bm.loc[False, "rate"],
    rio_bad_rate=bm.loc[True, "rio_rate"], rio_normal_rate=bm.loc[False, "rio_rate"],
    rio_share_orders=rio[0], rio_share_late=rio[1], rio_rate=rio[2], rest_rate=rio[3], rio_late_orders=int(rio[4]),
    ne_share_orders=nord[0], ne_share_late=nord[1], ne_rate=nord[2], ne_days=nord[3], sp_days=nord[4],
    ne_freight=nord[5], sp_freight=nord[6],
    half_missed_sellers=int(conc[0]), sellers_shipping=int(conc[1]), missed_total=int(conc[2]),
    half_missed_share_sellers=conc[0] / conc[1], half_missed_share_orders=conc[3] / conc[4],
)

lane = one(f"""select avg((seller_state = 'SP')::int),
                      avg((seller_state = 'SP' and cust_state = 'RJ')::int),
                      avg(is_late::int) filter (where seller_state = 'SP' and cust_state = 'RJ'),
                      sum(is_late::int) filter (where seller_state = 'SP' and cust_state = 'RJ') * 1.0 / sum(is_late::int)
               from fact_orders where {DELIV}""")
R["lanes"] = dict(sp_seller_share=lane[0], sprj_share=lane[1], sprj_rate=lane[2], sprj_share_late=lane[3])

# A test of whether a promise set from recent history would beat the promise Olist actually made.
bt = df(f"select purchased_at, delivered_at, cust_state, days_to_deliver as d, days_promised as p, is_late from fact_orders where {DELIV}")
bt["week"] = bt.purchased_at.dt.to_period("W").dt.start_time
tests = []
for q in (0.90, 0.93, 0.95, 0.97):
    parts = []
    for w in sorted(bt.week.unique()):
        if w < pd.Timestamp("2017-05-01"):
            continue
        past = bt[(bt.delivered_at < w) & (bt.delivered_at >= w - pd.Timedelta(days=28))]
        now = bt[bt.week == w].copy()
        if len(past) < 200:
            continue
        g = past.groupby("cust_state").d.agg(["count", lambda s: s.quantile(q)])
        g.columns = ["cnt", "sq"]
        now = now.join(g, on="cust_state")
        now["new_p"] = np.ceil(np.where(now.cnt.fillna(0) >= 30, now.sq, past.d.quantile(q)))
        parts.append(now)
    o = pd.concat(parts)
    tests.append(dict(quantile=q, orders=len(o), actual_promise=o.p.mean(), actual_late=o.is_late.mean(),
                      test_promise=o.new_p.mean(), test_late=(o.d > o.new_p).mean()))
R["promise_test"] = tests

# ---------------------------------------------------------------------------
# 5. Sellers: concentration, staying power, early signs
# ---------------------------------------------------------------------------
tiers = df("""
with t as (select *, ntile(100) over (order by sales desc, seller_id) as pct from seller_life)
select case when pct <= 1 then 0 when pct <= 5 then 1 when pct <= 20 then 2 when pct <= 50 then 3 else 4 end as tier,
       count(*) as sellers, sum(sales) as sales, avg(months_active) as months_active, min(sales) as min_sales
from t group by 1 order by 1""")
tiers["share_sellers"] = tiers.sellers / tiers.sellers.sum()
tiers["share_sales"] = tiers.sales / tiers.sales.sum()
R["tiers"] = recs(tiers)
top5 = tiers[tiers.tier <= 1]
top20 = tiers[tiers.tier <= 2]

trac = df("""
with early as (
    select l.seller_id, count(distinct s.order_id) as n30
    from seller_life l join seller_lines s using (seller_id)
    where s.purchased_at < l.first_sale_at + interval 30 day and l.first_sale_at < '2018-03-01' group by 1),
later as (
    select l.seller_id, sum(s.price) as sales
    from seller_life l join seller_lines s using (seller_id)
    where s.purchased_at >= l.first_sale_at + interval 90 day and s.purchased_at < l.first_sale_at + interval 180 day group by 1)
select case when n30 = 1 then 0 when n30 <= 3 then 1 when n30 <= 9 then 2 else 3 end as bucket,
       count(*) as sellers, avg((later.sales is not null)::int) as still_selling,
       sum(coalesce(later.sales, 0)) / count(*) / 3 as later_sales_pm
from early left join later using (seller_id) group by 1 order by 1""")
R["traction"] = recs(trac)
gone = 1 - (trac.sellers * trac.still_selling).sum() / trac.sellers.sum()
est = one("""
select count(distinct seller_id) filter (where month between '2018-01-01' and '2018-05-01'),
       sum(m.sales) filter (where month between '2018-01-01' and '2018-05-01') / 5,
       count(distinct seller_id) filter (where month >= '2018-06-01'),
       sum(m.sales) filter (where month >= '2018-06-01') / 3
from seller_month m join seller_life l using (seller_id) where first_month < '2018-01-01'""")
R["sellers"] = dict(
    total=int(tiers.sellers.sum()), top1_n=int(tiers.sellers[0]), top1_share=tiers.share_sales[0],
    top5_n=int(top5.sellers.sum()), top5_share=top5.share_sales.sum(),
    top20_n=int(top20.sellers.sum()), top20_share=top20.share_sales.sum(),
    bottom50_n=int(tiers.sellers[4]), bottom50_share=tiers.share_sales[4],
    one_month_n=one("select count(*) from seller_life where months_active = 1")[0],
    one_month_share=one("select avg((months_active = 1)::int) from seller_life")[0],
    cohort_n=int(trac.sellers.sum()), gone_by_month_4_6=gone,
    slow_start_share=trac.sellers[0] / trac.sellers.sum(),
    new_per_month_2018=mm.loc["2018-01":"2018-08", "new_sellers"].mean(),
    est_active_before=int(est[0]), est_sales_before=est[1], est_active_after=int(est[2]), est_sales_after=est[3],
    est_change=est[3] / est[1] - 1,
)

# ---------------------------------------------------------------------------
# 6. Customers: do they come back?
# ---------------------------------------------------------------------------
rp = one(f"""
with firsts as (select * from fact_orders where customer_order_no = 1 and {DELIV} and purchased_at < '2018-03-01'),
     again as (select customer_id, count(*) as n from fact_orders where customer_order_no > 1 group by 1)
select count(*), avg((a.n is not null)::int),
       avg((a.n is not null)::int) filter (where f.is_late), avg((a.n is not null)::int) filter (where not f.is_late),
       avg((a.n is not null)::int) filter (where f.review_score = 5), avg((a.n is not null)::int) filter (where f.review_score <= 2)
from firsts f left join again a using (customer_id)""")
once = one(f"""with c as (select customer_id, count(*) as n from fact_orders where {SOLD} group by 1)
               select avg((n = 1)::int), count(*) from c""")
ret18 = one(f"select avg((customer_order_no > 1)::int) from fact_orders where {SOLD} and month >= '2018-01-01'")[0]
R["customers"] = dict(first_orders=rp[0], repeat_rate=rp[1], repeat_after_late=rp[2], repeat_after_on_time=rp[3],
                      repeat_after_five=rp[4], repeat_after_low=rp[5], once_share=once[0], customers=once[1],
                      returning_order_share_2018=ret18)

# ---------------------------------------------------------------------------
# 7. Scorecards by customer state and by product category
# ---------------------------------------------------------------------------
STATE_NAMES = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
               "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
               "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
               "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
               "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
               "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins"}
card = """
select {dim} as key, count(*) as orders, sum(gmv) as sales, sum(gmv) / count(*) as aov,
       sum(freight) / sum(gmv) as freight_share, median(days_to_deliver) as median_days,
       avg(is_late::int) as late_rate, avg((review_score <= 2)::int) as low_rate, avg(review_score) as avg_score
from fact_orders where {where} group by 1"""
st = df(card.format(dim="cust_state", where=DELIV)).sort_values("sales", ascending=False)
st["name"] = st.key.map(STATE_NAMES)
st["sales_share"] = st.sales / st.sales.sum()
R["states"] = recs(st)

ct = df(card.format(dim="category", where=DELIV)).sort_values("sales", ascending=False)
chg = df(f"""select category as key,
                    sum(gmv) filter (where month between '2018-01-01' and '2018-05-01') / 5 as before_pm,
                    sum(gmv) filter (where month >= '2018-06-01') / 3 as after_pm
             from fact_orders where {SOLD} group by 1""")
ct = ct.merge(chg, on="key")
ct["change"] = ct.after_pm / ct.before_pm - 1
ct["sales_share"] = ct.sales / ct.sales.sum()
ct["name"] = ct.key.str.replace("_", " ").str.capitalize()
R["categories"] = recs(ct.head(20))
R["category_count"] = int(len(ct))

RESULTS.mkdir(exist_ok=True)


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (o != o) else round(float(o), 6)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


(RESULTS / "results.json").write_text(json.dumps(clean(R), indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote results/results.json")
for k in ("comments", "window", "trend", "stall", "bridge", "low_summary", "survey", "late", "sellers", "customers", "undelivered"):
    v = clean(R[k])
    if k == "undelivered":
        v = {a: b for a, b in v.items() if a != "by_status"}
    print(k, json.dumps(v, ensure_ascii=False))
print("periods", json.dumps(clean(R["periods"])))
print("low_groups", json.dumps(clean(R["low_groups"])))
print("traction", json.dumps(clean(R["traction"])))
print("tiers", json.dumps(clean(R["tiers"])))
print("promise", json.dumps(clean(R["promise_test"])))
print("multi", json.dumps(clean(R["multi_detail"])))
print("gap", json.dumps(clean(R["score_by_gap"])))
print("speed", json.dumps(clean(R["score_by_speed"])))
