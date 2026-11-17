"""Fills site/src.html with the numbers in results/results.json and writes site/index.html.

Every figure in the report's text is a {{token}} in src.html. This script works each one out
from the results file, so the wording and the charts can never disagree with the analysis.
Set CODE_URL to an empty string to build the page without the links to the code.
"""
import json
import re
from db import ROOT, RESULTS

CODE_URL = "https://github.com/RumitOsu/more-sellers-same-sales"

R = json.loads((RESULTS / "results.json").read_text(encoding="utf-8"))
W, P, T, S, B = R["window"], R["periods"], R["trend"], R["stall"], R["bridge"]
L, SV, SE, CU, UN, LS = R["late"], R["survey"], R["sellers"], R["customers"], R["undelivered"], R["low_summary"]
groups = {g["key"]: g for g in R["low_groups"]}
cats = {c["key"]: c for c in R["categories"]}
states = {s["key"]: s for s in R["states"]}
gap = {g["bucket"]: g for g in R["score_by_gap"]}
speed = {g["bucket"]: g for g in R["score_by_speed"]}
trac = R["traction"]
test95 = next(t for t in R["promise_test"] if t["quantile"] == 0.95)


def pct(v, d=0):
    return f"{v * 100:.{d}f}%"


def thousands(v):
    """R$863 thousand, or R$1.0 million."""
    if abs(v) >= 995_000:
        return f"R${v / 1e6:.1f} million"
    return f"R${round(abs(v) / 1000):,} thousand"


def reais(v):
    return f"R${round(v):,}"


def num(v):
    return f"{round(v):,}"


def round_to(v, step):
    return f"{round(v / step) * step:,}"


late_group, ordinary = groups["late"], groups["ordinary"]
peak_orders = L["bad_share_orders"] * W["delivered"]
avoided_late = L["bad_late_orders"] - L["normal_rate"] * peak_orders
avoided_bad = avoided_late * (late_group["low_rate"] - ordinary["low_rate"])
est_lost = SE["est_sales_before"] - SE["est_sales_after"]
activation = (trac[2]["sellers"] + trac[3]["sellers"]) / sum(t["sellers"] for t in trac)

