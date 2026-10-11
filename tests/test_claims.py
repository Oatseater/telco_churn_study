"""Guards for the qualitative claims written in README.md and memo.md.

The numbers in those files are filled in by code; these tests check that the
words around them ("highest", "only", "loses money") are still true for the data.
"""
import re
from pathlib import Path

from src import config, report


def by(records, key="category"):
    return {r[key]: r for r in records}


def test_month_to_month_churns_most_two_year_least(metrics):
    c = by(metrics["by_contract"])
    assert c["Month-to-month"]["churn_rate"] > c["One year"]["churn_rate"] > c["Two year"]["churn_rate"]
    assert c["Month-to-month"]["share_of_revenue_at_risk"] > 0.5


def test_churn_falls_with_tenure(metrics):
    rates = [r["churn_rate"] for r in sorted(metrics["by_tenure_bucket"], key=lambda r: r["sort_order"])]
    assert rates == sorted(rates, reverse=True)


def test_first_year_is_over_represented_in_revenue_at_risk(metrics):
    first = [r for r in metrics["by_tenure_bucket"] if r["sort_order"] <= 2]
    assert sum(r["share_of_revenue_at_risk"] for r in first) > sum(r["share_of_customers"] for r in first)


def test_electronic_check_churns_most(metrics):
    top = max(metrics["by_payment_method"], key=lambda r: r["churn_rate"])
    assert top["category"] == "Electronic check"
    manual = [r["churn_rate"] for r in metrics["by_payment_method"] if r["payment_type"] == "Manual"]
    auto = [r["churn_rate"] for r in metrics["by_payment_method"] if r["payment_type"] == "Automatic"]
    assert max(auto) < max(manual)


def test_fiber_churns_most_and_dominates_revenue_at_risk(metrics):
    top = max(metrics["by_internet_service"], key=lambda r: r["churn_rate"])
    assert top["category"] == "Fiber optic"
    assert top["share_of_revenue_at_risk"] > top["share_of_customers"]


def test_protective_addons_show_widest_gap_streaming_smallest(metrics):
    order = [r["category"] for r in metrics["addons"]]
    assert set(order[:2]) == {"Online security", "Tech support"}
    assert set(order[-2:]) == {"Streaming TV", "Streaming movies"}
    assert all(r["churn_rate_with"] < r["churn_rate_without"] for r in metrics["addons"])


def test_segment_extremes(metrics):
    segs = by(metrics["segments"], "segment")
    assert max(segs.values(), key=lambda r: r["churn_rate"])["segment"] == "New High-Spend"
    assert min(segs.values(), key=lambda r: r["churn_rate"])["segment"] == "Established Low-Spend"


def test_biggest_revenue_at_risk_is_not_where_a_discount_pays(metrics):
    sc = metrics["scenarios"]
    assert sc["top_revenue_at_risk_segment"] != sc["recommended"]["segment"]
    top = by(sc["by_segment"], "segment")[sc["top_revenue_at_risk_segment"]]
    assert top["net_benefit"] < 0
    assert top["cost_on_stayers"] > top["revenue_saved"]


def test_recommended_scenario_is_positive_and_unique(metrics):
    sc = metrics["scenarios"]
    assert sc["recommended"]["net_benefit"] > 0
    assert sc["recommended"]["segment"] == "New High-Spend"
    assert sc["n_segments_positive"] == 1  # the README says "only one segment"
    assert sc["recommended"]["break_even_save_rate"] < sc["defaults"]["save_rate"]


def test_month_to_month_targeting_is_near_break_even(metrics):
    """README describes narrowing the top-risk segment to month-to-month as 'roughly break-even'."""
    m = metrics["scenarios"]["top_revenue_at_risk_segment_month_to_month"]
    assert abs(m["net_benefit"]) < 0.02 * m["revenue_saved"]


def test_model_beats_simple_rule_and_majority_baseline(metrics):
    mm = metrics["model"]
    assert mm["roc_auc"] > mm["roc_auc_contract_rule"]
    assert mm["accuracy"] > mm["majority_class_accuracy"]
    assert mm["drivers"][0]["feature"].startswith("contract=")


def test_generated_docs_are_current(metrics):
    """README.md and memo.md must equal a fresh render: no hand-edited numbers."""
    ctx = report.build_context(metrics)
    for tpl, out in [("README.template.md", "README.md"), ("memo.template.md", "memo.md")]:
        text = (config.TEMPLATES_DIR / tpl).read_text(encoding="utf-8")
        expected = report.PLACEHOLDER.sub(lambda m: ctx[m.group(1)], text)
        assert (config.ROOT / out).read_text(encoding="utf-8") == expected, f"{out} is stale or hand-edited"
        assert not report.PLACEHOLDER.search(expected)


EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0000FE0F]")


def test_no_emojis_anywhere():
    exts = {".py", ".md", ".sql", ".css", ".toml", ".txt"}
    skip = {".git", "data", "__pycache__", ".pytest_cache", "venv", ".venv"}
    for p in Path(config.ROOT).rglob("*"):
        if p.is_file() and p.suffix in exts and not (set(p.relative_to(config.ROOT).parts) & skip):
            assert not EMOJI.search(p.read_text(encoding="utf-8")), f"emoji found in {p}"


# --- Guards for the dashboard's headline sentences -----------------------------

def test_retention_headline_month_one_is_the_heaviest_month():
    """Retention page: 'Leaving is heaviest at the start ... the first month alone'."""
    from src import database
    km = database.run_query_file("08_retention_curve_overall.sql")
    hazards = km.loc[km["tenure_month"] >= 1, ["tenure_month", "monthly_churn_hazard"]]
    assert hazards.loc[hazards["monthly_churn_hazard"].idxmax(), "tenure_month"] == 1


def test_retention_headline_month_to_month_keeps_fewest_after_two_years():
    from src import database, retention
    km = database.run_query_file("09_retention_curve_by_contract.sql")
    at24 = {c: retention.retention_at(retention.truncate(g), 24) for c, g in km.groupby("contract")}
    assert at24["Month-to-month"] < at24["One year"] <= at24["Two year"]


def test_segments_headline_biggest_risk_pot_mostly_stays(metrics):
    """Segments page: the largest amount at risk sits where 'most customers stay'."""
    biggest = max(metrics["segments"], key=lambda r: r["annual_revenue_at_risk"])
    assert biggest["churn_rate"] < 0.5
