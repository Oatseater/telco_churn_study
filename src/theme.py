"""One shared Plotly template and chart helpers used by every page.

Warm near-black, brushed silver, one red. Bright silver marks are what to look at,
dim silver is context, and red is kept for the one mark per page that matters most.
Costs and losses use a diagonal hatch rather than a colour.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# Names kept from the earlier palette so page code reads the same; values are new.
BLACK = "#121110"         # warm near-black page
WHITE = "#E6E3DE"         # bright silver: headlines, emphasised marks (14.7:1)
GREY_TEXT = "#8A8580"     # muted silver: secondary text, second line shade (5.2:1)
GREY_MARK = "#6E6A65"     # dim silver: context marks (3.5:1)
GREY_DIM = "#3F3B37"      # de-emphasised lines in highlight mode
RULE = "#3A3633"          # 1px hairlines
GRID = "#1E1C1A"          # gridlines, barely there
RED = "#C8342C"           # matte rosso, 3.6:1; at most twice per page
SILVER = "#BDB9B3"        # emphasised bars: brushed silver, not white
GREY_DIM_BAR = "#57534F"  # context bars

# Ordered shades for up to three ordered groups (e.g. contract length). Checked
# with the dataviz palette validator on a dark surface: adjacent pairs separate
# and all clear 3:1 contrast. Each line also gets a dash pattern and a label.
ORDERED_SHADES = [WHITE, GREY_TEXT, GREY_MARK]
DASHES = ["solid", "dash", "dot"]
HATCH = dict(shape="/", fgcolor=GREY_TEXT, bgcolor=BLACK, size=6, solidity=0.3)

FONT = "'Helvetica Neue', Helvetica, 'TeX Gyre Heros', Arial, sans-serif"
SERIF = "'Bodoni Moda', Didot, 'Bodoni 72', serif"

TEMPLATE_NAME = "mono_dark"

_template = go.layout.Template(
    layout=go.Layout(
        font=dict(family=FONT, size=14, color=GREY_TEXT),
        paper_bgcolor="rgba(0,0,0,0)",   # transparent so the page grain runs through charts
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[WHITE, GREY_TEXT, GREY_MARK],
        separators=".,",
        title=dict(font=dict(size=19, color=WHITE, family=SERIF, weight=500), x=0, xanchor="left",
                   y=0.97, yanchor="top", pad=dict(b=8),
                   subtitle=dict(font=dict(size=13, color=GREY_TEXT, family=FONT))),
        margin=dict(l=8, r=24, t=76, b=64),
        showlegend=False,
        hoverlabel=dict(bgcolor="#1A1817", bordercolor=RULE, font=dict(family=FONT, size=13, color=WHITE)),
        xaxis=dict(showgrid=False, zeroline=False, showline=True, linecolor=RULE, linewidth=1,
                   ticks="", tickfont=dict(color=GREY_TEXT, size=13),
                   title=dict(font=dict(size=13, color=GREY_TEXT))),
        yaxis=dict(showgrid=True, gridcolor=GRID, gridwidth=1, zeroline=False, showline=False,
                   tickfont=dict(color=GREY_TEXT, size=13), title=dict(font=dict(size=13, color=GREY_TEXT))),
        bargap=0.58,
    )
)
pio.templates[TEMPLATE_NAME] = _template
pio.templates.default = TEMPLATE_NAME

CHART_CONFIG = {"displayModeBar": False}


def titled(fig: go.Figure, title: str, subtitle: str = "", height: int = 380) -> go.Figure:
    fig.update_layout(template=TEMPLATE_NAME, height=height,
                      title=dict(text=title, subtitle=dict(text=subtitle)),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    # Set on the figure itself: Streamlit's chart theme overrides template-level colours
    # (it was tinting gridlines blue-purple) but leaves figure-level ones alone.
    fig.update_xaxes(gridcolor=GRID, linecolor=RULE, zerolinecolor=GREY_TEXT)
    fig.update_yaxes(gridcolor=GRID, linecolor=RULE, zerolinecolor=GREY_TEXT)
    return fig


def fmt_money(x: float, decimals: int = 0) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.{decimals}f}"


def fmt_pct(x: float) -> str:
    return f"{x:.1%}"


def fmt_int(x: float) -> str:
    return f"{x:,.0f}"


def in_100(x: float) -> str:
    """A share as people: 0.586 -> '59 in 100'."""
    return f"{round(x * 100):.0f} in 100"


def hbar(labels, values, text, title: str, subtitle: str, highlight=None, xmax: float | None = None,
         hover: str = "%{y}: %{x}", height: int | None = None, ref: float | None = None,
         ref_label: str = "", accent=None) -> go.Figure:
    """Horizontal bars, direct-labelled. Highlighted bars are bright silver, accent bars red,
    the rest dim silver."""
    highlight, accent = set(highlight or []), set(accent or [])
    colors = [RED if lab in accent else SILVER if lab in highlight else GREY_DIM_BAR for lab in labels]
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h", marker=dict(color=colors, line=dict(width=0)),
        text=text, textposition="outside", cliponaxis=False,
        textfont=dict(family=FONT, size=14, color=WHITE),
        hovertemplate=hover + "<extra></extra>",
    ))
    top = max(list(values) + ([ref] if ref else []))
    fig.update_xaxes(range=[0, xmax or top * 1.35], showticklabels=False, showline=False)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=WHITE, size=14))
    if ref is not None:
        fig.add_vline(x=ref, line=dict(color=GREY_TEXT, width=1, dash="dot"))
        fig.add_annotation(x=ref, y=1, yref="paper", yanchor="bottom", xanchor="left", xshift=4,
                           text=ref_label, showarrow=False, font=dict(size=12, color=GREY_TEXT))
    h = height or max(220, 96 + 48 * len(labels))
    titled(fig, title, subtitle, height=h)
    fig.update_layout(margin=dict(l=8, r=24, t=76, b=12))  # no x-axis, so no bottom margin needed
    return fig


def hbar_rate(df, category_col: str, rate_col: str, title: str, subtitle: str,
              reference: float | None = None, reference_label: str = "Overall",
              customers_col: str | None = "customers", height: int | None = None) -> go.Figure:
    """Rates by category; bars above the reference are white, the rest grey."""
    cats = df[category_col].astype(str).tolist()
    rates = df[rate_col].tolist()
    high = [c for c, r in zip(cats, rates) if reference is not None and r > reference]
    fig = hbar(cats, rates, [f"{r:.1%}" for r in rates], title, subtitle, highlight=high,
               xmax=max(rates + ([reference] if reference else [])) * 1.3,
               hover="%{y}<br>Churn rate %{x:.1%}", height=height,
               ref=reference, ref_label=f"{reference_label} {reference:.1%}" if reference is not None else "")
    if customers_col:
        fig.data[0].customdata = df[customers_col].tolist()
        fig.data[0].hovertemplate = "%{y}<br>Churn rate %{x:.1%}<br>%{customdata:,} customers<extra></extra>"
    return fig


def style_table(df, money_cols=(), pct_cols=(), int_cols=(), na="Not reachable", extra=None):
    """Pandas Styler with thousands separators, whole dollars and one-decimal percentages."""
    df = df.copy()
    fmt = {}
    for c in pct_cols:
        # Streamlit shows null cells as "None" regardless of the Styler, so columns with
        # gaps are converted to display strings up front.
        if df[c].isna().any():
            df[c] = [na if v is None or v != v else f"{v:.1%}" for v in df[c]]
    pct_cols = [c for c in pct_cols if pd.api.types.is_numeric_dtype(df[c])]
    for c in money_cols:
        fmt[c] = lambda v: "" if v != v or v is None else fmt_money(v)
    for c in pct_cols:
        fmt[c] = lambda v: na if v is None or v != v else f"{v:.1%}"
    for c in int_cols:
        fmt[c] = lambda v: "" if v != v or v is None else f"{v:,.0f}"
    fmt.update(extra or {})
    return df.style.format(fmt)


def share_bar(labels, values, title: str, subtitle: str, accent: str, height: int = 230) -> go.Figure:
    """One horizontal bar split into parts: how a single total divides up.
    The accent part is red; the others step down through the silvers."""
    total = float(sum(values))
    shades = iter([GREY_TEXT, GREY_MARK, GREY_DIM, RULE])
    fig = go.Figure()
    start = 0.0
    for lab, v in zip(labels, values):
        color = RED if lab == accent else next(shades)
        fig.add_trace(go.Bar(x=[v], y=[""], orientation="h", base=start, marker=dict(color=color, line=dict(width=0)),
                             hovertemplate=f"{lab}<br>%{{x:$,.0f}} ({v / total:.1%})<extra></extra>"))
        start += v
    # Labels: the accent part above-left, small parts alternate above and below at their right edge.
    start = 0.0
    for i, (lab, v) in enumerate(zip(labels, values)):
        share = v / total
        txt = f"{lab}<br>{fmt_money(v)}  {share:.0%}"
        if lab == accent:
            fig.add_annotation(x=start, y=0.5, yref="y domain", yshift=44, xanchor="left", yanchor="bottom",
                               text=txt, showarrow=False, align="left", font=dict(size=14, color=WHITE))
        else:
            above = i % 2 == 1
            fig.add_annotation(x=start + v, y=0.5, yref="y domain", yshift=44 if above else -44,
                               xanchor="right", yanchor="bottom" if above else "top", text=txt, showarrow=False,
                               align="right", font=dict(size=13, color=GREY_TEXT))
        start += v
    fig.update_layout(barmode="overlay", bargap=0.0)
    fig.update_xaxes(range=[0, total], showticklabels=False, showline=False, showgrid=False)
    fig.update_yaxes(showticklabels=False, showgrid=False, range=[-1.6, 1.6])
    titled(fig, title, subtitle, height=height)
    fig.update_traces(width=0.55)
    fig.update_layout(margin=dict(l=8, r=8, t=76, b=8))
    return fig


def dot_plot(labels, values, text, title: str, subtitle: str, accent: str | None = None,
             xmax: float | None = None, hover: str = "%{y}: %{x:.1%}", height: int | None = None) -> go.Figure:
    """Dots on hairline stems: lighter than bars when the point is the ranking."""
    fig = go.Figure()
    for lab, v in zip(labels, values):
        fig.add_trace(go.Scatter(x=[0, v], y=[lab, lab], mode="lines", line=dict(color=RULE, width=1),
                                 hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=values, y=labels, mode="markers+text", text=text, textposition="middle right",
        textfont=dict(size=14, color=WHITE),
        marker=dict(size=13, color=[RED if lab == accent else SILVER for lab in labels],
                    line=dict(width=0)),
        hovertemplate=hover + "<extra></extra>"))
    fig.update_xaxes(range=[0, xmax or max(values) * 1.35], showticklabels=False, showline=False, showgrid=False)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=WHITE, size=14))
    titled(fig, title, subtitle, height=height or 96 + 52 * len(labels))
    fig.update_layout(margin=dict(l=8, r=24, t=76, b=12))
    return fig
