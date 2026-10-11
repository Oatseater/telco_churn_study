"""Overview: the answer and a spec sheet, one bar for where the money went, then the splits."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from src import data_access as da
from src import theme as th
from src import ui

da.require_pipeline()
m = da.metrics()
o = da.query("01_overall_churn.sql").iloc[0]
contract = da.query("02_churn_by_contract.sql").sort_values("sort_order")
c = contract.set_index("category")
mtm, two = c.loc["Month-to-month"], c.loc["Two year"]
ratio = mtm["churn_rate"] / two["churn_rate"]

head, spec = st.columns([2.3, 1], gap="large", vertical_alignment="bottom")
with head:
    ui.page_header(
        f"Month-to-month customers leave {ratio:.0f} times as often as customers on two-year contracts.",
        f"{o['churn_rate']:.1%} of {o['customers']:,.0f} customers left. They took "
        f"{th.fmt_money(o['annual_revenue_at_risk'])} a year in billing with them, and "
        f"{mtm['share_of_revenue_at_risk']:.0%} of it came from people who could leave any month.",
    )
with spec:
    ui.ledger([
        ("Customers", th.fmt_int(o["customers"])),
        ("Left", f"{th.fmt_pct(o['churn_rate'])}  ({o['churned']:,.0f})"),
        ("Billed each month", th.fmt_money(o["monthly_revenue"])),
        ("At risk a year", th.fmt_money(o["annual_revenue_at_risk"])),
    ], accent=3)
    st.markdown('<div style="height:56px"></div>', unsafe_allow_html=True)

fig = th.share_bar(
    contract["category"].tolist(), contract["annual_revenue_at_risk"].tolist(),
    f"Where the {th.fmt_money(o['annual_revenue_at_risk'])} went",
    "A year of billing from the customers who left, split by their contract.",
    accent="Month-to-month", height=250,
)
st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

# ---------------------------------------------------------------------------
ui.section("Churn, split other ways", intro="Every number here comes from the SQL files in queries/. Pick a split.")

DIMENSIONS = {
    "Contract": ("02_churn_by_contract.sql", "contract"),
    "Tenure": ("03_churn_by_tenure_bucket.sql", "tenure"),
    "Payment method": ("04_churn_by_payment_method.sql", "payment method"),
    "Internet service": ("05_churn_by_internet_service.sql", "internet service"),
    "Add-on services": ("06_churn_by_addon_service.sql", "add-on"),
    "Services held": ("07_churn_by_service_count.sql", "number of services"),
}
choice = st.segmented_control("Split by", list(DIMENSIONS), default="Tenure") or "Tenure"
qfile, dim_label = DIMENSIONS[choice]
df = da.query(qfile)
overall_rate = float(o["churn_rate"])

if choice == "Add-on services":
    fig = go.Figure()
    for _, r in df.iterrows():
        fig.add_trace(go.Scatter(x=[r["churn_rate_with"], r["churn_rate_without"]], y=[r["category"]] * 2,
                                 mode="lines", line=dict(color=th.RULE, width=2), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=df["churn_rate_without"], y=df["category"], mode="markers+text",
        marker=dict(size=11, color=th.WHITE), text=[f"without {v:.1%}" for v in df["churn_rate_without"]],
        textposition="middle right", textfont=dict(size=13, color=th.WHITE), customdata=df["customers_without"],
        hovertemplate="%{y}, without it<br>%{x:.1%} left<br>%{customdata:,} customers<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=df["churn_rate_with"], y=df["category"], mode="markers+text",
        marker=dict(size=11, color=th.BLACK, line=dict(color=th.GREY_TEXT, width=2)),
        text=[f"with {v:.1%}" for v in df["churn_rate_with"]], textposition="middle left",
        textfont=dict(size=13, color=th.GREY_TEXT), customdata=df["customers_with"],
        hovertemplate="%{y}, with it<br>%{x:.1%} left<br>%{customdata:,} customers<extra></extra>"))
    fig.update_xaxes(tickformat=".0%", range=[0, df["churn_rate_without"].max() * 1.35], showgrid=True,
                     gridcolor=th.GRID)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=th.WHITE))
    th.titled(fig, "Churn with and without each add-on",
              "Internet customers only. Filled dot: without the add-on. Hollow dot: with it.", height=420)
    st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)
    top = df.iloc[0]
    ui.note(
        f"Internet customers without {top['category'].lower()} left at <span class='num'>"
        f"{top['churn_rate_without']:.1%}</span>. With it, <span class='num'>{top['churn_rate_with']:.1%}</span>. "
        "Security and support show the widest gaps. Streaming barely moves. People who buy support might just be "
        "more committed to begin with, so this is something to test, not a cause."
    )
else:
    df = df.sort_values("sort_order")
    df["category"] = df["category"].astype(str)
    left, right = st.columns(2, gap="large")
    with left:
        fig = th.hbar_rate(df, "category", "churn_rate", f"Churn rate by {dim_label}",
                           "Bright bars are above the overall rate.", reference=overall_rate)
        st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)
    with right:
        if "annual_revenue_at_risk" in df.columns:
            fig2 = th.hbar(
                df["category"].tolist(), df["annual_revenue_at_risk"].tolist(),
                [f"{th.fmt_money(v)}  ({s:.0%})" for v, s in zip(df["annual_revenue_at_risk"],
                                                                df["share_of_revenue_at_risk"])],
                f"Revenue at risk by {dim_label}", "What the people who left were paying, times 12.",
                highlight=[df.loc[df["annual_revenue_at_risk"].idxmax(), "category"]],
                xmax=df["annual_revenue_at_risk"].max() * 2.0,
                hover="%{y}<br>%{x:$,.0f} a year", height=fig.layout.height)
        else:
            fig2 = th.hbar(
                df["category"].tolist(), df["customers"].tolist(), [f"{v:,.0f}" for v in df["customers"]],
                "Customers by number of services", "Out of nine: phone, extra lines, internet and six add-ons.",
                xmax=df["customers"].max() * 1.3, hover="%{y} services<br>%{x:,} customers",
                height=fig.layout.height)
        st.plotly_chart(fig2, width="stretch", config=th.CHART_CONFIG)

    worst = df.loc[df["churn_rate"].idxmax()]
    msg = (f"Highest churn: {worst['category']}, at <span class='num'>{worst['churn_rate']:.1%}</span> against "
           f"<span class='num'>{overall_rate:.1%}</span> overall.")
    if "share_of_revenue_at_risk" in df.columns:
        msg += (f" That group is <span class='num'>{worst['share_of_revenue_at_risk']:.1%}</span> of the "
                "revenue at risk.")
    ui.note(msg)

# ---------------------------------------------------------------------------
st.markdown("### What a simple model adds")
mm = m["model"]
ui.ledger([
    ("ROC AUC on held-out customers", f"{mm['roc_auc']:.3f}"),
    ("The same for the rule 'month-to-month means at risk'", f"{mm['roc_auc_contract_rule']:.3f}"),
    ("Riskiest 10% who actually left", th.fmt_pct(mm["top_decile_churn_rate"])),
    ("Average across held-out customers", th.fmt_pct(mm["test_churn_rate"])),
    ("Accuracy", th.fmt_pct(mm["accuracy"])),
    ("Accuracy from guessing nobody leaves", th.fmt_pct(mm["majority_class_accuracy"])),
])
st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)

drv = [d for d in mm["drivers"] if abs(d["odds_ratio"] - 1) >= 0.10][:10]
ors = [d["odds_ratio"] for d in drv]
fig = go.Figure(go.Bar(
    x=[np.log(v) for v in ors], y=[d["label"] for d in drv], orientation="h",
    marker=dict(color=[th.SILVER if v > 1 else th.GREY_DIM_BAR for v in ors]),
    text=[f"{v:.2f}x odds" if v > 1 else f"{(1 - v):.0%} lower odds" for v in ors],
    textposition="outside", cliponaxis=False, textfont=dict(size=13, color=th.WHITE),
    customdata=ors, hovertemplate="%{y}<br>Odds ratio %{customdata:.2f}<extra></extra>"))
span = max(abs(np.log(v)) for v in ors) * 1.6
fig.update_xaxes(range=[-span, span], showticklabels=False, showline=False, zeroline=True,
                 zerolinecolor=th.GREY_TEXT, zerolinewidth=1)
fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=th.WHITE, size=13))
th.titled(fig, "What goes with leaving, holding everything else equal",
          "Odds ratios from a logistic regression. Bright bars raise the odds of leaving, dim bars lower them.",
          height=96 + 38 * len(drv) + 40)
st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

ui.note(
    "The model ranks people well. In its riskiest 10%, leavers turn up "
    f"<span class='num'>{mm['top_decile_lift']:.1f}x</span> as often as average. It doesn't show cause. Someone "
    "pushed onto a two-year contract isn't the same as someone who chose one. I didn't tune it, it has no "
    "confidence intervals, and I only checked it on this one public dataset. I left monthly charge out because "
    f"the services a customer holds explain it almost completely (R-squared <span class='num'>"
    f"{mm['services_explain_charges_r2']:.3f}</span>)."
)
st.markdown("### How I counted")
ui.note(
    "Churn rate is the share of customers marked as gone. Revenue at risk is what the ones who left were paying "
    "each month, times 12. All money is billing, not profit. I'm assuming US dollars; the data doesn't say."
)
