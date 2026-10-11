"""Streamlit entry point: shared styling, persistent disclaimer and page routing.

Run:  streamlit run app.py   (after python run_pipeline.py)
"""
import streamlit as st

st.set_page_config(
    page_title="Telco churn",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src import config, theme, ui  # noqa: E402,F401  (theme registers the shared Plotly template)

ui.load_css()

pages = [
    st.Page("pages/overview.py", title="Overview", default=True),
    st.Page("pages/retention.py", title="Retention"),
    st.Page("pages/segments.py", title="Segments"),
    st.Page("pages/calculator.py", title="Retention calculator"),
]
nav = st.navigation(pages)

with st.sidebar:
    st.markdown(
        '<div class="sidebar-note"><b>Data</b><br>IBM Telco Customer Churn sample, '
        "public. One row per customer.</div>"
        # The one personal line. Change it to whatever you want it to say.
        '<div class="signature">I did this for fun.</div>',
        unsafe_allow_html=True,
    )

ui.disclaimer()
nav.run()
