"""Render README.md and memo.md from templates using computed metrics only.

Templates use {{ placeholder }} markers. Rendering fails if a placeholder has no
value. Some context values are spare, available for future template edits.
"""
from __future__ import annotations

import re

from src import config

PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def pct(x: float) -> str:
    return f"{x:.1%}"


def money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.0f}"


def money_k(x: float) -> str:
    """Compact money for prose: $1.67M, $573k."""
    sign = "-" if x < 0 else ""
    a = abs(x)
    if a >= 1_000_000:
        return f"{sign}${a / 1_000_000:,.2f}M"
    if a >= 1_000:
        return f"{sign}${a / 1_000:,.0f}k"
    return f"{sign}${a:,.0f}"


def num(x: float) -> str:
    return f"{x:,.0f}"


def _by(records: list[dict], key: str, value) -> dict:
    for r in records:
        if r[key] == value:
            return r
    raise KeyError(f"{key}={value!r} not found")


def segment_table(m: dict) -> str:
    rows = ["| Segment | Rule | Customers | Churn rate | Avg monthly charge | Annual revenue at risk | Share of risk |",
            "|---|---|---:|---:|---:|---:|---:|"]
    for s in m["segments"]:
        rows.append(
            f"| {s['segment']} | {s['rule']} | {num(s['customers'])} ({pct(s['share_of_customers'])}) | "
            f"{pct(s['churn_rate'])} | {money(s['avg_monthly_charge'])} | "
            f"{money(s['annual_revenue_at_risk'])} | {pct(s['share_of_revenue_at_risk'])} |")
    return "\n".join(rows)


def scenario_table(m: dict) -> str:
    rows = ["| Target segment | Customers saved | Revenue saved | Discount cost | Net benefit | Break-even save rate |",
            "|---|---:|---:|---:|---:|---:|"]
    for r in m["scenarios"]["by_segment"]:
        be = r["break_even_save_rate"]
        rows.append(
            f"| {r['segment']} | {num(r['customers_saved'])} | {money(r['revenue_saved'])} | "
            f"{money(r['discount_cost'])} | {money(r['net_benefit'])} | "
            f"{pct(be) if be is not None else 'not reachable'} |")
    return "\n".join(rows)


def drivers_list(m: dict, n: int = 6) -> str:
    return "\n".join(f"- {d['plain_english']}" for d in m["model"]["drivers"][:n])


def query_table(m: dict) -> str:
    rows = ["| File | Business question |", "|---|---|"]
    for q in m["queries"]:
        rows.append(f"| `queries/{q['file']}` | {q['question']} |")
    return "\n".join(rows)


