"""Segments: who leaves by segment, what to do about each, then the detail."""
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config
from src import data_access as da
from src import theme as th
from src import ui

da.require_pipeline()
seg = da.query("10_segment_summary.sql").sort_values("sort_order")
mix = da.query("11_segment_contract_mix.sql")
overall_rate = float(da.query("01_overall_churn.sql").iloc[0]["churn_rate"])

top = seg.loc[seg["churn_rate"].idxmax()]
biggest = seg.loc[seg["annual_revenue_at_risk"].idxmax()]

ui.page_header(
    f"Of new customers paying {th.fmt_money(config.HIGH_SPEND_MIN_MONTHLY)} or more a month, "
    f"{th.in_100(top['churn_rate'])} left.",
    f"They're {top['share_of_customers']:.0%} of customers and {top['share_of_revenue_at_risk']:.0%} of the "
    f"revenue at risk. The biggest pot of money sits with {biggest['segment']}, but most of them stay. "
    f"{th.in_100(biggest['churn_rate'])} left.",
)

d = seg.sort_values("churn_rate", ascending=False)
fig = th.dot_plot(
    d["segment"].tolist(), d["churn_rate"].tolist(), [f"   {th.in_100(r)}" for r in d["churn_rate"]],
    "Who leaves, by segment", "Out of every 100 customers in each segment.",
    accent=top["segment"], xmax=d["churn_rate"].max() * 1.3, hover="%{y}<br>%{x:.1%} left", height=360,
)
st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

# Segment list ---------------------------------------------------------------
st.markdown("### Each segment, and what I'd do")
rows = []
for _, r in seg.iterrows():
    info = config.SEGMENTS[r["segment"]]
    above = r["churn_rate"] > overall_rate
    rows.append(
        '<div class="seg-row">'
        f'<div><div class="name">{escape(r["segment"])}</div>'
        f'<div class="rule-text">{escape(info["rule"])}</div></div>'
        '<div class="stats">'
        f'<div class="stat"><div class="v">{r["customers"]:,.0f}</div>'
        f'<div class="k">customers, {r["share_of_customers"]:.0%} of all</div></div>'
        f'<div class="stat"><div class="v{" accent" if r["segment"] == top["segment"] else "" if above else " dim"}">{r["churn_rate"]:.1%}</div>'
        f'<div class="k">left{", above average" if above else ""}</div></div>'
        f'<div class="stat"><div class="v{"" if above else " dim"}">{th.fmt_money(r["annual_revenue_at_risk"])}</div>'
        '<div class="k">at risk a year</div></div>'
        '</div>'
        f'<div class="action">{escape(info["action"])}</div>'
        '</div>'
    )
st.markdown(f'<div class="seg-list">{"".join(rows)}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
ui.section("How the segments were built", intro="Where the money sits, and what each segment is made of.")

left, right = st.columns(2, gap="large")
with left:
    d = seg.sort_values("annual_revenue_at_risk", ascending=False)
    fig = th.hbar(
        d["segment"].tolist(), d["annual_revenue_at_risk"].tolist(),
        [f"{th.fmt_money(v)}  ({s:.0%})" for v, s in zip(d["annual_revenue_at_risk"], d["share_of_revenue_at_risk"])],
        "Revenue at risk by segment", "A year of billing from those who left, and share of the total.",
        highlight=[biggest["segment"]], xmax=d["annual_revenue_at_risk"].max() * 1.9,
        hover="%{y}<br>%{x:$,.0f} a year", height=340)
    st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

with right:
    LABEL_POS = {"New High-Spend": "bottom center", "New Standard": "bottom center",
                 "Established Thin Bundle": "top right", "Established Full Bundle": "top center",
                 "Established Low-Spend": "bottom center"}
    fig = go.Figure(go.Scatter(
        x=seg["churn_rate"], y=seg["avg_monthly_charge"], mode="markers+text",
        marker=dict(size=seg["customers"], sizemode="area", sizeref=2.0 * seg["customers"].max() / (46 ** 2),
                    sizemin=6, color=[th.SILVER if s == top["segment"] else th.GREY_DIM_BAR for s in seg["segment"]],
                    line=dict(color=th.BLACK, width=2)),
        text=seg["segment"], textposition=[LABEL_POS.get(s, "top center") for s in seg["segment"]],
        textfont=dict(size=12, color=th.WHITE), cliponaxis=False, customdata=seg[["customers", "annual_revenue_at_risk"]],
        hovertemplate="%{text}<br>%{x:.1%} left<br>Average bill %{y:$,.2f}<br>"
                      "%{customdata[0]:,} customers<br>%{customdata[1]:$,.0f} at risk<extra></extra>"))
    fig.add_vline(x=overall_rate, line=dict(color=th.GREY_TEXT, width=1, dash="dot"))
    fig.add_annotation(x=overall_rate, y=1, yref="paper", text=f"Average {overall_rate:.1%}", showarrow=False,
                       xanchor="left", xshift=4, yanchor="bottom", font=dict(size=12, color=th.GREY_TEXT))
    fig.update_xaxes(tickformat=".0%", range=[-0.1, seg["churn_rate"].max() * 1.2], title_text="Share who left",
                     showgrid=True, gridcolor=th.GRID)
    fig.update_yaxes(tickformat="$,.0f", range=[0, seg["avg_monthly_charge"].max() * 1.3],
                     title_text="Avg bill")
    th.titled(fig, "Churn against value", "Circle size is number of customers.", height=340)
    st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

st.markdown("### What each segment is made of")
mtm = mix[mix["contract"] == "Month-to-month"].set_index("segment")["share_of_segment"]
fiber = (mix.assign(f=mix["share_fiber"] * mix["customers"]).groupby("segment")[["f", "customers"]].sum()
         .pipe(lambda x: x["f"] / x["customers"]))
table = pd.DataFrame({
    "Segment": seg["segment"],
    "Customers": seg["customers"],
    "Avg tenure, months": seg["avg_tenure_months"],
    "Avg services": seg["avg_services"],
    "Avg bill": seg["avg_monthly_charge"],
    "Month-to-month": seg["segment"].map(mtm).fillna(0),
    "Fiber": seg["segment"].map(fiber).fillna(0),
})
st.dataframe(
    th.style_table(table, money_cols=["Avg bill"], pct_cols=["Month-to-month", "Fiber"],
                   int_cols=["Customers"], extra={"Avg tenure, months": "{:.1f}",
                                                  "Avg services": "{:.1f}"}),
    hide_index=True, width="stretch")

ui.note(
    "Every customer gets the same questions, in order, in SQL (src/schema.sql). Have they been "
    f"with us under <span class='num'>{config.NEW_CUSTOMER_MAX_TENURE + 1}</span> months? Do they pay "
    f"<span class='num'>{th.fmt_money(config.HIGH_SPEND_MIN_MONTHLY)}</span> or more a month, close to the median "
    f"bill? Do they hold <span class='num'>{config.FULL_BUNDLE_MIN_SERVICES}</span> or more of the nine services? "
    "I only ask the last one of established high payers, because that's where it splits churn the most. Everyone "
    "lands in exactly one segment. Revenue at risk is what the people who left were paying, times 12."
)
