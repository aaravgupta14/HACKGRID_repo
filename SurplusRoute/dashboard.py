import base64
import html
import json
from pathlib import Path
from datetime import date, timedelta
from datetime import time as datetime_time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_option_menu import option_menu

from surplusroute import config, marketplace
from surplusroute.agent import SurplusRouteAgent
from surplusroute.geo import DISTRICT_COORDINATES, known_districts
from surplusroute.i18n import LANGUAGES, district_name, option, t
from surplusroute.model import model_path
from surplusroute.prepare import panel_path
from surplusroute.public_buyers import PUBLIC_BUYERS_CHECKED_ON

PRODUCT_ICON = Path(__file__).resolve().parent / "assets" / "product_icon.png"
st.set_page_config(page_title="SurplusRoute", page_icon=str(PRODUCT_ICON) if PRODUCT_ICON.exists() else None,
                   layout="wide", initial_sidebar_state="expanded")

GREEN, AMBER, RED = "#2e7d32", "#e08a00", "#c62828"
DEEP, INK, MUTED, SURFACE = "#123d1a", "#1b2e1d", "#5b7260", "#f5faf4"
LEVEL_COLORS = {"HIGH": RED, "WATCH": AMBER, "NORMAL": GREEN}
LEVEL_ORDER = ["HIGH", "WATCH", "NORMAL"]
PAGES = ["alerts", "sell", "matches", "register", "how"]
PAGE_ICONS = ["bell", "box-seam", "people", "shop", "info-circle"]
FONT = "Poppins, 'Noto Sans Kannada', 'Noto Sans Devanagari', sans-serif"

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&family=Noto+Sans+Kannada:wght@400;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap');
    html, body, [class*="css"], .stMarkdown, .stText, button, input, label, textarea, select {
        font-family: Poppins, 'Noto Sans Kannada', 'Noto Sans Devanagari', sans-serif;
    }
    .stApp {background: linear-gradient(180deg, #f3f9f1 0%, #ffffff 420px);}
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer {visibility: hidden; height: 0;}
    .block-container {padding-top: 1.4rem; padding-bottom: 1rem; max-width: 1320px;}
    [data-testid="stSidebar"] {background: linear-gradient(180deg, #0f3316 0%, #1d5a26 100%);}
    [data-testid="stSidebar"] * {color: #eaf6ea !important;}
    [data-testid="stSidebar"] [data-baseweb="select"] * {color: #1b2e1d !important;}
    [data-testid="stSidebar"] [data-baseweb="select"] > div {background: #ffffff; border-radius: 10px;}
    .sr-brand {display: flex; align-items: center; gap: 12px; margin: 4px 0 18px 0;}
    .sr-logo {width: 46px; height: 46px; border-radius: 14px; background: linear-gradient(135deg, #9be15d, #2e7d32);
              display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.15rem;
              color: #ffffff !important; box-shadow: 0 6px 16px rgba(0,0,0,0.25);}
    .sr-logo-light {width: 64px; height: 64px; background: #ffffff; padding: 4px; overflow: hidden;}
    .sr-logo-img {width: 100%; height: 100%; object-fit: contain; border-radius: 10px;}
    .sr-brand b {font-size: 1.25rem; letter-spacing: 0.2px;}
    .sr-brand span {display: block; font-size: 0.78rem; opacity: 0.8;}
    .sr-side-note {font-size: 0.78rem; opacity: 0.75; margin-top: 18px; line-height: 1.4;}

    .sr-hero {position: relative; overflow: hidden; border-radius: 22px; padding: 30px 34px; color: #ffffff;
              background: radial-gradient(circle at 85% 20%, rgba(155,225,93,0.45) 0, rgba(155,225,93,0) 38%),
                          radial-gradient(circle at 10% 110%, rgba(255,255,255,0.18) 0, rgba(255,255,255,0) 40%),
                          linear-gradient(120deg, #0f3316 0%, #1f6b2a 55%, #3f9a3a 100%);
              box-shadow: 0 18px 40px rgba(18,61,26,0.25); margin-bottom: 18px;}
    .sr-hero h1 {color: #ffffff; font-size: 2.5rem; font-weight: 800; margin: 0; letter-spacing: -0.5px;}
    .sr-hero p {color: #e3f4df; font-size: 1.08rem; margin: 6px 0 16px 0; max-width: 760px;}
    .sr-chip {display: inline-block; background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.28);
              border-radius: 999px; padding: 6px 14px; margin: 0 8px 6px 0; font-size: 0.9rem; color: #ffffff;
              backdrop-filter: blur(4px);}
    .sr-chip b {color: #ffffff;}

    .sr-kpis {display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin: 6px 0 18px 0;}
    .sr-kpi {background: #ffffff; border-radius: 18px; padding: 12px 16px 12px 16px; border: 1px solid #e3efe1;
             border-top: 6px solid #2e7d32; box-shadow: 0 6px 18px rgba(18,61,26,0.06);}
    .sr-kpi small {display: block; color: #5b7260; font-size: 0.82rem; line-height: 1.3; min-height: 2.1em;}
    .sr-kpi b {display: block; font-size: clamp(1.15rem, 1.9vw, 1.7rem); font-weight: 800; color: #1b2e1d; line-height: 1.15; word-break: normal; overflow-wrap: normal;}

    .sr-section {font-size: 1.3rem; font-weight: 700; color: #123d1a; margin: 22px 0 10px 0;}
    .sr-sub {color: #5b7260; font-size: 0.92rem; margin: -6px 0 10px 0;}

    .sr-agent {background: #ffffff; border: 1px solid #e3efe1; border-radius: 20px; padding: 16px 18px;
               box-shadow: 0 6px 18px rgba(18,61,26,0.05); margin-bottom: 8px;}
    .sr-agent-title {font-weight: 700; color: #123d1a; margin-bottom: 12px; font-size: 1rem;}
    .sr-steps {display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px;}
    .sr-step {position: relative; background: #f5faf4; border-radius: 14px; padding: 12px 12px 12px 14px;}
    .sr-step .n {width: 28px; height: 28px; border-radius: 50%; background: #2e7d32; color: #ffffff; font-weight: 700;
                 display: inline-flex; align-items: center; justify-content: center; font-size: 0.85rem; margin-right: 6px;}
    .sr-step b {color: #123d1a;}
    .sr-step p {margin: 6px 0 6px 0; color: #4b6350; font-size: 0.85rem; line-height: 1.3;}
    .sr-tag {display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: 0.72rem; font-weight: 600;}
    .sr-tag.a {background: #e3f2fd; color: #0d47a1;}
    .sr-tag.p {background: #f3e5f5; color: #6a1b9a;}

    .sr-panel {background: #ffffff; border: 1px solid #e3efe1; border-radius: 20px; padding: 10px 14px 4px 14px;
               box-shadow: 0 6px 18px rgba(18,61,26,0.05);}

    .sr-card {background: #ffffff; border: 1px solid #e3efe1; border-radius: 20px; padding: 18px 20px;
              box-shadow: 0 10px 26px rgba(18,61,26,0.07); border-top: 6px solid #2e7d32; margin-top: 6px;}
    .sr-card-head {display: flex; justify-content: space-between; align-items: center; gap: 12px;}
    .sr-card-head > div:first-child {min-width: 0; flex: 1 1 auto;}
    .sr-card h3 {margin: 0; color: #1b2e1d; font-size: 1.3rem; font-weight: 700; word-break: normal !important; overflow-wrap: normal !important; hyphens: none;}
    .sr-pill {display: inline-block; background: #2e7d32; color: #ffffff; border-radius: 999px; padding: 4px 12px;
              font-size: 0.85rem; font-weight: 600; margin-top: 4px;}
    .sr-gauge {width: 92px; height: 92px; border-radius: 50%; flex: 0 0 92px;
               background: #edf3ec;
               display: flex; align-items: center; justify-content: center;}
    .sr-gauge div {width: 70px; height: 70px; border-radius: 50%; background: #ffffff; display: flex; flex-direction: column;
                   align-items: center; justify-content: center;}
    .sr-gauge b {font-size: 1.25rem; color: #1b2e1d; line-height: 1;}
    .sr-gauge span {font-size: 0.62rem; color: #5b7260; text-align: center; line-height: 1.1; margin-top: 2px;}
    .sr-reason {margin: 12px 0; font-size: 1.02rem; color: #25402a;}
    .sr-prices {display: flex; align-items: center; gap: 12px; background: #f5faf4; border-radius: 14px; padding: 12px 14px;}
    .sr-prices .col small {display: block; color: #5b7260; font-size: 0.78rem;}
    .sr-prices .col b {font-size: 1.35rem; color: #1b2e1d;}
    .sr-prices .arrow {font-size: 1.6rem; color: #5b7260; font-weight: 700;}
    .sr-mini {display: flex; gap: 10px; margin: 10px 0; flex-wrap: wrap;}
    .sr-mini div {background: #ffffff; border: 1px solid #e3efe1; border-radius: 12px; padding: 6px 12px; font-size: 0.86rem; color: #25402a;}
    .sr-mini b {color: #1b2e1d;}
    .sr-todo {background: #fff7e0; border-radius: 14px; padding: 10px 14px; color: #3e2f00; margin: 8px 0;}
    .sr-better {font-size: 0.9rem; color: #25402a; margin-top: 8px;}
    .sr-better ul {margin: 4px 0 0 18px; padding: 0;}
    .sr-small {color: #5b7260; font-size: 0.82rem; margin-top: 6px;}

    .sr-buyer {background: #ffffff; border: 1px solid #e3efe1; border-radius: 18px; padding: 16px 18px; margin: 8px 0;
               box-shadow: 0 6px 16px rgba(18,61,26,0.05);}
    .sr-buyer-head {display: flex; gap: 12px; align-items: center;}
    .sr-avatar {width: 46px; height: 46px; border-radius: 14px; background: linear-gradient(135deg, #c5e8b7, #7cc36b);
                color: #123d1a; font-weight: 800; display: flex; align-items: center; justify-content: center;}
    .sr-buyer b.name {font-size: 1.08rem; color: #1b2e1d;}
    .sr-status {border-radius: 999px; padding: 2px 10px; font-size: 0.75rem; font-weight: 600; color: #ffffff; background: #2e7d32;}
    .sr-bar {height: 8px; background: #edf3ec; border-radius: 999px; overflow: hidden; margin: 8px 0 4px 0;}
    .sr-bar div {height: 100%; background: linear-gradient(90deg, #7cc36b, #2e7d32); border-radius: 999px;}
    .sr-contact {font-weight: 600; color: #123d1a; margin-top: 6px;}
    .sr-verified {border: 1.5px solid #2e7d32; color: #2e7d32; background: #eef7ec; border-radius: 999px;
                  padding: 1px 10px; font-size: 0.75rem; font-weight: 700;}
    .sr-trust {color: #7a5a00; font-size: 0.86rem; font-weight: 600; margin-top: 6px;}
    .sr-hint {background: #eef7ec; border: 1px solid #cfe6c9; border-radius: 14px; padding: 10px 14px; margin: 4px 0 12px 0;}
    .sr-hint b {color: #123d1a; display: block; font-size: 1.05rem;}
    .sr-hint span {color: #5b7260; font-size: 0.82rem;}
    .sr-slip {width: 100%; border-collapse: collapse; margin: 6px 0 10px 0;}
    .sr-slip td {padding: 8px 6px; border-bottom: 1px dashed #d7ead3; color: #25402a;}
    .sr-slip td:last-child {text-align: right; color: #1b2e1d;}
    .sr-fee {display: flex; justify-content: flex-end; color: #5b7260; font-size: 0.95rem;}
    .sr-receive {text-align: right; font-size: 1.2rem; font-weight: 800; color: #123d1a; margin: 4px 0 10px 0;}
    .sr-escrow {background: #fff7e0; border-radius: 12px; padding: 10px 12px; color: #3e2f00; font-size: 0.88rem; margin-bottom: 10px;}
    .sr-phone {background: #123d1a; color: #ffffff; border-radius: 12px; padding: 12px 14px; font-size: 1.15rem; font-weight: 700; text-align: center;}

    .sr-res {background: #ffffff; border: 1px solid #e3efe1; border-radius: 20px; padding: 18px 20px; height: 100%;
             box-shadow: 0 6px 18px rgba(18,61,26,0.05);}
    .sr-res .num {width: 38px; height: 38px; border-radius: 12px; background: linear-gradient(135deg, #9be15d, #2e7d32);
                  color: #ffffff; font-weight: 800; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 8px;}
    .sr-res h4 {margin: 2px 0 6px 0; color: #123d1a;}
    .sr-res p {color: #3f5844; margin: 0; line-height: 1.45;}
    .sr-proof {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 8px;}
    .sr-proof div {background: linear-gradient(135deg, #0f3316, #2e7d32); color: #ffffff; border-radius: 18px; padding: 18px 20px;}
    .sr-proof b {display: block; font-size: 2.2rem; font-weight: 800; color: #ffffff;}
    .sr-proof span {color: #dff1da; font-size: 0.92rem;}

    .stButton > button, .stFormSubmitButton > button {border-radius: 12px; font-weight: 600; padding: 0.5rem 1rem;}
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background: linear-gradient(90deg, #2e7d32, #43a047); border: none; box-shadow: 0 6px 14px rgba(46,125,50,0.3);}
    [data-testid="stForm"] {background: #ffffff; border: 1px solid #e3efe1; border-radius: 20px; padding: 18px 20px;
                            box-shadow: 0 6px 18px rgba(18,61,26,0.05);}
    .sr-footer {text-align: center; margin-top: 40px; padding: 22px 0 8px 0; border-top: 1px solid #d7ead3;}
    .sr-footer b {color: #1f6b2a; font-size: 1.1rem; letter-spacing: 0.3px; display: block;}
    .sr-team-logo {width: 170px; max-width: 45vw; border-radius: 22px; display: block; margin: 0 auto 12px auto;
                   box-shadow: 0 10px 24px rgba(18,61,26,0.15);}
    .sr-footer span {display: block; color: #5b7260; font-size: 0.8rem; margin-top: 4px;}
    @media (max-width: 1250px) {
        .sr-kpis {grid-template-columns: repeat(3, minmax(0, 1fr));}
    }
    @media (max-width: 1400px) {
        .sr-gauge {width: 74px; height: 74px; flex: 0 0 74px;}
        .sr-gauge div {width: 56px; height: 56px;}
        .sr-gauge b {font-size: 1rem;}
        .sr-gauge span {font-size: 0.55rem;}
        .sr-card h3 {font-size: 1.1rem;}
    }
    @media (max-width: 900px) {
        .sr-kpis {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .sr-steps {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .sr-proof {grid-template-columns: 1fr;}
        .sr-hero h1 {font-size: 1.9rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def image_html(name, css_class, alt):
    folder = Path(__file__).resolve().parent / "assets"
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    for suffix, kind in mime.items():
        path = folder / f"{name}{suffix}"
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode()
            return f"<img class='{css_class}' src='data:{kind};base64,{data}' alt='{alt}'>"
    return ""


def team_logo_html():
    return image_html("team_logo", "sr-team-logo", "Team Ghee Podi Dosa logo")


def esc(value):
    return html.escape(str(value))


def stamp(commodity, state):
    return (model_path(commodity, state).stat().st_mtime, panel_path(commodity, state).stat().st_mtime)


@st.cache_resource(show_spinner=False)
def load_agent(commodity, state, model_stamp):
    return SurplusRouteAgent(commodity, state)


@st.cache_data(show_spinner=False)
def agent_report(commodity, state, as_of, model_stamp):
    return load_agent(commodity, state, model_stamp).run(as_of)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return None


def kg(value_per_quintal):
    return None if value_per_quintal is None or pd.isna(value_per_quintal) else value_per_quintal / 100


def money(value):
    return f"{value:,.0f}" if value >= 10 else f"{value:,.1f}"


def go_to_sell(alert):
    st.session_state["prefill"] = alert
    st.session_state["force_page"] = "sell"


def days_text(alert, lang):
    low = alert["buffer_days_low"] if alert["buffer_days_low"] is not None else alert["model_days_to_bottom"]
    high = alert["buffer_days_high"] if alert["buffer_days_high"] is not None else alert["model_days_to_bottom"]
    return t("days_about", lang, low=low) if low == high else t("days_range", lang, low=low, high=high)


def reason_text(alert, lang, crop_label):
    code = alert["reason_code"]
    if code == "supply_rush":
        return t("reason_supply_rush", lang, crop=crop_label, pct=f"{max(alert['arrival_vs_baseline_pct'], 0):.0f}")
    if code == "price_high":
        return t("reason_price_high", lang, pct=f"{alert['price_vs_baseline_pct']:.0f}")
    return t(f"reason_{code}", lang)


def style_figure(figure, height=360, title=None):
    figure.update_layout(
        height=height, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", font=dict(family=FONT, size=13, color=INK),
        margin=dict(l=8, r=8, t=50 if title else 24, b=8), hoverlabel=dict(font=dict(family=FONT)),
        legend=dict(orientation="h", y=-0.16, x=0, font=dict(size=12)),
    )
    if title:
        figure.update_layout(title=dict(text=title, font=dict(size=16, color=DEEP, family=FONT), x=0.01))
    return figure


def hero(commodity_label, state_label, as_of, lang):
    st.markdown(
        f"""
        <div class='sr-hero'>
          <h1>SurplusRoute</h1>
          <p>{esc(t('tagline', lang))}</p>
          <span class='sr-chip'>{esc(commodity_label)}</span>
          <span class='sr-chip'>{esc(state_label)}</span>
          <span class='sr-chip'>{esc(t('showing', lang))}: <b>{esc(as_of.strftime('%d %b %Y'))}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_row(report, lang):
    alerts = report["alerts"]
    tiles = []
    for level in LEVEL_ORDER:
        count = sum(a["risk_level"] == level for a in alerts)
        tiles.append((LEVEL_COLORS[level], esc(f"{t(f'level_{level}', lang)} ({t('markets_count', lang)})"), str(count)))
    tonnes = sum(a["arrival_tonnes"] or 0 for a in alerts)
    supply = report["summary"]["state_arrival_vs_baseline_pct"]
    tiles.append(("#5b7260", esc(t("kpi_arrived", lang)), esc(t("tonnes", lang, value=f"{tonnes:,.0f}"))))
    supply_text = f"{supply:+.0f}%" if supply is not None else "-"
    tiles.append((RED if (supply or 0) >= 20 else GREEN, esc(t("kpi_supply", lang)), supply_text))
    body = "".join(f"<div class='sr-kpi' style='border-top-color:{c}'><small>{label}</small><b>{value}</b></div>" for c, label, value in tiles)
    st.markdown(f"<div class='sr-kpis'>{body}</div>", unsafe_allow_html=True)


def agent_strip(report, lang):
    steps = [
        ("step_look", t("step_look_desc", lang, n=report["summary"]["districts_tracked"]), "a"),
        ("step_understand", t("step_understand_desc", lang), "a"),
        ("step_predict", t("step_predict_desc", lang), "p"),
        ("step_decide", t("step_decide_desc", lang), "a"),
        ("step_match", t("step_match_desc", lang), "a"),
    ]
    cells = "".join(
        f"<div class='sr-step'><span class='n'>{i}</span><b>{esc(t(key, lang))}</b><p>{esc(desc)}</p>"
        f"<span class='sr-tag {kind}'>{esc(t('tag_analysis' if kind == 'a' else 'tag_prediction', lang))}</span></div>"
        for i, (key, desc, kind) in enumerate(steps, start=1)
    )
    st.markdown(
        f"<div class='sr-agent'><div class='sr-agent-title'>{esc(t('agent_title', lang))}</div>"
        f"<div class='sr-steps'>{cells}</div></div>",
        unsafe_allow_html=True,
    )


def risk_map(alerts, lang, crop_label):
    figure = go.Figure()
    base_lat = [c[0] for c in DISTRICT_COORDINATES.values()]
    base_lon = [c[1] for c in DISTRICT_COORDINATES.values()]
    figure.add_trace(go.Scattermapbox(lat=base_lat, lon=base_lon, mode="markers", hoverinfo="skip", showlegend=False,
                                      marker=dict(size=6, color="#9fb7a2", opacity=0.6)))
    for level in LEVEL_ORDER:
        rows = [a for a in alerts if a["risk_level"] == level and a["district"].lower() in DISTRICT_COORDINATES]
        if not rows:
            continue
        coords = [DISTRICT_COORDINATES[a["district"].lower()] for a in rows]
        tonnes = np.array([max(a["arrival_tonnes"] or 0, 1) for a in rows])
        names = [district_name(a["district"], lang) for a in rows]
        figure.add_trace(go.Scattermapbox(
            lat=[c[0] for c in coords], lon=[c[1] for c in coords], mode="markers+text",
            name=t(f"level_{level}", lang), text=names, textposition="top right",
            textfont=dict(size=12, color=INK),
            marker=dict(size=np.clip(np.sqrt(tonnes) * 1.6, 14, 60), color=LEVEL_COLORS[level], opacity=0.85),
            customdata=[[f"{a['crash_probability']:.0%}", money(kg(a["modal_price"])), f"{a['arrival_tonnes'] or 0:,.0f}"] for a in rows],
            hovertemplate=(f"<b>%{{text}}</b><br>{esc(t('chance', lang))}: %{{customdata[0]}}"
                           f"<br>{esc(t('price_today', lang))}: ₹%{{customdata[1]}}/kg"
                           f"<br>{esc(t('arrived_today', lang))}: %{{customdata[2]}} t<extra></extra>"),
        ))
    figure.update_layout(mapbox=dict(style="open-street-map", center=dict(lat=14.6, lon=76.3), zoom=5.35))
    style_figure(figure, height=440)
    figure.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=0.02, x=0.02,
                         bgcolor="rgba(255,255,255,0.85)"))
    return figure


def risk_ranking(alerts, lang):
    rows = sorted(alerts, key=lambda a: a["crash_probability"])
    figure = go.Figure(go.Bar(
        x=[a["crash_probability"] * 100 for a in rows], y=[district_name(a["district"], lang) for a in rows],
        orientation="h", marker=dict(color=[LEVEL_COLORS[a["risk_level"]] for a in rows], cornerradius=6),
        text=[f"{a['crash_probability']:.0%}" for a in rows],
        customdata=[t(f"level_{a['risk_level']}", lang) for a in rows],
        textposition="outside", cliponaxis=False, textfont=dict(size=13, color=INK),
        hovertemplate="<b>%{y}</b><br>%{x:.0f}% | %{customdata}<extra></extra>", showlegend=False,
    ))
    for level in LEVEL_ORDER:
        figure.add_bar(x=[None], y=[None], orientation="h", marker_color=LEVEL_COLORS[level], name=t(f"level_{level}", lang))
    figure.add_vline(x=config.RISK_HIGH * 100, line=dict(color=RED, dash="dot", width=2))
    figure.add_annotation(x=config.RISK_HIGH * 100, y=1.02, yref="paper", text=t("act_line", lang), showarrow=False,
                          font=dict(color=RED, size=12))
    figure.update_xaxes(range=[0, 112], showgrid=False, visible=False)
    figure.update_yaxes(showgrid=False, tickfont=dict(size=13))
    style_figure(figure, height=440)
    figure.update_layout(margin=dict(l=130, r=48, t=30, b=8), bargap=0.35,
                         legend=dict(orientation="h", y=-0.08, x=0))
    figure.update_yaxes(automargin=True)
    return figure


def alert_card(alert, lang, crop_label):
    level = alert["risk_level"]
    color = LEVEL_COLORS[level]
    percent = round(alert["crash_probability"] * 100)
    better = ""
    if alert["reroute_to"]:
        items = "".join(
            "<li>" + esc(t("better_price_row", lang, district=district_name(o["district"], lang),
                           price=money(kg(o["modal_price"])), gap=money(kg(o["price_gap_per_quintal"])))) + "</li>"
            for o in alert["reroute_to"][:2]
        )
        better = f"<div class='sr-better'><b>{esc(t('better_price', lang))}</b><ul>{items}</ul></div>"
    mandis = f"<div class='sr-small'>{esc(t('markets', lang))}: {esc(', '.join(alert['mandis'][:5]))}</div>" if alert["mandis"] else ""
    st.markdown(
        f"""
        <div class='sr-card' style='border-top-color:{color}'>
          <div class='sr-card-head'>
            <div><h3>{esc(district_name(alert['district'], lang))}</h3><span class='sr-pill' style='background:{color}'>{esc(t(f'level_{level}', lang))}</span></div>
            <div class='sr-gauge' style='background:conic-gradient({color} {percent}%, #edf3ec 0)'><div><b>{percent}%</b><span>{esc(t('tag_prediction', lang))}</span></div></div>
          </div>
          <div class='sr-reason'>{esc(reason_text(alert, lang, crop_label))}</div>
          <div class='sr-prices'>
            <div class='col'><small>{esc(t('price_today', lang))}</small><b>{esc(t('per_kg', lang, value=money(kg(alert['modal_price']))))}</b></div>
            <div class='arrow' style='color:{color}'>&rarr;</div>
            <div class='col'><small>{esc(t('may_fall_to', lang))}</small><b>{esc(t('per_kg', lang, value=money(kg(alert['projected_bottom_price']))))}</b></div>
          </div>
          <div class='sr-mini'>
            <div>{esc(t('days_left', lang))}: <b>{esc(days_text(alert, lang))}</b></div>
            <div>{esc(t('arrived_today', lang))}: <b>{esc(t('tonnes', lang, value=f"{alert['arrival_tonnes'] or 0:,.0f}"))}</b></div>
          </div>
          <div class='sr-todo'><b>{esc(t('what_to_do', lang))}:</b> {esc(t(f"action_{alert['action_code']}", lang))}</div>
          {better}
          {mandis}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button(t("sell_button", lang), key=f"sell_{alert['district']}", on_click=go_to_sell, args=(alert,),
              type="primary", use_container_width=True)


def add_today_marker(figure, when, lang):
    figure.add_shape(type="line", x0=when, x1=when, y0=0, y1=1, yref="paper", line=dict(color="#607d8b", dash="dot"))
    figure.add_annotation(x=when, y=1, yref="paper", text=t("today", lang), showarrow=False, yanchor="bottom",
                          font=dict(color="#455a64"))


def supply_chart(history, when, lang, crop_label):
    ratio = history["arrival_tonnes"] / history["arrival_baseline"]
    groups = [
        ("bar_normal", GREEN, ratio < 1.2),
        ("bar_high", AMBER, (ratio >= 1.2) & (ratio < config.SPIKE_RATIO)),
        ("bar_rush", RED, ratio >= config.SPIKE_RATIO),
    ]
    figure = go.Figure()
    for label, color, mask in groups:
        mask = mask.fillna(False)
        figure.add_bar(x=history.loc[mask, "date"], y=history.loc[mask, "arrival_tonnes"], name=t(label, lang),
                       marker=dict(color=color, cornerradius=3), width=86400000 * 0.75,
                       hovertemplate="%{x|%d %b}: %{y:,.0f} t<extra></extra>")
    figure.add_scatter(x=history["date"], y=history["arrival_baseline"], name=t("normal_amount", lang), mode="lines",
                       line=dict(color="#37474f", dash="dash", width=2), hovertemplate="%{y:,.0f} t<extra></extra>")
    figure.update_layout(barmode="overlay")
    figure.update_yaxes(title=t("axis_tonnes", lang), gridcolor="#eef5ec", rangemode="tozero")
    figure.update_xaxes(showgrid=False, tickformat="%d %b")
    add_today_marker(figure, when, lang)
    return style_figure(figure, height=380, title=t("chart_supply_title", lang, crop=crop_label))


def price_chart(history, alert, when, lang, crop_label):
    figure = go.Figure()
    figure.add_scatter(x=history["date"], y=history["price_baseline"] / 100, name=t("normal_price", lang), mode="lines",
                       line=dict(color="#90a4ae", dash="dash", width=2), hovertemplate="₹%{y:.1f}/kg<extra></extra>")
    figure.add_scatter(x=history["date"], y=history["modal_price"] / 100, name=t("price_line", lang), mode="lines",
                       line=dict(color=GREEN, width=3, shape="spline", smoothing=0.6), fill="tozeroy",
                       fillcolor="rgba(46,125,50,0.08)", hovertemplate="%{x|%d %b}: ₹%{y:.1f}/kg<extra></extra>")
    if alert and alert["risk_level"] != "NORMAL":
        days = alert["buffer_days_high"] or alert["model_days_to_bottom"]
        end = pd.Timestamp(when) + pd.Timedelta(days=days)
        figure.add_scatter(x=[pd.Timestamp(when), end], y=[alert["modal_price"] / 100, alert["projected_bottom_price"] / 100],
                           name=t("possible_price", lang), mode="lines+markers",
                           line=dict(color=RED, dash="dot", width=3), marker=dict(size=[8, 13], symbol="triangle-down"),
                           hovertemplate="₹%{y:.1f}/kg<extra></extra>")
        figure.update_xaxes(range=[history["date"].min(), end + pd.Timedelta(days=2)])
    figure.update_yaxes(title=t("axis_rupees_kg", lang), gridcolor="#eef5ec", rangemode="tozero")
    figure.update_xaxes(showgrid=False, tickformat="%d %b")
    add_today_marker(figure, when, lang)
    return style_figure(figure, height=380, title=t("chart_price_title", lang, crop=crop_label))


def initials(name):
    parts = [p for p in str(name).replace("'", "").split() if p[:1].isalnum()]
    return "".join(p[0] for p in parts[:2]).upper() or "B"


def booking_key(listing, buyer):
    return f"{listing['listing_id']}::{buyer['buyer_id']}"


def plain(record):
    return {key: (None if isinstance(value, float) and np.isnan(value) else value) for key, value in dict(record).items()}


def request_booking(listing, buyer):
    st.session_state["booking_request"] = (listing, buyer)


def confirm_booking(listing, buyer, pickup_text):
    record = marketplace.create_booking(listing, buyer, pickup_text, confirmed_by_user=True)
    st.session_state.setdefault("bookings", {})[booking_key(listing, buyer)] = record
    st.session_state["booking_confirmed_open"] = (listing, buyer)


def rupees(value):
    return f"{float(value):,.0f}"


def buyer_card(buyer, lang, show_match=True, listing=None):
    registered = buyer["listing_status"] == "registered"
    status = t("status_registered" if registered else "status_public", lang)
    verified = marketplace.is_verified(buyer)
    trust = marketplace.sample_trust(buyer)
    booking = st.session_state.get("bookings", {}).get(booking_key(listing, buyer)) if listing is not None else None
    details = []
    if show_match and pd.notna(buyer.get("distance_km")):
        details.append(t("distance", lang, km=f"{buyer['distance_km']:.0f}"))
    if pd.notna(buyer.get("can_absorb_qtl")):
        details.append(t("can_take", lang, qty=f"{buyer['can_absorb_qtl']:,.0f}"))
    if pd.notna(buyer.get("max_price_per_qtl")):
        details.append(t("pays_up_to", lang, price=money(kg(buyer["max_price_per_qtl"]))))
    if booking:
        contacts = [str(v) for v in (buyer.get("contact_phone"), buyer.get("contact_email")) if pd.notna(v) and str(v).strip()]
        contact = " | ".join(contacts) if contacts else t("buyer_no_phone", lang)
    else:
        contact = t("phone_hidden", lang)
    source = ""
    if pd.notna(buyer.get("source_url")) and str(buyer.get("source_url")).strip():
        source = f" <a href='{esc(buyer['source_url'])}' target='_blank'>{esc(t('source', lang))}</a>"
    address = f"<div class='sr-small'>{esc(buyer['address'])}</div>" if pd.notna(buyer.get("address")) and str(buyer.get("address")).strip() else ""
    match = ""
    if show_match and pd.notna(buyer.get("match_score")):
        score = float(buyer["match_score"])
        match = (f"<div class='sr-bar'><div style='width:{min(score, 100):.0f}%'></div></div>"
                 f"<div class='sr-small'>{esc(t('match', lang))}: {score:.0f}/100</div>")
    if trust:
        trust_text = f"{t('trust_line', lang, rating=trust['rating'], deals=trust['deals'], disputes=trust['disputes'])} {t('trust_sample', lang)}"
    else:
        trust_text = t("trust_none", lang)
    badges = f"<span class='sr-status' style='background:{GREEN if registered else AMBER}'>{esc(status)}</span>"
    if verified:
        badges = f"<span class='sr-verified'>{esc(t('verified', lang))}</span> " + badges
    if booking:
        badges += f" <span class='sr-status' style='background:#123d1a'>{esc(t('booked_badge', lang))}</span>"
    st.markdown(
        f"""
        <div class='sr-buyer'>
          <div class='sr-buyer-head'>
            <div class='sr-avatar'>{esc(initials(buyer['business_name']))}</div>
            <div><b class='name'>{esc(buyer['business_name'])}</b><br>
              <span class='sr-small'>{esc(option(buyer['business_type'], lang))} | {esc(district_name(buyer['district'], lang))}</span></div>
          </div>
          <div style='margin-top:8px'>{badges}</div>
          <div class='sr-trust'>{esc(trust_text)}</div>
          {address}
          {match}
          <div class='sr-small'>{esc(' | '.join(details))}</div>
          <div class='sr-contact'>{esc(contact)}{source}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if listing is not None:
        st.button(t("booked_badge" if booking else "book_button", lang), key=f"book_{booking_key(listing, buyer)}",
                  on_click=request_booking, args=(plain(listing), plain(buyer)), disabled=bool(booking),
                  type="primary", use_container_width=True)


@st.dialog("SurplusRoute", width="large")
def booking_dialog(listing, buyer, lang):
    key = booking_key(listing, buyer)
    st.session_state.pop("booking_confirmed_open", None)
    bookings = st.session_state.setdefault("bookings", {})
    booking = bookings.get(key)
    totals = marketplace.deal_totals(listing["quantity_qtl"], listing["asking_price_per_qtl"])
    quantity = float(listing["quantity_qtl"])
    st.markdown(f"<div class='sr-section' style='margin-top:0'>{esc(t('slip_title', lang))}</div>", unsafe_allow_html=True)
    if booking:
        pickup_text = booking["pickup_at"]
    else:
        left, right = st.columns(2)
        pickup_day = left.date_input(t("pickup_date", lang), value=date.today() + timedelta(days=1), key=f"pd_{key}")
        pickup_clock = right.time_input(t("slip_pickup", lang), value=datetime_time(7, 0), key=f"pt_{key}")
        pickup_text = f"{pickup_day.strftime('%d %b %Y')} {pickup_clock.strftime('%H:%M')}"
    grade = listing.get("grade") or "-"
    rows = [
        (t("slip_buyer", lang), buyer["business_name"]),
        (t("slip_crop", lang), option(listing["crop"], lang)),
        (t("slip_quantity", lang), t("slip_quantity_value", lang, qty=f"{quantity:,.1f}", kg=f"{quantity * 100:,.0f}")),
        (t("slip_grade", lang), option(grade, lang)),
        (t("slip_price", lang), t("per_kg", lang, value=money(float(listing["asking_price_per_qtl"]) / 100))),
        (t("slip_total", lang), f"₹{rupees(totals['total'])}"),
        (t("slip_pickup", lang), pickup_text),
    ]
    table = "".join(f"<tr><td>{esc(k)}</td><td><b>{esc(v)}</b></td></tr>" for k, v in rows)
    st.markdown(
        f"""
        <table class='sr-slip'>{table}</table>
        <div class='sr-fee'>{esc(t('fee_line', lang, fee=rupees(totals['fee'])))}</div>
        <div class='sr-receive'>{esc(t('you_receive', lang, amount=rupees(totals['seller_receives'])))}</div>
        <div class='sr-escrow'>{esc(t('escrow_note', lang))}</div>
        """,
        unsafe_allow_html=True,
    )
    if booking:
        st.success(t("booking_confirmed", lang))
        phone = buyer.get("contact_phone")
        if phone and str(phone).strip():
            st.markdown(f"<div class='sr-phone'>{esc(t('buyer_phone', lang, phone=phone))}</div>", unsafe_allow_html=True)
        else:
            st.info(t("buyer_no_phone", lang))
        if st.button(t("close", lang), use_container_width=True, key=f"close_{key}"):
            st.rerun()
    else:
        st.caption(t("booking_by_you", lang))
        st.button(t("confirm_booking", lang), type="primary", use_container_width=True, key=f"confirm_{key}",
                  on_click=confirm_booking, args=(listing, buyer, pickup_text))


def fair_price_kg(agent, district, as_of):
    rows = agent.history[(agent.history["date"] == pd.Timestamp(as_of))
                         & (agent.history["district"].str.lower() == str(district).lower())]
    if rows.empty or pd.isna(rows["modal_price"].iloc[0]):
        return None
    return float(rows["modal_price"].iloc[0]) / 100


def show_matches(agent, listing, lang):
    crop_label = option(listing["crop"], lang)
    st.markdown(f"<div class='sr-section'>{esc(t('matches_title', lang, qty=f'{float(listing['quantity_qtl']):,.0f}', crop=crop_label, district=district_name(listing['district'], lang)))}</div>",
                unsafe_allow_html=True)
    matches = agent.match_surplus(listing)
    if matches.empty:
        st.info(t("no_matches", lang))
        return
    columns = st.columns(2)
    for index, (_, buyer) in enumerate(matches.iterrows()):
        with columns[index % 2]:
            buyer_card(buyer, lang, listing=listing)
    st.caption(t("booking_by_you", lang))
    st.caption(t("demo_note", lang))


with st.sidebar:
    product_icon = image_html("product_icon", "sr-logo-img", "SurplusRoute logo")
    logo_box = f"<div class='sr-logo sr-logo-light'>{product_icon}</div>" if product_icon else "<div class='sr-logo'>SR</div>"
    st.markdown(f"<div class='sr-brand'>{logo_box}<div><b>SurplusRoute</b>"
                "<span>Mandi glut early warning</span></div></div>", unsafe_allow_html=True)
    lang = st.radio("Language / ಭಾಷೆ / भाषा", list(LANGUAGES), format_func=LANGUAGES.get, key="lang", horizontal=True)
    ready_crops = [cs for cs in config.TRACKED if panel_path(*cs).exists() and model_path(*cs).exists()] or config.TRACKED
    commodity, state = st.selectbox(
        t("crop_state", lang), ready_crops, format_func=lambda cs: f"{option(cs[0], lang)}, {option(cs[1], lang)}"
    )

crop_label = option(commodity, lang)

if not panel_path(commodity, state).exists() or not model_path(commodity, state).exists():
    st.warning(t("not_ready", lang))
    st.stop()

model_stamp = stamp(commodity, state)
with st.spinner("SurplusRoute..."):
    agent = load_agent(commodity, state, model_stamp)
dates = [pd.Timestamp(d).date() for d in agent.available_dates(honest_only=True)]
if st.session_state.get("as_of") not in dates:
    st.session_state["as_of"] = dates[-1]

with st.sidebar:
    as_of = st.select_slider(t("date", lang), options=dates, key="as_of", format_func=lambda d: d.strftime("%d %b %Y"))
    st.markdown(f"<div class='sr-side-note'>{esc(t('data_source', lang))}</div>", unsafe_allow_html=True)

hero(crop_label, option(state, lang), as_of, lang)

labels = [t(f"nav_{p}", lang) for p in PAGES]
forced = st.session_state.pop("force_page", None)
current = forced or st.session_state.get("page", "alerts")
choice = option_menu(
    None, labels, icons=PAGE_ICONS, orientation="horizontal", default_index=PAGES.index(current),
    manual_select=PAGES.index(forced) if forced else None, key=f"nav_{lang}",
    styles={
        "container": {"padding": "6px", "background-color": "#ffffff", "border-radius": "16px",
                      "border": "1px solid #e3efe1", "box-shadow": "0 6px 18px rgba(18,61,26,0.06)"},
        "icon": {"color": "#2e7d32", "font-size": "16px"},
        "nav-link": {"font-size": "15px", "font-weight": "600", "color": "#1b2e1d", "border-radius": "12px",
                     "margin": "0 3px", "--hover-color": "#eef7ec", "font-family": FONT},
        "nav-link-selected": {"background": "linear-gradient(90deg, #1f6b2a, #43a047)", "color": "#ffffff"},
    },
)
page = PAGES[labels.index(choice)] if choice in labels else current
st.session_state["page"] = page

if page == "alerts":
    with st.spinner("SurplusRoute..."):
        report = agent_report(commodity, state, pd.Timestamp(as_of), model_stamp)
    if report["status"] != "ok":
        st.info(t("no_data", lang))
    else:
        alerts = report["alerts"]
        kpi_row(report, lang)
        agent_strip(report, lang)

        left, right = st.columns([3, 2], gap="medium")
        with left:
            st.markdown(f"<div class='sr-section'>{esc(t('map_title', lang))}</div>"
                        f"<div class='sr-sub'>{esc(t('map_help', lang, crop=crop_label))}</div>", unsafe_allow_html=True)
            st.plotly_chart(risk_map(alerts, lang, crop_label), use_container_width=True, config={"displayModeBar": False})
        with right:
            st.markdown(f"<div class='sr-section'>{esc(t('rank_title', lang))}</div>"
                        f"<div class='sr-sub'>{esc(t('chance', lang))}</div>", unsafe_allow_html=True)
            st.plotly_chart(risk_ranking(alerts, lang), use_container_width=True, config={"displayModeBar": False})

        at_risk = [a for a in alerts if a["risk_level"] != "NORMAL"]
        st.markdown(f"<div class='sr-section'>{esc(t('alerts_title', lang))}</div>", unsafe_allow_html=True)
        if not at_risk:
            st.success(t("no_alerts", lang))
        columns = st.columns(2, gap="medium")
        for index, alert in enumerate(at_risk):
            with columns[index % 2]:
                alert_card(alert, lang, crop_label)

        safe = [a for a in alerts if a["risk_level"] == "NORMAL"]
        if safe:
            st.markdown(f"<div class='sr-section'>{esc(t('safe_markets', lang))}</div>", unsafe_allow_html=True)
            st.dataframe(
                pd.DataFrame({
                    t("district", lang): [district_name(a["district"], lang) for a in safe],
                    t("price_today", lang): [t("per_kg", lang, value=money(kg(a["modal_price"]))) for a in safe],
                    t("chance", lang): [a["crash_probability"] * 100 for a in safe],
                    t("markets", lang): [", ".join(a["mandis"][:3]) for a in safe],
                }),
                hide_index=True, use_container_width=True,
                column_config={t("chance", lang): st.column_config.ProgressColumn(t("chance", lang), format="%.0f%%",
                                                                                   min_value=0, max_value=100)},
            )

        st.markdown(f"<div class='sr-section'>{esc(t('deep_dive', lang))}</div>", unsafe_allow_html=True)
        chosen = st.selectbox(t("chart_pick", lang), [a["district"] for a in alerts],
                              format_func=lambda d: district_name(d, lang), label_visibility="collapsed")
        chosen_alert = next(a for a in alerts if a["district"] == chosen)
        history = agent.district_history(chosen, as_of)
        chart_left, chart_right = st.columns(2, gap="medium")
        with chart_left:
            st.plotly_chart(supply_chart(history, pd.Timestamp(as_of), lang, crop_label), use_container_width=True,
                            config={"displayModeBar": False})
        with chart_right:
            st.plotly_chart(price_chart(history, chosen_alert, pd.Timestamp(as_of), lang, crop_label),
                            use_container_width=True, config={"displayModeBar": False})
        st.caption(t("chart_help", lang, crop=crop_label))

elif page == "sell":
    prefill = st.session_state.get("prefill")
    st.markdown(f"<div class='sr-section'>{esc(t('sell_title', lang))}</div>", unsafe_allow_html=True)
    form_col, info_col = st.columns([3, 2], gap="large")
    with info_col:
        if prefill:
            color = LEVEL_COLORS[prefill["risk_level"]]
            st.markdown(
                f"""
                <div class='sr-card' style='border-top-color:{color}'>
                  <div class='sr-card-head'>
                    <div><small class='sr-small'>{esc(t('from_alert', lang))}</small>
                    <h3>{esc(district_name(prefill['district'], lang))}</h3>
                    <span class='sr-pill' style='background:{color}'>{esc(t(f"level_{prefill['risk_level']}", lang))}</span></div>
                    <div class='sr-gauge' style='background:conic-gradient({color} {round(prefill['crash_probability'] * 100)}%, #edf3ec 0)'><div>
                      <b>{round(prefill['crash_probability'] * 100)}%</b><span>{esc(t('tag_prediction', lang))}</span></div></div>
                  </div>
                  <div class='sr-reason'>{esc(reason_text(prefill, lang, crop_label))}</div>
                  <div class='sr-prices'>
                    <div class='col'><small>{esc(t('price_today', lang))}</small><b>{esc(t('per_kg', lang, value=money(kg(prefill['modal_price']))))}</b></div>
                    <div class='arrow' style='color:{color}'>&rarr;</div>
                    <div class='col'><small>{esc(t('may_fall_to', lang))}</small><b>{esc(t('per_kg', lang, value=money(kg(prefill['projected_bottom_price']))))}</b></div>
                  </div>
                  <div class='sr-todo'><b>{esc(t('what_to_do', lang))}:</b> {esc(t(f"action_{prefill['action_code']}", lang))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info(t("sell_tip", lang))
    with form_col:
        districts = known_districts()
        default_district = prefill["district"] if prefill and prefill["district"] in districts else districts[0]
        district = st.selectbox(t("stock_district", lang), districts, index=districts.index(default_district),
                                format_func=lambda d: district_name(d, lang), key="sell_district")
        hint = fair_price_kg(agent, district, as_of)
        if hint is not None:
            st.markdown(f"<div class='sr-hint'><b>{esc(t('fair_price', lang, district=district_name(district, lang), price=money(hint)))}</b>"
                        f"<span>{esc(t('fair_price_note', lang, date=as_of.strftime('%d %b %Y')))}</span></div>",
                        unsafe_allow_html=True)
        with st.form("listing_form"):
            left, right = st.columns(2)
            seller_name = left.text_input(t("seller_name", lang))
            seller_type = right.selectbox(t("seller_type", lang), config.SELLER_TYPES, format_func=lambda v: option(v, lang))
            phone = left.text_input(t("phone", lang))
            email = right.text_input(t("email", lang))
            quantity = left.number_input(t("quantity", lang), min_value=0.0, step=5.0)
            grade = right.selectbox(t("grade", lang), config.GRADES, format_func=lambda v: option(v, lang))
            default_price = round(hint if hint is not None else (float(prefill["modal_price"]) / 100 if prefill else 0.0), 1)
            asking_kg = left.number_input(t("asking_price", lang), min_value=0.0, value=default_price, step=0.5)
            available_until = right.date_input(t("available_until", lang), value=date.today() + timedelta(days=3))
            photo = st.file_uploader(t("photo", lang), type=["jpg", "jpeg", "png", "webp"])
            submitted = st.form_submit_button(t("submit_listing", lang), type="primary", use_container_width=True)
    if submitted:
        try:
            listing = marketplace.add_listing(
                seller_name, seller_type, phone, email, commodity, state, district, quantity, asking_kg * 100,
                available_until, prefill["risk_level"] if prefill else None,
                prefill["crash_probability"] if prefill else None,
                grade=grade, photo_bytes=photo.getvalue() if photo else None,
            )
            st.session_state["last_listing"] = listing
            st.success(t("listing_saved", lang))
        except ValueError as error:
            st.error(t(str(error), lang))
    last_listing = st.session_state.get("last_listing")
    if last_listing and last_listing["crop"] == commodity:
        if last_listing.get("photo_path"):
            st.caption(t("photo_stamped", lang, time=last_listing["photo_timestamp"]))
            st.image(last_listing["photo_path"], width=280)
        show_matches(agent, last_listing, lang)

elif page == "matches":
    listings = marketplace.load_listings()
    listings = listings[listings["crop"] == commodity] if not listings.empty else listings
    if listings.empty:
        st.info(t("no_listings", lang))
    else:
        listings = listings.iloc[::-1]
        choice_index = st.selectbox(
            t("pick_listing", lang), listings.index,
            format_func=lambda i: f"{listings.at[i, 'seller_name']} | {listings.at[i, 'quantity_qtl']:,.0f} qtl | "
                                  f"{district_name(listings.at[i, 'district'], lang)} | "
                                  f"{t('per_kg', lang, value=money(listings.at[i, 'asking_price_per_qtl'] / 100))}",
        )
        show_matches(agent, listings.loc[choice_index], lang)

elif page == "register":
    st.markdown(f"<div class='sr-section'>{esc(t('nav_register', lang))}</div>"
                f"<div class='sr-sub'>{esc(t('register_intro', lang))}</div>", unsafe_allow_html=True)
    form_col, list_col = st.columns([3, 2], gap="large")
    with form_col:
        with st.form("buyer_form", clear_on_submit=True):
            left, right = st.columns(2)
            business_name = left.text_input(t("business_name", lang))
            business_type = right.selectbox(t("business_type", lang), config.BUYER_TYPES, format_func=lambda v: option(v, lang))
            buyer_district = left.selectbox(t("district", lang), known_districts(), format_func=lambda d: district_name(d, lang))
            crops = right.multiselect(t("crops_interest", lang), list(config.COMMODITY_IDS), format_func=lambda v: option(v, lang))
            capacity = left.number_input(t("capacity", lang), min_value=0.0, step=5.0)
            max_price_kg = right.number_input(t("max_price", lang), min_value=0.0, step=0.5)
            radius = left.number_input(t("radius", lang), min_value=0.0, value=float(config.DEFAULT_MATCH_RADIUS_KM), step=10.0)
            contact_name = right.text_input(t("contact_name", lang))
            buyer_phone = left.text_input(t("phone", lang))
            buyer_email = right.text_input(t("email", lang))
            business_id = st.text_input(t("business_id", lang), placeholder="UDYAM-KR-03-0012345", help=t("business_id_help", lang))
            registered = st.form_submit_button(t("register_button", lang), type="primary", use_container_width=True)
        if registered:
            try:
                buyer = marketplace.add_buyer(business_name, business_type, state, buyer_district, crops, capacity,
                                              max_price_kg * 100, radius, contact_name, buyer_phone, buyer_email, business_id)
                st.success(t("registered_ok", lang, name=buyer["business_name"]))
            except ValueError as error:
                st.error(t(str(error), lang))
    with list_col:
        st.markdown(f"<div class='sr-section' style='margin-top:0'>{esc(t('buyer_list', lang))}</div>", unsafe_allow_html=True)
        for _, buyer in marketplace.load_buyers().iterrows():
            buyer_card(buyer, lang, show_match=False)
        st.caption(t("public_note", lang, date=PUBLIC_BUYERS_CHECKED_ON))
        st.caption(t("demo_note", lang))

else:
    st.markdown(f"<div class='sr-section'>{esc(t('how_title', lang))}</div>", unsafe_allow_html=True)
    resources = [("res_track", "res_track_desc"), ("res_ai", "res_ai_desc"), ("res_agent", "res_agent_desc"),
                 ("res_segment", "res_segment_desc")]
    columns = st.columns(4, gap="medium")
    for index, (column, (title_key, desc_key)) in enumerate(zip(columns, resources), start=1):
        column.markdown(f"<div class='sr-res'><span class='num'>{index}</span><h4>{esc(t(title_key, lang))}</h4>"
                        f"<p>{esc(t(desc_key, lang))}</p></div>", unsafe_allow_html=True)

    how_report = agent_report(commodity, state, pd.Timestamp(as_of), model_stamp)
    if how_report["status"] == "ok":
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        agent_strip(how_report, lang)

    backtest = read_json(config.OUTPUT_DIR / f"backtest_summary_{commodity}_{state.replace(' ', '_')}.json")
    if backtest:
        st.markdown(f"<div class='sr-section'>{esc(t('proof_title', lang))}</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class='sr-proof'>
              <div><b>{backtest['episodes_caught']} / {backtest['crash_episodes']}</b><span>{esc(t('proof_caught', lang))}</span></div>
              <div><b>{backtest['median_lead_days_before_15pct_fall']:.0f}</b><span>{esc(t('proof_days', lang))}</span></div>
              <div><b>{backtest['false_alarm_rate']:.0%}</b><span>{esc(t('proof_false', lang))}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(t("proof_note", lang))

booking_request = st.session_state.pop("booking_request", None) or st.session_state.pop("booking_confirmed_open", None)
if booking_request:
    booking_dialog(booking_request[0], booking_request[1], lang)

st.markdown(f"<div class='sr-footer'>{team_logo_html()}<b>Created by Team Ghee Podi Dosa</b>"
            f"<span>{esc(t('data_source', lang))}</span></div>", unsafe_allow_html=True)