TOK = {
    # executive summary
    "latest_days": f"{P['latest']['median_days']:.0f}",
    "latest_late": pct(P["latest"]["late_rate"], 1),
    "latest_sales": thousands(P["latest"]["sales_pm"]),
    "sales_vs_prior": pct(1 - P["latest"]["sales_pm"] / P["prior"]["sales_pm"]),
    "jan17_sales": thousands(T["jan17_sales"]),
    "peak_sales": thousands(T["peak_sales"]),
    "sellers_change": pct(S["sellers_change"]),
    "sales_change_abs": pct(-S["sales_change"]),
    "continuing_pct": pct(-B["continuing_pct"]),
    "bad_share_late": pct(L["bad_share_late"]),
    "rio_bad_rate": pct(L["rio_bad_rate"]),
    "late_score": f"{late_group['avg_score']:.1f}",
    "ordinary_score": f"{ordinary['avg_score']:.1f}",
    "top1_n": num(SE["top1_n"]),
    "top1_share": pct(SE["top1_share"]),
    "gone_share": pct(SE["gone_by_month_4_6"]),
    "multi_share_orders": pct(LS["multi_share_orders"]),
    "multi_share_low": pct(LS["multi_share_low"]),
    # 1 growth
    "q1_17_sales": thousands(T["h1_17"]),
    "q4_17_sales": thousands(T["q4_17"]),
    "growth_2017": f"{T['growth_2017']:.1f}",
    "jan_may_sales": thousands(P["jan_may_18"]["sales_pm"]),
    "aug_yoy": pct(T["aug_yoy"]),
    "sellers_jan": num(S["sellers_jan"]),
    "sellers_aug": num(S["sellers_aug"]),
    "new_per_month": num(SE["new_per_month_2018"]),
    "per_seller_jan": reais(S["per_seller_jan"]),
    "per_seller_aug": reais(S["per_seller_aug"]),
    "per_seller_change": pct(-S["per_seller_change"]),
    "continuing_n": num(B["continuing_n"]),
    "continuing_before": thousands(B["continuing_before"]),
    "continuing_after": thousands(B["continuing_after"]),
    "new_delta": thousands(B["new_delta"]),
    "stopped_delta": thousands(B["stopped_delta"]),
    "cat_computers_change": pct(-cats["computers_accessories"]["change"]),
    "cat_sports_change": pct(-cats["sports_leisure"]["change"]),
    "cat_health_change": pct(cats["health_beauty"]["change"]),
    # 2 customers
    "customers": num(CU["customers"]),
    "once_share": pct(CU["once_share"]),
    "returning_share": pct(CU["returning_order_share_2018"], 1),
    "repeat_per_100": num(CU["repeat_rate"] * 100),
    "repeat_after_five": pct(CU["repeat_after_five"], 1),
    "repeat_after_low": pct(CU["repeat_after_low"], 1),
    "repeat_after_on_time": pct(CU["repeat_after_on_time"], 1),
    "repeat_after_late": pct(CU["repeat_after_late"], 1),
    "first_orders": num(CU["first_orders"]),
    # 3 bad orders
    "low_rate": pct(W["low_rate"], 1),
    "baseline": pct(LS["baseline"], 1),
    "problem_share_orders": pct(LS["problem_share_orders"]),
    "problem_share_low": pct(LS["problem_share_low"]),
    "reviewed": num(W["reviewed"]),
    "excess": round_to(LS["excess"], 100),
    "excess_share": pct(LS["excess_share"]),
    "undelivered_paid": thousands(UN["paid"]),
    "undelivered_paid_share": pct(UN["paid_share"], 1),
    "undelivered_orders": num(UN["orders"]),
    "undelivered_2017": pct(UN["rate_2017"], 1),
    "undelivered_latest": pct(UN["rate_latest"], 1),
    "unavailable_2017": pct(UN["unavailable_2017"], 1),
    "unavailable_latest": pct(UN["unavailable_latest"], 1),
    "several_items_low": pct(groups["several_items"]["low_rate"]),
    "split_sellers_low": pct(groups["split_sellers"]["low_rate"]),
    "multi_partial": pct(R["comments"]["multi_partial"]),
    "single_partial": pct(R["comments"]["single_partial"]),
    # 4 delivery
    "q1_days": f"{P['q1_18']['median_days']:.0f}",
    "bad_share_orders": pct(L["bad_share_orders"]),
    "normal_rate": pct(L["normal_rate"], 1),
    "bad_rate": pct(L["bad_rate"], 1),
    "rio_share_orders": pct(L["rio_share_orders"]),
    "rio_share_late": pct(L["rio_share_late"]),
    "avg_promised": f"{W['avg_promised']:.0f}",
    "avg_days": f"{W['avg_days']:.0f}",
    "slow_on_time_score": f"{speed[5]['avg_score']:.1f}",
    "late_4_7_score": f"{gap[5]['avg_score']:.1f}",
    "asked_before": pct(SV["asked_before_share"]),
    "d13_after_score": f"{SV['d13_after_score']:.1f}",
    "d13_before_score": f"{SV['d13_before_score']:.1f}",
    "carrier_share": pct(L["carrier_share"]),
    "seller_share": pct(L["seller_share"]),
    "transit_late": f"{L['transit_late']:.0f}",
    "transit_on_time": f"{L['transit_on_time']:.0f}",
    "half_missed_sellers": num(L["half_missed_sellers"]),
    "half_missed_share": pct(L["half_missed_share_sellers"]),
    "sp_share_orders": pct(states["SP"]["orders"] / W["delivered"]),
    "sp_seller_share": pct(R["lanes"]["sp_seller_share"]),
    "sp_days": f"{L['sp_days']:.0f}",
    "ne_share_orders": pct(L["ne_share_orders"]),
    "ne_share_late": pct(L["ne_share_late"]),
    "ne_days": f"{L['ne_days']:.0f}",
    "ne_freight": pct(L["ne_freight"]),
    "sp_freight": pct(L["sp_freight"]),
    "sprj_share": pct(R["lanes"]["sprj_share"]),
    "sprj_rate": pct(R["lanes"]["sprj_rate"]),
    "test_late": pct(test95["test_late"], 1),
    "actual_late": pct(test95["actual_late"], 1),
    "test_extra_days": f"{test95['test_promise'] - test95['actual_promise']:.0f}",
    # 5 sellers
    "sellers_total": num(SE["total"]),
    "top5_n": num(SE["top5_n"]),
    "top5_share": pct(SE["top5_share"]),
    "bottom50_n": num(SE["bottom50_n"]),
    "bottom50_share": pct(SE["bottom50_share"]),
    "cohort_n": num(SE["cohort_n"]),
    "est_before": thousands(SE["est_sales_before"]),
    "est_after": thousands(SE["est_sales_after"]),
    "est_change": pct(-SE["est_change"]),
    "est_active_before": num(SE["est_active_before"]),
    "est_active_after": num(SE["est_active_after"]),
    "slow_start_share": pct(SE["slow_start_share"]),
    "trac0_still": pct(trac[0]["still_selling"]),
    "trac3_still": pct(trac[3]["still_selling"]),
    "trac_ratio": f"{trac[3]['later_sales_pm'] / trac[0]['later_sales_pm']:.0f}",
    # 6 recommendations
    "peak_avoided_late": round_to(avoided_late, 100),
    "peak_avoided_bad": round_to(avoided_bad, 100),
    "activation_share": pct(activation),
    "active4_still": pct(sum(t["sellers"] * t["still_selling"] for t in trac[2:]) / sum(t["sellers"] for t in trac[2:])),
    "rest_still": pct(sum(t["sellers"] * t["still_selling"] for t in trac[:2]) / sum(t["sellers"] for t in trac[:2])),
    "est_lost": thousands(est_lost),
    "est_tenth": thousands(est_lost / 10),
    "gap_pm": thousands(-B["total_delta"]),
    "gap_year": thousands(-B["total_delta"] * 12),
    "multi_orders": num(LS["multi_orders"]),
    "multi_excess": round_to(LS["multi_excess"], 100),
    "multi_low_rate": pct(LS["multi_low_rate"]),
    # notes
    "code_sentence": (f'The SQL and the scripts are <a href="{CODE_URL}" target="_blank" rel="noopener noreferrer">on GitHub</a>.'
                      if CODE_URL else ""),
    "code_button": (f'<a href="{CODE_URL}" target="_blank" rel="noopener noreferrer">Code on GitHub ↗</a>' if CODE_URL else ""),
}

DATA = {k: R[k] for k in ("monthly", "periods", "bridge", "low_groups", "score_by_gap", "tiers", "traction",
                          "states", "categories", "category_count")}
DATA["customers"] = {"repeat_rate": CU["repeat_rate"]}

src = (ROOT / "site" / "src.html").read_text(encoding="utf-8")
used = set(re.findall(r"\{\{(\w+)\}\}", src))
missing, unused = used - TOK.keys(), TOK.keys() - used
if missing:
    raise SystemExit(f"tokens in src.html with no value: {sorted(missing)}")
if unused:
    print("values not used by the page:", sorted(unused))
out = re.sub(r"\{\{(\w+)\}\}", lambda m: TOK[m.group(1)], src)
out = out.replace("/*DATA*/null", json.dumps(DATA, ensure_ascii=False, separators=(",", ":")))
(ROOT / "site" / "index.html").write_text(out, encoding="utf-8", newline="\n")
print(f"wrote site/index.html ({len(out) / 1024:.0f} KB, {len(used)} tokens)")
for k in sorted(TOK):
    if not k.startswith("code_"):
        print(f"  {k} = {TOK[k]}")
