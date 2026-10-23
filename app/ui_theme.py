from __future__ import annotations

import streamlit as st


def apply_ichiban_theme() -> None:
    """Apply ICHIBAN's approachable professional UI styling.

    UI-only helper. It does not touch valuation logic, report routing,
    comp math, prompt building, or parser behavior.
    """
    st.markdown(
        """
        <style>
        :root {
            --ichiban-ink: #1F2933;
            --ichiban-muted: #667085;
            --ichiban-navy: #1F3A5F;
            --ichiban-teal: #2F6F73;
            --ichiban-teal-soft: #E7F1F1;
            --ichiban-sage: #DDE7DF;
            --ichiban-gold: #C89B3C;
            --ichiban-cream: #F7F4EF;
            --ichiban-card: #FFFFFF;
            --ichiban-border: #D8DEE6;
            --ichiban-alert: #FFF7E0;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(47,111,115,0.10), transparent 34rem),
                linear-gradient(180deg, #F7F4EF 0%, #FFFFFF 62%);
            color: var(--ichiban-ink);
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #203A5C 0%, #1F3A5F 100%);
            border-right: 1px solid rgba(255,255,255,0.12);
        }

        section[data-testid="stSidebar"] * {
            color: #F8FAFC !important;
        }

        section[data-testid="stSidebar"] a {
            border-radius: 10px;
        }

        section[data-testid="stSidebar"] a:hover {
            background-color: rgba(255,255,255,0.10);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 4rem;
            max-width: 1180px;
        }

        h1, h2, h3 {
            color: var(--ichiban-navy);
            letter-spacing: -0.015em;
        }

        h1 {
            font-weight: 750;
            border-bottom: 3px solid var(--ichiban-gold);
            padding-bottom: 0.35rem;
            margin-bottom: 0.75rem;
        }

        h2, h3 {
            font-weight: 680;
        }

        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stMarkdownContainer"] li {
            line-height: 1.55;
        }

        div[data-testid="stAlert"] {
            border-radius: 14px;
            border: 1px solid var(--ichiban-border);
            box-shadow: 0 2px 10px rgba(31,58,95,0.05);
        }

        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.92);
            border: 1px solid var(--ichiban-border);
            border-radius: 14px;
            padding: 0.85rem 1rem;
            box-shadow: 0 3px 12px rgba(31,58,95,0.06);
        }

        div[data-testid="stMetricLabel"] {
            color: var(--ichiban-muted);
            font-weight: 650;
        }

        div[data-testid="stExpander"] {
            background: rgba(255,255,255,0.96);
            border: 1px solid var(--ichiban-border);
            border-radius: 14px;
            box-shadow: 0 3px 12px rgba(31,58,95,0.05);
            overflow: hidden;
        }

        div[data-testid="stExpander"] summary {
            color: var(--ichiban-navy);
            font-weight: 700;
        }

        div[data-testid="stForm"] {
            background: rgba(255,255,255,0.92);
            border: 1px solid var(--ichiban-border);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            box-shadow: 0 4px 18px rgba(31,58,95,0.05);
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 999px;
            border: 1px solid rgba(47,111,115,0.35);
            font-weight: 700;
            padding: 0.52rem 1.05rem;
            transition: all 120ms ease-in-out;
        }

        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {
            background: linear-gradient(135deg, var(--ichiban-teal), #245E63);
            border: 1px solid #245E63;
            color: white;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(47,111,115,0.22);
        }

        div[data-baseweb="input"] input,
        div[data-baseweb="textarea"] textarea,
        div[data-baseweb="select"] {
            border-radius: 12px !important;
        }

        label, .stRadio label, .stCheckbox label {
            color: var(--ichiban-ink) !important;
            font-weight: 600;
        }

        .ichiban-hero {
            background: linear-gradient(135deg, rgba(31,58,95,0.98), rgba(47,111,115,0.95));
            color: white;
            border-radius: 20px;
            padding: 1.35rem 1.5rem;
            margin: 0.5rem 0 1.25rem 0;
            box-shadow: 0 10px 30px rgba(31,58,95,0.18);
        }

        .ichiban-hero h2, .ichiban-hero h3, .ichiban-hero p {
            color: white;
            margin-bottom: 0.25rem;
        }

        .ichiban-kicker {
            color: #E8D8B0;
            font-size: 0.82rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.2rem;
        }

        .ichiban-card {
            background: rgba(255,255,255,0.94);
            border: 1px solid var(--ichiban-border);
            border-left: 5px solid var(--ichiban-teal);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            margin: 0.75rem 0;
            box-shadow: 0 4px 18px rgba(31,58,95,0.06);
        }

        .ichiban-card strong {
            color: var(--ichiban-navy);
        }

        .ichiban-soft-note {
            background: var(--ichiban-teal-soft);
            border: 1px solid rgba(47,111,115,0.22);
            border-radius: 14px;
            padding: 0.85rem 1rem;
            color: var(--ichiban-ink);
        }

        .ichiban-status-tarzan {
            display: inline-block;
            background: #E7F1F1;
            border: 1px solid rgba(47,111,115,0.28);
            color: #245E63;
            border-radius: 999px;
            padding: 0.2rem 0.7rem;
            font-weight: 800;
            font-size: 0.82rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ichiban_hero(title: str, subtitle: str | None = None, kicker: str = "ICHIBAN INSIGHT") -> None:
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="ichiban-hero">
            <div class="ichiban-kicker">{kicker}</div>
            <h2>{title}</h2>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
