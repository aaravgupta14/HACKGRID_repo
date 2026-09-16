import html
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from surplusroute import config, marketplace
from surplusroute.agent import SurplusRouteAgent
from surplusroute.geo import known_districts
from surplusroute.i18n import LANGUAGES, district_name, option, t
from surplusroute.model import model_path
from surplusroute.prepare import panel_path
from surplusroute.public_buyers import PUBLIC_BUYERS_CHECKED_ON

st.set_page_config(page_title="SurplusRoute", layout="wide")

GREEN, AMBER, RED = "#2e7d32", "#ef8f00", "#c62828"
LEVEL_COLORS = {"HIGH": RED, "WATCH": AMBER, "NORMAL": GREEN}
EXAMPLE_DATE = date(2023, 7, 27)
PAGES = ["alerts", "sell", "matches", "register"]

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem;}
    .sr-header {background: linear-gradient(90deg, #1b5e20, #43a047); color: #ffffff; padding: 20px 26px;
                border-radius: 14px; margin-bottom: 14px;}
    .sr-header h1 {color: #ffffff; margin: 0; font-size: 2.1rem;}
    .sr-header p {color: #e8f5e9; margin: 4px 0 0 0; font-size: 1.05rem;}
    .sr-count {border-radius: 12px; padding: 14px 18px; color: #ffffff; text-align: center;}
    .sr-count b {font-size: 2rem; display: block;}
    .sr-card {background: #ffffff; border: 1px solid #d7ead7; border-left: 10px solid var(--level);
              border-radius: 12px; padding: 16px 20px; margin: 10px 0 6px 0;}
    .sr-card h3 {margin: 0 0 6px 0; color: #1b3a1f;}
    .sr-badge {background: var(--level); color: #ffffff; border-radius: 20px; padding: 3px 12px;
               font-size: 0.9rem; margin-left: 8px; vertical-align: middle;}
    .sr-reason {font-size: 1.1rem; margin: 6px 0 10px 0;}
    .sr-grid {display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 10px;}
    .sr-stat {background: #eef7ee; border-radius: 10px; padding: 8px 14px; min-width: 150px;}
    .sr-stat span {display: block; font-size: 0.85rem; color: #4a6b4d;}
    .sr-stat b {font-size: 1.25rem; color: #1b3a1f;}
    .sr-todo {background: #fff8e1; border-radius: 10px; padding: 10px 14px; margin: 6px 0;}
    .sr-small {color: #4a6b4d; font-size: 0.9rem;}
    .sr-buyer {background: #ffffff; border: 1px solid #d7ead7; border-radius: 12px; padding: 14px 18px; margin: 8px 0;}
    .sr-tag {border-radius: 20px; padding: 2px 10px; font-size: 0.85rem; color: #ffffff;}
    .sr-footer {text-align: center; color: #2e7d32; font-weight: 700; padding: 18px 0 6px 0;
                border-top: 2px solid #c8e6c9; margin-top: 36px; font-size: 1.05rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def stamp(commodity, state):
    return model_path(commodity, state).stat().st_mtime


@st.cache_resource(show_spinner=False)
def load_agent(commodity, state, model_stamp):
    return SurplusRouteAgent(commodity, state)


@st.cache_data(show_spinner=False)
def agent_report(commodity, state, as_of, model_stamp):
    return load_agent(commodity, state, model_stamp).run(as_of)


def kg(value_per_quintal):
    return None if value_per_quintal is None or pd.isna(value_per_quintal) else value_per_quintal / 100


def money(value):
    return f"{value:,.0f}" if value >= 10 else f"{value:,.1f}"


def go_to_sell(alert):
    st.session_state["prefill"] = alert
    st.session_state["page"] = "sell"


def set_date(value):
    st.session_state["as_of"] = value


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


def alert_card(alert, lang, crop_label):
    level = alert["risk_level"]
    name = html.escape(district_name(alert["district"], lang))
    today_kg = kg(alert["modal_price"])
    bottom_kg = kg(alert["projected_bottom_price"])
    stats = [
        (t("chance", lang), f"{alert['crash_probability']:.0%}"),
        (t("price_today", lang), t("per_kg", lang, value=money(today_kg))),
        (t("may_fall_to", lang), t("per_kg", lang, value=money(bottom_kg))),
        (t("days_left", lang), days_text(alert, lang)),
        (t("arrived_today", lang), t("tonnes", lang, value=f"{alert['arrival_tonnes']:,.0f}")),
    ]
    grid = "".join(f"<div class='sr-stat'><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>" for k, v in stats)
    better = ""
    if alert["reroute_to"]:
        rows = "".join(
            "<li>" + html.escape(t("better_price_row", lang, district=district_name(o["district"], lang),
                                   price=money(kg(o["modal_price"])), gap=money(kg(o["price_gap_per_quintal"])))) + "</li>"
            for o in alert["reroute_to"]
        )
        better = f"<div><b>{html.escape(t('better_price', lang))}</b><ul>{rows}</ul></div>"
    mandis = ""
    if alert["mandis"]:
        mandis = f"<div class='sr-small'>{html.escape(t('markets', lang))}: {html.escape(', '.join(alert['mandis']))}</div>"
    st.markdown(
        f"""
        <div class='sr-card' style='--level:{LEVEL_COLORS[level]}'>
          <h3>{name}<span class='sr-badge'>{html.escape(t(f'level_{level}', lang))}</span></h3>
          <div class='sr-reason'>{html.escape(reason_text(alert, lang, crop_label))}</div>
          <div class='sr-grid'>{grid}</div>
          <div class='sr-todo'><b>{html.escape(t('what_to_do', lang))}:</b> {html.escape(t(f"action_{alert['action_code']}", lang))}</div>
          {better}
          {mandis}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button(t("sell_button", lang), key=f"sell_{alert['district']}", on_click=go_to_sell, args=(alert,), type="primary")


def add_today_marker(figure, when, lang):
    figure.add_shape(type="line", x0=when, x1=when, y0=0, y1=1, yref="paper", line=dict(color="#607d8b", dash="dot"))
    figure.add_annotation(x=when, y=1, yref="paper", text=t("today", lang), showarrow=False, yanchor="bottom",
                          font=dict(color="#455a64"))


def style_chart(figure, title, y_title):
    figure.update_layout(
        title=dict(text=title, font=dict(size=18, color="#1b3a1f")), height=340, plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff", margin=dict(l=10, r=10, t=60, b=10), bargap=0.15,
        legend=dict(orientation="h", y=-0.18, x=0), font=dict(size=14),
    )
    figure.update_yaxes(title=y_title, gridcolor="#e8f5e9", rangemode="tozero")
    figure.update_xaxes(gridcolor="#f1f8f1", tickformat="%d %b")
    return figure


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
                       marker_color=color, width=86400000 * 0.8)
    figure.add_scatter(x=history["date"], y=history["arrival_baseline"], name=t("normal_amount", lang),
                       mode="lines", line=dict(color="#37474f", dash="dash", width=2))
    figure.update_layout(barmode="overlay")
    add_today_marker(figure, when, lang)
    return style_chart(figure, t("chart_supply_title", lang, crop=crop_label), t("axis_tonnes", lang))


def price_chart(history, alert, when, lang, crop_label):
    figure = go.Figure()
    figure.add_scatter(x=history["date"], y=history["price_baseline"] / 100, name=t("normal_price", lang),
                       mode="lines", line=dict(color="#90a4ae", dash="dash", width=2))
    figure.add_scatter(x=history["date"], y=history["modal_price"] / 100, name=t("price_line", lang),
                       mode="lines+markers", line=dict(color=GREEN, width=3), marker=dict(size=5))
    if alert and alert["risk_level"] != "NORMAL":
        days = alert["buffer_days_high"] or alert["model_days_to_bottom"]
        figure.add_scatter(
            x=[pd.Timestamp(when), pd.Timestamp(when) + pd.Timedelta(days=days)],
            y=[alert["modal_price"] / 100, alert["projected_bottom_price"] / 100],
            name=t("possible_price", lang), mode="lines+markers",
            line=dict(color=RED, dash="dot", width=3), marker=dict(size=10, symbol="triangle-down"),
        )
        figure.update_xaxes(range=[history["date"].min(), pd.Timestamp(when) + pd.Timedelta(days=days + 2)])
    add_today_marker(figure, when, lang)
    return style_chart(figure, t("chart_price_title", lang, crop=crop_label), t("axis_rupees_kg", lang))


def show_matches(agent, listing, lang):
    crop_label = option(listing["crop"], lang)
    st.subheader(t("matches_title", lang, qty=f"{float(listing['quantity_qtl']):,.0f}", crop=crop_label,
                   district=district_name(listing["district"], lang)))
    matches = agent.match_surplus(listing)
    if matches.empty:
        st.info(t("no_matches", lang))
        return
    for _, buyer in matches.iterrows():
        registered = buyer["listing_status"] == "registered"
        tag_color = GREEN if registered else AMBER
        tag = t("status_registered" if registered else "status_public", lang)
        details = [t("distance", lang, km=f"{buyer['distance_km']:.0f}")]
        if pd.notna(buyer["can_absorb_qtl"]):
            details.append(t("can_take", lang, qty=f"{buyer['can_absorb_qtl']:,.0f}"))
        if pd.notna(buyer["max_price_per_qtl"]):
            details.append(t("pays_up_to", lang, price=money(kg(buyer["max_price_per_qtl"]))))
        contacts = [str(v) for v in (buyer["contact_phone"], buyer["contact_email"]) if pd.notna(v) and str(v).strip()]
        contact_line = " | ".join(contacts) if contacts else t("no_phone", lang)
        source = ""
        if pd.notna(buyer.get("source_url")) and str(buyer.get("source_url")).strip():
            source = f" | <a href='{html.escape(str(buyer['source_url']))}' target='_blank'>{html.escape(t('source', lang))}</a>"
        address = f"<div class='sr-small'>{html.escape(str(buyer['address']))}</div>" if pd.notna(buyer.get("address")) else ""
        st.markdown(
            f"""
            <div class='sr-buyer'>
              <b style='font-size:1.15rem'>{html.escape(str(buyer['business_name']))}</b>
              <span class='sr-tag' style='background:{tag_color}'>{html.escape(tag)}</span>
              <div class='sr-small'>{html.escape(option(buyer['business_type'], lang))} | {html.escape(district_name(buyer['district'], lang))}
                | {html.escape(t('match', lang))}: {buyer['match_score']:.0f}/100</div>
              {address}
              <div>{html.escape(' | '.join(details))}</div>
              <div><b>{html.escape(contact_line)}</b>{source}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.caption(t("contact_note", lang))


with st.sidebar:
    lang = st.radio("Language / ಭಾಷೆ / भाषा", list(LANGUAGES), format_func=LANGUAGES.get, key="lang", horizontal=True)
    commodity, state = st.selectbox(
        t("crop_state", lang), config.TRACKED, format_func=lambda cs: f"{option(cs[0], lang)}, {option(cs[1], lang)}"
    )

crop_label = option(commodity, lang)
st.markdown(f"<div class='sr-header'><h1>SurplusRoute</h1><p>{html.escape(t('tagline', lang))}</p></div>",
            unsafe_allow_html=True)

if not panel_path(commodity, state).exists() or not model_path(commodity, state).exists():
    st.warning(t("not_ready", lang))
    st.stop()

model_stamp = stamp(commodity, state)
with st.spinner("..."):
    agent = load_agent(commodity, state, model_stamp)
dates = [pd.Timestamp(d).date() for d in agent.available_dates(honest_only=True)]
if st.session_state.get("as_of") not in dates:
    st.session_state["as_of"] = dates[-1]

with st.sidebar:
    as_of = st.select_slider(t("date", lang), options=dates, key="as_of", format_func=lambda d: d.strftime("%d %b %Y"))
    left, right = st.columns(2)
    if EXAMPLE_DATE in dates:
        left.button(t("example_button", lang), on_click=set_date, args=(EXAMPLE_DATE,), use_container_width=True)
    right.button(t("latest_button", lang), on_click=set_date, args=(dates[-1],), use_container_width=True)

page = st.radio("page", PAGES, key="page", horizontal=True, label_visibility="collapsed",
                format_func=lambda p: t(f"nav_{p}", lang))

if page == "alerts":
    with st.spinner("..."):
        report = agent_report(commodity, state, pd.Timestamp(as_of), model_stamp)
    if report["status"] != "ok":
        st.info(t("no_data", lang))
    else:
        alerts = report["alerts"]
        counts = st.columns(3)
        for column, level in zip(counts, ["HIGH", "WATCH", "NORMAL"]):
            number = sum(a["risk_level"] == level for a in alerts)
            column.markdown(
                f"<div class='sr-count' style='background:{LEVEL_COLORS[level]}'><b>{number}</b>"
                f"{html.escape(t(f'level_{level}', lang))} ({html.escape(t('markets_count', lang))})</div>",
                unsafe_allow_html=True,
            )
        at_risk = [a for a in alerts if a["risk_level"] != "NORMAL"]
        if not at_risk:
            st.success(t("no_alerts", lang))
        for alert in at_risk:
            alert_card(alert, lang, crop_label)

        safe = [a for a in alerts if a["risk_level"] == "NORMAL"]
        if safe:
            st.markdown(f"#### {t('safe_markets', lang)}")
            st.dataframe(
                pd.DataFrame({
                    t("district", lang): [district_name(a["district"], lang) for a in safe],
                    t("price_today", lang): [t("per_kg", lang, value=money(kg(a["modal_price"]))) for a in safe],
                    t("chance", lang): [f"{a['crash_probability']:.0%}" for a in safe],
                    t("markets", lang): [", ".join(a["mandis"][:3]) for a in safe],
                }),
                hide_index=True, use_container_width=True,
            )

        st.markdown("---")
        chosen = st.selectbox(t("chart_pick", lang), [a["district"] for a in alerts],
                              format_func=lambda d: district_name(d, lang))
        chosen_alert = next(a for a in alerts if a["district"] == chosen)
        history = agent.district_history(chosen, as_of)
        st.plotly_chart(supply_chart(history, pd.Timestamp(as_of), lang, crop_label), use_container_width=True)
        st.caption(t("chart_help", lang, crop=crop_label))
        st.plotly_chart(price_chart(history, chosen_alert, pd.Timestamp(as_of), lang, crop_label), use_container_width=True)

elif page == "sell":
    st.subheader(t("sell_title", lang))
    prefill = st.session_state.get("prefill")
    districts = known_districts()
    default_district = prefill["district"] if prefill and prefill["district"] in districts else districts[0]
    if prefill:
        st.info(f"{t('from_alert', lang)}: {district_name(prefill['district'], lang)} | "
                f"{t(f'level_{prefill['risk_level']}', lang)} | {reason_text(prefill, lang, crop_label)}")
    with st.form("listing_form"):
        left, right = st.columns(2)
        seller_name = left.text_input(t("seller_name", lang))
        seller_type = right.selectbox(t("seller_type", lang), config.SELLER_TYPES, format_func=lambda v: option(v, lang))
        phone = left.text_input(t("phone", lang))
        email = right.text_input(t("email", lang))
        district = left.selectbox(t("stock_district", lang), districts, index=districts.index(default_district),
                                  format_func=lambda d: district_name(d, lang))
        quantity = right.number_input(t("quantity", lang), min_value=0.0, step=5.0)
        default_price = round(float(prefill["modal_price"]) / 100, 1) if prefill else 0.0
        asking_kg = left.number_input(t("asking_price", lang), min_value=0.0, value=default_price, step=0.5)
        available_until = right.date_input(t("available_until", lang), value=date.today() + timedelta(days=3))
        submitted = st.form_submit_button(t("submit_listing", lang), type="primary")
    if submitted:
        try:
            listing = marketplace.add_listing(
                seller_name, seller_type, phone, email, commodity, state, district, quantity, asking_kg * 100,
                available_until, prefill["risk_level"] if prefill else None,
                prefill["crash_probability"] if prefill else None,
            )
            st.success(t("listing_saved", lang))
            show_matches(agent, listing, lang)
        except ValueError as error:
            st.error(t(str(error), lang))

elif page == "matches":
    listings = marketplace.load_listings()
    listings = listings[listings["crop"] == commodity] if not listings.empty else listings
    if listings.empty:
        st.info(t("no_listings", lang))
    else:
        listings = listings.iloc[::-1]
        choice = st.selectbox(
            t("pick_listing", lang), listings.index,
            format_func=lambda i: f"{listings.at[i, 'seller_name']} | {listings.at[i, 'quantity_qtl']:,.0f} qtl | "
                                  f"{district_name(listings.at[i, 'district'], lang)} | "
                                  f"{t('per_kg', lang, value=money(listings.at[i, 'asking_price_per_qtl'] / 100))}",
        )
        show_matches(agent, listings.loc[choice], lang)

else:
    st.markdown(t("register_intro", lang))
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
        small = st.checkbox(t("small_confirm", lang))
        registered = st.form_submit_button(t("register_button", lang), type="primary")
    if registered:
        try:
            buyer = marketplace.add_buyer(business_name, business_type, state, buyer_district, crops, capacity,
                                          max_price_kg * 100, radius, contact_name, buyer_phone, buyer_email, small)
            st.success(t("registered_ok", lang, name=buyer["business_name"]))
        except ValueError as error:
            st.error(t(str(error), lang))

    st.markdown(f"#### {t('buyer_list', lang)}")
    buyers = marketplace.load_buyers()
    st.dataframe(
        pd.DataFrame({
            t("col_name", lang): buyers["business_name"],
            t("col_type", lang): [option(v, lang) for v in buyers["business_type"]],
            t("district", lang): [district_name(v, lang) for v in buyers["district"]],
            t("col_crops", lang): [", ".join(option(c, lang) for c in str(v).split(";")) for v in buyers["crops"]],
            t("col_status", lang): [t(f"status_short_{s}", lang) for s in buyers["listing_status"]],
            t("phone", lang): buyers["contact_phone"].fillna(""),
            t("col_address", lang): buyers["address"].fillna(""),
            t("source", lang): buyers["source_url"].fillna(""),
        }),
        hide_index=True, use_container_width=True,
        column_config={t("source", lang): st.column_config.LinkColumn(t("source", lang))},
    )
    st.caption(t("public_note", lang, date=PUBLIC_BUYERS_CHECKED_ON))

st.markdown("<div class='sr-footer'>Created by Team Ghee Podi Dosa</div>", unsafe_allow_html=True)
