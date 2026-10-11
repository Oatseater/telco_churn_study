"""Retention calculator: does a discount offer pay for itself? Answer first, workings below."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config
from src import data_access as da
from src import economics as ec
from src import theme as th
from src import ui

da.require_pipeline()
cust = da.customers()
m = da.metrics()
recommended = m["scenarios"]["recommended"]["segment"]

# Advanced inputs live further down the page; read their current values first.
uptake = st.session_state.get("uptake_pct", int(round(config.DEFAULT_STAYER_UPTAKE * 100))) / 100
horizon = st.session_state.get("horizon", config.HORIZON_MONTHS)

header = st.container()

controls, statement = st.columns([1, 1.3], gap="large")
with controls:
    segment = st.selectbox("Who gets the offer", config.SEGMENT_ORDER,
                           index=config.SEGMENT_ORDER.index(recommended))
    mtm_only = st.checkbox("Only those on month-to-month contracts", value=False)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    discount = st.slider("Discount off the monthly bill", 0, 50, int(round(config.DEFAULT_DISCOUNT * 100)),
                         step=1, format="%d%%") / 100
    save_rate = st.slider("Share of would-be leavers who stay because of it", 0, 100,
                          int(round(config.DEFAULT_SAVE_RATE * 100)), step=1, format="%d%%") / 100

    st.caption(f"The starting values, {config.DEFAULT_DISCOUNT:.0%} off and {config.DEFAULT_SAVE_RATE:.0%} kept, "
               "are my guesses, not from the data. Move them.")

econ = ec.economics_from_customers(cust, segment, month_to_month_only=mtm_only)
if econ.customers == 0:
    with header:
        ui.page_header("Nobody matches that choice.", "Pick another segment or untick month-to-month only.", enter=False)
    st.stop()
r = ec.run_scenario(econ, discount, save_rate, uptake, horizon)
who = f"{econ.customers:,.0f} {segment} customers" + (" on month-to-month" if mtm_only else "")

with header:
    if r.net_benefit >= 0:
        ui.page_header(
            f"This offer keeps {r.customers_saved:,.0f} customers and brings in "
            f"{th.fmt_money(r.net_benefit)} more than it costs.",
            f"{discount:.0%} off for {horizon} months, offered to all {who}. It pays for itself if at least "
            f"{th.fmt_pct(r.break_even_save_rate)} of would-be leavers stay.",
            enter=False,
        )
    else:
        be = (f"It needs {th.fmt_pct(r.break_even_save_rate)} of would-be leavers to stay just to break even."
              if r.break_even_save_rate is not None else "It can't break even, even if every would-be leaver stays.")
        ui.page_header(
            f"This offer costs {th.fmt_money(-r.net_benefit)} more than it brings back.",
            f"{discount:.0%} off for {horizon} months, offered to all {who}. Most of them were staying anyway, "
            f"and they get the discount too. {be}",
            enter=False,
        )

with statement:
    be_txt = th.fmt_pct(r.break_even_save_rate) if r.break_even_save_rate is not None else "Not reachable"
    ui.ledger([
        ("Customers offered the discount", th.fmt_int(r.customers_targeted)),
        ("Expected to leave without it", th.fmt_int(r.expected_churners)),
        ("Kept because of it", th.fmt_int(r.customers_saved)),
        (f"Billing kept over {horizon} months", th.fmt_money(r.revenue_saved)),
        ("Spent on the discount", th.fmt_money(r.discount_cost)),
        ("  of which to people who would have stayed", th.fmt_money(r.cost_on_stayers)),
        ("Net result", th.fmt_money(r.net_benefit)),
        ("Break-even share who must stay", be_txt),
    ], accent=6 if r.net_benefit < 0 else None, caption="Gross billing, before any other costs.")

st.markdown('<div style="height:72px"></div>', unsafe_allow_html=True)

fig = go.Figure()
fig.add_trace(go.Bar(y=["Billing kept"], x=[r.revenue_saved], orientation="h",
                     marker=dict(color=th.SILVER), text=[th.fmt_money(r.revenue_saved)],
                     textposition="outside", cliponaxis=False, textfont=dict(size=15, color=th.WHITE),
                     hovertemplate="Billing kept %{x:$,.0f}<extra></extra>"))
fig.add_trace(go.Bar(y=["Discount given"], x=[r.discount_cost], orientation="h",
                     marker=dict(color=th.BLACK, pattern=th.HATCH, line=dict(color=th.GREY_TEXT, width=1)),
                     text=[th.fmt_money(r.discount_cost)], textposition="outside", cliponaxis=False,
                     textfont=dict(size=15, color=th.WHITE),
                     hovertemplate="Discount given %{x:$,.0f}<extra></extra>"))
fig.update_xaxes(range=[0, max(r.revenue_saved, r.discount_cost, 1) * 1.3], showticklabels=False, showline=False)
fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=th.WHITE, size=14))
th.titled(fig, "What comes back, what goes out",
          f"Over {horizon} months. Hatched is the discount, including what goes to people who were staying anyway.", height=240)
st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

# ---------------------------------------------------------------------------
ui.section("The math", intro="Where the discount money goes, how much the answer leans on the save rate, what I "
                "assumed, and the same offer tried on every segment.")

with st.expander("Change the other assumptions"):
    a1, a2 = st.columns(2, gap="large")
    with a1:
        st.slider("Share of would-have-stayed customers who also take the discount", 0, 100,
                  int(round(config.DEFAULT_STAYER_UPTAKE * 100)), step=5, format="%d%%", key="uptake_pct")
    with a2:
        st.slider("Months the discount runs and kept billing is counted", 3, 24, config.HORIZON_MONTHS,
                  step=1, key="horizon")

left, right = st.columns(2, gap="large")
with left:
    steps = [r.revenue_saved, -r.cost_on_saved, -r.cost_on_stayers, r.net_benefit]
    fig = go.Figure(go.Waterfall(
        orientation="v", x=["Billing<br>kept", "Discount to<br>those kept", "Discount to<br>stayers", "Net"],
        measure=["relative", "relative", "relative", "total"], y=steps,
        text=[th.fmt_money(v) for v in steps], textposition="outside", cliponaxis=False,
        textfont=dict(size=13, color=th.WHITE),
        width=0.5, increasing=dict(marker=dict(color=th.SILVER)),
        decreasing=dict(marker=dict(color=th.BLACK, line=dict(color=th.GREY_TEXT, width=1))),
        totals=dict(marker=dict(color=th.SILVER if r.net_benefit >= 0 else th.GREY_DIM_BAR)),
        connector=dict(line=dict(color=th.RULE, width=1)),
        hovertemplate="%{x}<br>%{y:$,.0f}<extra></extra>"))
    fig.update_yaxes(tickformat="$,.0f", range=[min(0, r.net_benefit) * 1.3, max(r.revenue_saved, 1) * 1.3])
    fig.update_xaxes(tickangle=0)
    th.titled(fig, "Where the money goes", "Stayers: customers who would not have left anyway.", height=400)
    st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

with right:
    rates = np.linspace(0, 1, 101)
    nets = [ec.run_scenario(econ, discount, s, uptake, horizon).net_benefit for s in rates]
    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color=th.GREY_MARK, width=1))
    fig.add_trace(go.Scatter(x=rates, y=nets, mode="lines", line=dict(color=th.WHITE, width=2),
                             hovertemplate="Save rate %{x:.0%}<br>Net %{y:$,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[save_rate], y=[r.net_benefit], mode="markers",
                             marker=dict(size=11, color=th.BLACK, line=dict(color=th.WHITE, width=2)),
                             hovertemplate="Your choice<br>%{y:$,.0f}<extra></extra>"))
    fig.add_annotation(x=save_rate, y=r.net_benefit, text=f"Your choice: {th.fmt_money(r.net_benefit)}",
                       showarrow=True, arrowhead=0, arrowcolor=th.GREY_TEXT, ax=56, ay=44, xanchor="left",
                       font=dict(size=13, color=th.WHITE), bgcolor=th.BLACK)
    if r.break_even_save_rate is not None:
        fig.add_vline(x=r.break_even_save_rate, line=dict(color=th.GREY_TEXT, width=1, dash="dot"))
        fig.add_annotation(x=r.break_even_save_rate, y=1, yref="paper", yanchor="bottom", showarrow=False,
                           text=f"Break-even {r.break_even_save_rate:.1%}", xanchor="left", xshift=4,
                           font=dict(size=12, color=th.GREY_TEXT))
    fig.update_xaxes(tickformat=".0%", title_text="Share of would-be leavers who stay", range=[0, 1])
    fig.update_yaxes(tickformat="$,.0f")
    th.titled(fig, "How the answer depends on the save rate",
              f"At {discount:.0%} off. The save rate is the least certain input.", height=400)
    st.plotly_chart(fig, width="stretch", config=th.CHART_CONFIG)

ui.assumptions_box(ec.assumptions_text(discount, save_rate, uptake, horizon),
                   title="What I assumed")

st.markdown("### Same offer, every segment")
rows = []
for s in config.SEGMENT_ORDER:
    e = ec.economics_from_customers(cust, s, month_to_month_only=mtm_only)
    if e.customers == 0:
        continue
    x = ec.run_scenario(e, discount, save_rate, uptake, horizon)
    rows.append({"Who gets the offer": e.segment, "Customers": e.customers, "Share who leave": e.churn_rate,
                 "Customers kept": x.customers_saved, "Billing kept": x.revenue_saved,
                 "Discount cost": x.discount_cost, "Net": x.net_benefit,
                 "Break-even save rate": x.break_even_save_rate})
st.dataframe(
    th.style_table(pd.DataFrame(rows), money_cols=["Billing kept", "Discount cost", "Net"],
                   pct_cols=["Share who leave", "Break-even save rate"], int_cols=["Customers", "Customers kept"]),
    hide_index=True, width="stretch")
ui.note(
    "Most blanket discounts lose money. Where few people would leave, almost everyone getting the discount was "
    "staying anyway, so it costs more than it saves. The offer only pays where a lot of the group would otherwise "
    "go. Aim it better before you make it bigger. Before rolling anything out, test the save rate against a random "
    "group that gets no offer."
)