def build_context(m: dict) -> dict[str, str]:
    o = m["overall"]
    a = m["audit"]
    mtm = _by(m["by_contract"], "category", "Month-to-month")
    one = _by(m["by_contract"], "category", "One year")
    two = _by(m["by_contract"], "category", "Two year")
    tb = m["by_tenure_bucket"]
    first = tb[0]
    last = tb[-1]
    first_year = [r for r in tb if r["category"] in ("0-6 months", "7-12 months")]
    pay = m["by_payment_method"]
    top_pay = pay[0]
    auto = [r for r in pay if r["payment_type"] == "Automatic"]
    fiber = _by(m["by_internet_service"], "category", "Fiber optic")
    dsl = _by(m["by_internet_service"], "category", "DSL")
    no_net = _by(m["by_internet_service"], "category", "No")
    addons = m["addons"]
    top_addon, second_addon = addons[0], addons[1]
    stream = [r for r in addons if r["category"].startswith("Streaming")]
    svc = m["by_service_count"]
    svc_peak = max(svc, key=lambda r: r["churn_rate"])
    ret = m["retention"]
    rc = ret["by_contract"]
    segs = m["segments"]
    seg_top_churn = max(segs, key=lambda r: r["churn_rate"])
    seg_top_risk = max(segs, key=lambda r: r["annual_revenue_at_risk"])
    seg_low = min(segs, key=lambda r: r["churn_rate"])
    md = m["model"]
    sc = m["scenarios"]
    rec = sc["recommended"]
    rec_seg = _by(segs, "segment", rec["segment"])
    top_risk_blanket = _by(sc["by_segment"], "segment", sc["top_revenue_at_risk_segment"])
    top_risk_mtm = sc["top_revenue_at_risk_segment_month_to_month"]
    defaults = sc["defaults"]
    drivers = md["drivers"]

    ctx = {
        "generated_at": m["generated_at_utc"],
        "disclaimer": config.DISCLAIMER,
        # audit
        "n_rows": num(a["n_rows"]),
        "n_cols": num(a["n_columns"]),
        "n_blank_total_charges": num(a["total_charges_blank"]),
        "n_tenure_zero": num(a["tenure_zero_rows"]),
        "n_dup_profiles": num(a["duplicate_rows_excl_id"]),
        "n_dup_ids": num(a["duplicate_ids"]),
        "n_outliers": num(sum(v["n_outliers"] for v in a["outliers_iqr"].values())),
        "share_totals_consistent": pct(a["total_vs_expected_ratio"]["share_within_20pct"]),
        # overall
        "n_customers": num(o["customers"]),
        "n_churned": num(o["churned"]),
        "churn_rate": pct(o["churn_rate"]),
        "monthly_revenue": money(o["monthly_revenue"]),
        "monthly_revenue_churned": money(o["churned_monthly_revenue"]),
        "annual_revenue_at_risk": money(o["annual_revenue_at_risk"]),
        "annual_revenue_at_risk_k": money_k(o["annual_revenue_at_risk"]),
        "share_revenue_churned": pct(o["share_of_revenue_churned"]),
        # contract
        "mtm_churn": pct(mtm["churn_rate"]),
        "one_year_churn": pct(one["churn_rate"]),
        "two_year_churn": pct(two["churn_rate"]),
        "mtm_share_customers": pct(mtm["share_of_customers"]),
        "mtm_share_risk": pct(mtm["share_of_revenue_at_risk"]),
        "mtm_vs_two_year_x": f"{mtm['churn_rate'] / two['churn_rate']:.0f}",
        # tenure
        "first_bucket_label": first["category"],
        "first_bucket_churn": pct(first["churn_rate"]),
        "last_bucket_label": last["category"],
        "last_bucket_churn": pct(last["churn_rate"]),
        "first_year_share_risk": pct(sum(r["share_of_revenue_at_risk"] for r in first_year)),
        "first_year_share_customers": pct(sum(r["share_of_customers"] for r in first_year)),
        # payment
        "top_payment_method": top_pay["category"].lower(),
        "top_payment_churn": pct(top_pay["churn_rate"]),
        "top_payment_share_risk": pct(top_pay["share_of_revenue_at_risk"]),
        "auto_payment_churn_low": pct(min(r["churn_rate"] for r in auto)),
        "auto_payment_churn_high": pct(max(r["churn_rate"] for r in auto)),
        # internet
        "fiber_churn": pct(fiber["churn_rate"]),
        "fiber_share_customers": pct(fiber["share_of_customers"]),
        "fiber_share_risk": pct(fiber["share_of_revenue_at_risk"]),
        "fiber_avg_charge": money(fiber["avg_monthly_charge"]),
        "dsl_churn": pct(dsl["churn_rate"]),
        "no_internet_churn": pct(no_net["churn_rate"]),
        # add-ons
        "top_addon": top_addon["category"].lower(),
        "top_addon_with": pct(top_addon["churn_rate_with"]),
        "top_addon_without": pct(top_addon["churn_rate_without"]),
        "second_addon": second_addon["category"].lower(),
        "second_addon_with": pct(second_addon["churn_rate_with"]),
        "second_addon_without": pct(second_addon["churn_rate_without"]),
        "streaming_gap_max_pts": f"{max(r['churn_gap'] for r in stream) * 100:.1f}",
        # service count
        "svc_peak_n": num(svc_peak["category"]),
        "svc_peak_churn": pct(svc_peak["churn_rate"]),
        "svc_max_n": num(svc[-1]["category"]),
        "svc_max_churn": pct(svc[-1]["churn_rate"]),
        # retention
        "first_month_hazard": pct(ret["first_month_hazard"]),
        "ret_12": pct(ret["overall"]["12"]),
        "ret_24": pct(ret["overall"]["24"]),
        "ret_60": pct(ret["overall"]["60"]),
        "ret_mtm_12": pct(rc["Month-to-month"]["12"]),
        "ret_mtm_24": pct(rc["Month-to-month"]["24"]),
        "ret_two_24": pct(rc["Two year"]["24"]),
        "ret_one_24": pct(rc["One year"]["24"]),
        "min_at_risk": num(ret["min_at_risk"]),
        # segments
        "segment_table": segment_table(m),
        "n_segments": num(len(segs)),
        "seg_top_churn_name": seg_top_churn["segment"],
        "seg_top_churn_rate": pct(seg_top_churn["churn_rate"]),
        "seg_top_churn_share_customers": pct(seg_top_churn["share_of_customers"]),
        "seg_top_churn_share_risk": pct(seg_top_churn["share_of_revenue_at_risk"]),
        "seg_top_churn_risk": money(seg_top_churn["annual_revenue_at_risk"]),
        "seg_top_risk_name": seg_top_risk["segment"],
        "seg_top_risk_amount": money(seg_top_risk["annual_revenue_at_risk"]),
        "seg_top_risk_churn": pct(seg_top_risk["churn_rate"]),
        "seg_top_risk_share_revenue": pct(seg_top_risk["share_of_revenue"]),
        "seg_low_name": seg_low["segment"],
        "seg_low_churn": pct(seg_low["churn_rate"]),
        # model
        "model_auc": f"{md['roc_auc']:.3f}",
        "model_auc_rule": f"{md['roc_auc_contract_rule']:.3f}",
        "model_accuracy": pct(md["accuracy"]),
        "model_majority_accuracy": pct(md["majority_class_accuracy"]),
        "model_precision": pct(md["precision_at_0_5"]),
        "model_recall": pct(md["recall_at_0_5"]),
        "model_top_decile_rate": pct(md["top_decile_churn_rate"]),
        "model_top_decile_lift": f"{md['top_decile_lift']:.1f}",
        "model_test_churn": pct(md["test_churn_rate"]),
        "model_n_train": num(md["n_train"]),
        "model_n_test": num(md["n_test"]),
        "test_size": pct(config.TEST_SIZE),
        "model_r2": f"{md['services_explain_charges_r2']:.3f}",
        "drivers_list": drivers_list(m),
        "driver_1": drivers[0]["plain_english"],
        # scenarios
        "default_discount": f"{defaults['discount']:.0%}",
        "default_save_rate": f"{defaults['save_rate']:.0%}",
        "default_uptake": f"{defaults['stayer_uptake']:.0%}",
        "horizon_months": num(defaults["horizon_months"]),
        "scenario_table": scenario_table(m),
        "n_segments_positive": num(sc["n_segments_positive"]),
        "rec_segment": rec["segment"],
        "rec_customers": num(rec["customers_targeted"]),
        "rec_churn": pct(rec_seg["churn_rate"]),
        "rec_saved": num(rec["customers_saved"]),
        "rec_revenue_saved": money(rec["revenue_saved"]),
        "rec_cost": money(rec["discount_cost"]),
        "rec_cost_stayers": money(rec["cost_on_stayers"]),
        "rec_net": money(rec["net_benefit"]),
        "rec_roi": f"{rec['roi']:.1f}",
        "rec_break_even": pct(rec["break_even_save_rate"]),
        "top_risk_blanket_net": money(top_risk_blanket["net_benefit"]),
        "top_risk_blanket_loss": money(abs(top_risk_blanket["net_benefit"])),
        "top_risk_blanket_cost_stayers": money(top_risk_blanket["cost_on_stayers"]),
        "top_risk_blanket_break_even": (pct(top_risk_blanket["break_even_save_rate"])
                                        if top_risk_blanket["break_even_save_rate"] is not None
                                        else "not reachable"),
        "top_risk_mtm_customers": num(top_risk_mtm["customers_targeted"]),
        "top_risk_mtm_net": money(top_risk_mtm["net_benefit"]),
        "top_risk_mtm_break_even": (pct(top_risk_mtm["break_even_save_rate"])
                                    if top_risk_mtm["break_even_save_rate"] is not None
                                    else "not reachable"),
        "query_table": query_table(m),
    }
    return ctx


def render(template_name: str, out_name: str, ctx: dict[str, str]) -> set[str]:
    tpl = (config.TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
    used = set(PLACEHOLDER.findall(tpl))
    missing = sorted(used - ctx.keys())
    if missing:
        raise KeyError(f"{template_name}: no value for placeholders {missing}")
    out = PLACEHOLDER.sub(lambda mt: ctx[mt.group(1)], tpl)
    (config.ROOT / out_name).write_text(out, encoding="utf-8")
    return used


def render_all(metrics: dict) -> None:
    ctx = build_context(metrics)
    render("README.template.md", "README.md", ctx)
    render("memo.template.md", "memo.md", ctx)
