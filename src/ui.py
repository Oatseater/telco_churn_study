"""Small HTML building blocks shared by the dashboard pages."""
from __future__ import annotations

from html import escape

import streamlit as st

from src import config


def load_css() -> None:
    css = (config.ASSETS_DIR / "style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def disclaimer() -> None:
    st.markdown(f'<div class="disclaimer">{escape(config.DISCLAIMER, quote=False)}</div>', unsafe_allow_html=True)


def page_header(answer: str, support: str = "", enter: bool = True) -> None:
    """Open a page with the answer as one plain sentence. `enter` gives it the slow entrance."""
    st.markdown(
        f'<div class="page-header{" enter" if enter else ""}"><h1>{escape(answer)}</h1>'
        + (f'<p class="support">{escape(support)}</p>' if support else "") + "</div>",
        unsafe_allow_html=True,
    )


def ledger(rows: list[tuple[str, str]], accent: int | None = None, caption: str = "") -> None:
    """A spec sheet: label on the left, value on the right, hairlines between.
    `accent` is the index of the one row whose value is red, if any."""
    items = "".join(
        f'<div class="row"><dt>{escape(k)}</dt><dd class="{"accent" if i == accent else ""}">{escape(v)}</dd></div>'
        for i, (k, v) in enumerate(rows))
    cap = f'<p class="ledger-caption">{escape(caption)}</p>' if caption else ""
    st.markdown(f'<dl class="ledger">{items}</dl>{cap}', unsafe_allow_html=True)


def section(title: str, intro: str = "") -> None:
    """Start a deeper part of the page."""
    st.markdown(
        f'<div class="section"><h2>{escape(title)}</h2>'
        + (f"<p>{escape(intro)}</p>" if intro else "") + "</div>",
        unsafe_allow_html=True,
    )


def note(html: str) -> None:
    """A plain paragraph. Caller is responsible for escaping any data in html."""
    st.markdown(f'<div class="note">{html}</div>', unsafe_allow_html=True)


def assumptions_box(items: list[str], title: str = "Assumptions") -> None:
    lis = "".join(f"<li>{escape(i)}</li>" for i in items)
    st.markdown(f'<div class="assumptions"><h3>{escape(title)}</h3><ol>{lis}</ol></div>',
                unsafe_allow_html=True)
