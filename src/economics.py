"""Money layer: revenue at risk and the retention scenario calculator.

Used by both the dashboard and the generated memo, so the numbers cannot differ.

Scenario logic, for one target segment over a fixed horizon:

    expected_churners = customers x churn_rate
    customers_saved   = expected_churners x save_rate
    revenue_saved     = customers_saved x avg charge of churners x horizon
                        (gross: what the saved customers keep paying, before discount)
    discount_cost     = discount x horizon x (
                            customers_saved x avg charge of churners
                          + stayer_uptake x customers who would have stayed anyway
                                          x avg charge of stayers)
    net_benefit       = revenue_saved - discount_cost

The key point the calculator makes visible: you cannot tell in advance who will
churn, so the discount also goes to customers who would have stayed anyway. That
subsidy is usually the largest cost.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from src import config


@dataclass
class SegmentEconomics:
    segment: str
    customers: int
    churn_rate: float
    avg_charge_churned: float
    avg_charge_retained: float


@dataclass
class ScenarioResult:
    segment: str
    discount: float
    save_rate: float
    stayer_uptake: float
    horizon_months: int
    customers_targeted: int
    expected_churners: float
    customers_saved: float
    stayers_subsidised: float
    revenue_saved: float
    cost_on_saved: float
    cost_on_stayers: float
    discount_cost: float
    net_benefit: float
    roi: float
    break_even_save_rate: float | None

    def as_dict(self) -> dict:
        return asdict(self)


def segment_economics(segment_summary: pd.DataFrame) -> dict[str, SegmentEconomics]:
    out = {}
    for _, r in segment_summary.iterrows():
        out[r["segment"]] = SegmentEconomics(
            segment=r["segment"],
            customers=int(r["customers"]),
            churn_rate=float(r["churn_rate"]),
            avg_charge_churned=float(r["avg_monthly_charge_churned"]),
            avg_charge_retained=float(r["avg_monthly_charge_retained"]),
        )
    return out


def economics_from_customers(customers: pd.DataFrame, segment: str,
                             month_to_month_only: bool = False) -> SegmentEconomics:
    """Same inputs as segment_economics(), computed from customer rows so the
    calculator can narrow a segment to its month-to-month customers. Tests check
    that the unfiltered result matches queries/10_segment_summary.sql."""
    d = customers[customers["segment"] == segment]
    if month_to_month_only:
        d = d[d["contract"] == "Month-to-month"]
    churned = d[d["churned"] == 1]
    retained = d[d["churned"] == 0]
    label = segment + (" (month-to-month only)" if month_to_month_only else "")
    return SegmentEconomics(
        segment=label,
        customers=int(len(d)),
        churn_rate=float(d["churned"].mean()) if len(d) else 0.0,
        avg_charge_churned=float(churned["monthly_charges"].mean()) if len(churned) else 0.0,
        avg_charge_retained=float(retained["monthly_charges"].mean()) if len(retained) else 0.0,
    )


def run_scenario(seg: SegmentEconomics, discount: float, save_rate: float,
                 stayer_uptake: float = config.DEFAULT_STAYER_UPTAKE,
                 horizon_months: int = config.HORIZON_MONTHS) -> ScenarioResult:
    if not 0 <= discount <= 1 or not 0 <= save_rate <= 1 or not 0 <= stayer_uptake <= 1:
        raise ValueError("discount, save_rate and stayer_uptake must be between 0 and 1")

    churners = seg.customers * seg.churn_rate
    stayers = seg.customers - churners
    saved = churners * save_rate
    subsidised = stayers * stayer_uptake

    revenue_saved = saved * seg.avg_charge_churned * horizon_months
    cost_saved = discount * horizon_months * saved * seg.avg_charge_churned
    cost_stayers = discount * horizon_months * subsidised * seg.avg_charge_retained
    cost = cost_saved + cost_stayers
    net = revenue_saved - cost

    # Save rate s at which net = 0:
    #   s*C*m_c*(1-d) = d*U*S*m_s  ->  s = d*U*S*m_s / (C*m_c*(1-d))
    denom = churners * seg.avg_charge_churned * (1 - discount)
    if denom > 0:
        be = discount * subsidised * seg.avg_charge_retained / denom
        be = be if be <= 1 else None  # not reachable even if every churner is saved
    else:
        be = None

    return ScenarioResult(
        segment=seg.segment, discount=discount, save_rate=save_rate,
        stayer_uptake=stayer_uptake, horizon_months=horizon_months,
        customers_targeted=seg.customers, expected_churners=churners,
        customers_saved=saved, stayers_subsidised=subsidised,
        revenue_saved=revenue_saved, cost_on_saved=cost_saved,
        cost_on_stayers=cost_stayers, discount_cost=cost, net_benefit=net,
        roi=(net / cost) if cost > 0 else float("nan"),
        break_even_save_rate=be,
    )


def compare_segments(econ: dict[str, SegmentEconomics], discount: float, save_rate: float,
                     stayer_uptake: float = config.DEFAULT_STAYER_UPTAKE) -> pd.DataFrame:
    rows = [run_scenario(econ[s], discount, save_rate, stayer_uptake).as_dict()
            for s in config.SEGMENT_ORDER if s in econ]
    return pd.DataFrame(rows)


def assumptions_text(discount: float, save_rate: float, stayer_uptake: float,
                     horizon_months: int = config.HORIZON_MONTHS) -> list[str]:
    """The assumptions behind every scenario number, for display on screen and in the memo."""
    return [
        f"The offer is {discount:.0%} off the monthly bill for {horizon_months} months.",
        f"{save_rate:.0%} of the people who would have left stay because of it. This is a guess. "
        "Only a proper test can measure it.",
        f"{stayer_uptake:.0%} of the people who were staying anyway take the discount too, because nobody can "
        "tell in advance who is about to leave.",
        "Each segment churns at the rate seen in this data.",
        f"Anyone kept stays the full {horizon_months} months and keeps paying what they pay now.",
        "Money is billing, not profit. No cost to serve, no campaign costs.",
        "Currency is US dollars. The data doesn't say, so that's an assumption too.",
    ]
