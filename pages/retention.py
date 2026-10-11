"""Retention: three survival lines first, then the filterable Kaplan-Meier detail."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config
from src import data_access as da
from src import retention as rt
from src import theme as th
from src import ui

da.require_pipeline()
cust = da.customers()
by_contract = da.query("09_retention_curve_by_contract.sql")
overall_sql = da.query("08_retention_curve_overall.sql")

CONTRACTS = ["Month-to-month", "One year", "Two year"]
HORIZON = 24
at_h = {c: rt.retention_at(rt.truncate(by_contract[by_contract["contract"] == c]), HORIZON) for c in CONTRACTS}
overall_12 = rt.retention_at(overall_sql, 12)
month_one = float(overall_sql.loc[overall_sql["tenure_month"] == 1, "monthly_churn_hazard"].iloc[0])

ui.page_header(
    f"Out of 100 month-to-month customers, {round(at_h['Month-to-month'] * 100):.0f} are still here after two "
    f"years. On a two-year contract, {round(at_h['Two year'] * 100):.0f} are.",
    f"Leaving is heaviest at the start. {th.in_100(1 - overall_12)} are gone within a year, and the first "
    f"month alone loses {month_one:.1%}.",
)

# The one visual: three survival lines, month-to-month in red.
fig = go.Figure()
STYLE = {"Month-to-month": (th.RED, "solid", 2.6), "One year": (th.WHITE, "solid", 1.4),
         "Two year": (th.GREY_TEXT, "dot", 1.6)}
for c in CONTRACTS:
    k = rt.truncate(by_contract[by_contract["contract"] == c])
    color, dash, width = STYLE[c]
    fig.add_trace(go.Scatter(x=k["tenure_month"], y=k["retention"] * 100, mode="lines",
                             line=dict(color=color, width=width, dash=dash, shape="hv"),
                             hovertemplate=f"{c}<br>Month %{{x}}<br>%{{y:.0f}} of 100 still here<extra></extra>"))
    last = k.iloc[-1]
    fig.add_annotation(x=last["tenure_month"], y=last["retention"] * 100, xanchor="left", xshift=10,
                       text=f"{c}  {last['retention'] * 100:.0f}", showarrow=False,
                       font=dict(size=14, color=th.WHITE if c != "Two year" else th.GREY_TEXT))
fig.add_vline(x=HORIZON, line=dict(color=th.RULE, width=1))
fig.add_annotation(x=HORIZON, y=1, yref="paper", yanchor="bottom", xanchor="left", xshift=6, showarrow=False,
                   text="two years", font=dict(size=12, color=th.GREY_TEXT))
fig.update_xaxes(title_text="Months since joining", dtick=12, range=[0, 73])
fig.update_yaxes(range=[0, 101], dtick=25, title_text=None, ticksuffix="")
fig.update_layout(margin=dict(l=8, r=190, t=76, b=64))
th.titled(fig, "Out of 100 who join, how many are still here", "By the contract they signed.", height=470)
st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

# ---------------------------------------------------------------------------
ui.section("The same curves, with filters", intro="Month by month. Use them to check the headline for any group you like.")

COMPARE = {
    "Contract": ("contract", CONTRACTS),
    "Internet service": ("internet_service", ["Fiber optic", "DSL", "No"]),
    "Payment type": ("payment_type", ["Manual", "Automatic"]),
    "Segment": ("segment", config.SEGMENT_ORDER),
}
cust = cust.assign(payment_type=cust["payment_method"].str.endswith("(automatic)")
                   .map({True: "Automatic", False: "Manual"}))

c1, c2, c3, c4 = st.columns([1.1, 1.3, 1.3, 1.6], gap="small")
with c1:
    compare = st.selectbox("Compare by", list(COMPARE), index=0)
with c2:
    f_contract = st.multiselect("Contract", CONTRACTS, placeholder="All contracts")
with c3:
    f_internet = st.multiselect("Internet service", COMPARE["Internet service"][1], placeholder="All internet types")
with c4:
    f_segment = st.multiselect("Segment", config.SEGMENT_ORDER, placeholder="All segments")

d = cust
if f_contract:
    d = d[d["contract"].isin(f_contract)]
if f_internet:
    d = d[d["internet_service"].isin(f_internet)]
if f_segment:
    d = d[d["segment"].isin(f_segment)]
if d.empty:
    st.info("No customers match these filters. Remove one to see results.")
    st.stop()

col, order = COMPARE[compare]
groups = [g for g in order if g in set(d[col])]
km = rt.kaplan_meier_by(d, col)
overall = rt.truncate(rt.kaplan_meier(d))

highlight = None
if len(groups) > 3:
    highlight = st.selectbox("Highlight", groups, index=0,
                             help="With more than three groups, one is drawn bright and the rest dim.")

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=overall["tenure_month"], y=overall["retention"], mode="lines",
    line=dict(color=th.GREY_DIM, width=2, dash="dot", shape="hv"), customdata=overall["at_risk"],
    hovertemplate="All selected<br>Month %{x}<br>%{y:.1%} still here<br>At risk %{customdata:,}<extra></extra>"))
end_labels = []
for i, g in enumerate(groups):
    k = km[km[col] == g]
    if k.empty:
        continue
    if highlight is None:
        color, dash, width = th.ORDERED_SHADES[i], th.DASHES[i], 2
    else:
        color, dash, width = (th.WHITE, "solid", 2.5) if g == highlight else (th.GREY_DIM, "solid", 1.5)
    fig.add_trace(go.Scatter(
        x=k["tenure_month"], y=k["retention"], mode="lines",
        line=dict(color=color, width=width, dash=dash, shape="hv"), customdata=k[["at_risk", "churned"]],
        hovertemplate=f"{g}<br>Month %{{x}}<br>%{{y:.1%}} still here<br>"
                      "At risk %{customdata[0]:,}; left this month %{customdata[1]:,}<extra></extra>"))
    last = k.iloc[-1]
    end_labels.append((g, float(last["tenure_month"]), float(last["retention"]), color))

end_labels.sort(key=lambda t: t[2], reverse=True)
placed = []
for g, x, y, color in end_labels:
    y_lab = y
    for py in placed:
        if abs(y_lab - py) < 0.045:
            y_lab = py - 0.045
    placed.append(y_lab)
    fig.add_annotation(x=x, y=y_lab, text=f"{g}  {y:.0%}", showarrow=False, xanchor="left", xshift=8,
                       font=dict(size=13, color=th.WHITE if color != th.GREY_DIM else th.GREY_MARK))

fig.update_xaxes(title_text="Months since joining", range=[0, int(d["tenure_months"].max()) + 1], dtick=12)
fig.update_yaxes(tickformat=".0%", range=[0, 1.02])
fig.update_layout(margin=dict(l=8, r=210, t=76, b=64))
th.titled(fig, f"Share still active, by {compare.lower()}",
          f"Kaplan-Meier estimate. Lines stop where fewer than {rt.MIN_AT_RISK} customers remain. "
          "Dotted: everyone selected.", height=480)
st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

milestones = [6, 12, 24, 36, 48, 60]
rows = []
for g in groups:
    k = km[km[col] == g]
    row = {compare: g, "Customers": int((d[col] == g).sum())}
    row.update({f"{mth} months": rt.retention_at(k, mth) for mth in milestones})
    rows.append(row)
row = {compare: "All selected", "Customers": len(d)}
row.update({f"{mth} months": rt.retention_at(overall, mth) for mth in milestones})
rows.append(row)

st.markdown("### Share still here at each milestone")
st.dataframe(th.style_table(pd.DataFrame(rows), pct_cols=[f"{mth} months" for mth in milestones],
                            int_cols=["Customers"], na="-"),
             hide_index=True, width="stretch")
st.caption(f"A dash means fewer than {rt.MIN_AT_RISK} customers were still at risk by then.")

left, right = st.columns(2, gap="large")
with left:
    st.markdown("### How I worked it out")
    ui.note(
        "Kaplan-Meier. Each month I take the share of still-active customers who leave and knock it off the "
        "running total. Anyone who hasn't left counts as still here up to their current tenure. The overall and "
        "by-contract curves are computed in SQL (queries/08 and queries/09). The filtered views use the same math "
        "in Python, and a test checks the two match.<br><br>"
        "One catch. This is a single snapshot, not people followed from the day they joined, so it assumes people "
        "who joined years ago behaved like recent joiners. And customers pick their own contract, so the gap "
        "between contracts isn't the contract's doing alone."
    )
with right:
    h = rt.kaplan_meier(d).query("1 <= tenure_month <= 24").dropna(subset=["monthly_churn_hazard"])
    if not h.empty:
        figh = go.Figure(go.Bar(
            x=h["tenure_month"], y=h["monthly_churn_hazard"],
            marker=dict(color=[th.SILVER if i == 0 else th.GREY_DIM_BAR for i in range(len(h))]),
            customdata=h[["at_risk", "churned"]],
            hovertemplate="Month %{x}<br>%{y:.1%} of those still active left<br>"
                          "At risk %{customdata[0]:,}<extra></extra>"))
        first = h.iloc[0]
        figh.add_annotation(x=first["tenure_month"], y=first["monthly_churn_hazard"],
                            text=f"{first['monthly_churn_hazard']:.1%} in month one", showarrow=False,
                            xanchor="left", xshift=10, yshift=-4, font=dict(size=13, color=th.WHITE))
        figh.update_xaxes(title_text="Month", dtick=3)
        figh.update_yaxes(tickformat=".0%")
        th.titled(figh, "Chance of leaving in each early month",
                  "Of customers still active at that month.", height=340)
        st.plotly_chart(figh, width="stretch", config=th.CHART_CONFIG)
