"""End-to-end pipeline: audit -> clean -> SQLite -> SQL analysis -> retention ->
segmentation -> model -> money layer -> generated README and memo.

Run:  python run_pipeline.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

import pandas as pd

from src import audit, clean, config, database, economics, model, report, retention


def log(msg: str) -> None:
    print(f"[pipeline] {msg}", flush=True)


def records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records"))


def main() -> int:
    t0 = time.time()
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    config.QUERY_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Audit -------------------------------------------------------------
    log("Stage 1/8  audit raw data")
    try:
        raw = audit.load_raw()
    except audit.SchemaError as exc:
        print(f"\nSTOPPED: {exc}\n", file=sys.stderr)
        return 1
    audit_results = audit.run_audit(raw)
    audit.write_audit_report(audit_results)
    log(f"           {audit_results['n_rows']:,} rows; report -> {config.AUDIT_REPORT.relative_to(config.ROOT)}")

    # 2. Clean -------------------------------------------------------------
    log("Stage 2/8  clean and validate")
    df = clean.clean(raw)
    clean.validate_clean(df)
    df.to_csv(config.CLEAN_CSV, index=False)

    # 3. Load into SQLite --------------------------------------------------
    log("Stage 3/8  load into SQLite and create views")
    database.load_to_sqlite(df)

    # 4. SQL analysis ------------------------------------------------------
    log("Stage 4/8  run SQL queries")
    results: dict[str, pd.DataFrame] = {}
    for path in database.query_files():
        res = database.run_query_file(path)
        if res.empty:
            raise RuntimeError(f"{path.name} returned no rows")
        res.to_csv(config.QUERY_RESULTS_DIR / f"{path.stem}.csv", index=False)
        results[path.stem] = res
        log(f"           {path.name:<40} {len(res):>4} rows")

    overall = results["01_overall_churn"].iloc[0].to_dict()

    # 5. Retention (Kaplan-Meier, from SQL) --------------------------------
    log("Stage 5/8  retention curves")
    km_all = results["08_retention_curve_overall"]
    km_contract = results["09_retention_curve_by_contract"]
    milestones = [6, 12, 24, 36, 48, 60]
    ret = {
        "milestones": milestones,
        "min_at_risk": retention.MIN_AT_RISK,
        "overall": {str(m): retention.retention_at(km_all, m) for m in milestones},
        "by_contract": {},
        "first_month_hazard": float(km_all.loc[km_all.tenure_month == 1, "monthly_churn_hazard"].iloc[0]),
    }
    for c, g in km_contract.groupby("contract"):
        g = retention.truncate(g)
        ret["by_contract"][c] = {str(m): retention.retention_at(g, m) for m in milestones}

    # 6. Segmentation (rules in SQL; summary from query 10) ----------------
    log("Stage 6/8  segmentation")
    seg = results["10_segment_summary"].copy()
    seg["rule"] = seg["segment"].map(lambda s: config.SEGMENTS[s]["rule"])
    seg["action"] = seg["segment"].map(lambda s: config.SEGMENTS[s]["action"])

    # 7. Model -------------------------------------------------------------
    log("Stage 7/8  baseline logistic regression")
    model_results = model.train_baseline(df)
    model_results["services_explain_charges_r2"] = model.services_explain_charges_r2(df)
    log(f"           test ROC AUC {model_results['roc_auc']:.3f} "
        f"(contract-only rule {model_results['roc_auc_contract_rule']:.3f})")

    # 8. Money layer -------------------------------------------------------
    log("Stage 8/8  revenue at risk and retention scenarios")
    econ = economics.segment_economics(seg)
    d, s, u = config.DEFAULT_DISCOUNT, config.DEFAULT_SAVE_RATE, config.DEFAULT_STAYER_UPTAKE
    comparison = economics.compare_segments(econ, d, s, u)
    best = comparison.sort_values("net_benefit", ascending=False).iloc[0].to_dict()
    top_risk_segment = seg.sort_values("annual_revenue_at_risk", ascending=False).iloc[0]["segment"]
    profile = database.read_table("SELECT * FROM customer_profile")
    top_risk_mtm = economics.run_scenario(
        economics.economics_from_customers(profile, top_risk_segment, month_to_month_only=True), d, s, u
    ).as_dict()
    top_risk_mtm["customers_in_segment"] = int((profile["segment"] == top_risk_segment).sum())
    scenarios = {
        "defaults": {"discount": d, "save_rate": s, "stayer_uptake": u,
                     "horizon_months": config.HORIZON_MONTHS},
        "assumptions": economics.assumptions_text(d, s, u),
        "by_segment": records(comparison),
        "recommended": best,
        "top_revenue_at_risk_segment": top_risk_segment,
        "top_revenue_at_risk_segment_month_to_month": top_risk_mtm,
        "n_segments_positive": int((comparison["net_benefit"] > 0).sum()),
    }

    metrics = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "audit": audit_results,
        "overall": overall,
        "by_contract": records(results["02_churn_by_contract"]),
        "by_tenure_bucket": records(results["03_churn_by_tenure_bucket"]),
        "by_payment_method": records(results["04_churn_by_payment_method"]),
        "by_internet_service": records(results["05_churn_by_internet_service"]),
        "addons": records(results["06_churn_by_addon_service"]),
        "by_service_count": records(results["07_churn_by_service_count"]),
        "retention": ret,
        "segments": records(seg),
        "segment_contract_mix": records(results["11_segment_contract_mix"]),
        "model": model_results,
        "scenarios": scenarios,
        "queries": [{"file": p.name, "question": database.business_question(p)}
                    for p in database.query_files()],
    }
    config.METRICS_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    # Generated documents ---------------------------------------------------
    report.render_all(metrics)
    log("           README.md and memo.md rendered from templates")
    log(f"Done in {time.time() - t0:.1f}s. Next: streamlit run app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
