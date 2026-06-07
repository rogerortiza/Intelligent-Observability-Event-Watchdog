"""Streamlit dashboard — service health monitoring with 5-second auto-refresh."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

load_dotenv()

_API = os.environ.get("API_BASE_URL", "http://localhost:8000") + "/api/v1"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Intelligent Observability & Event Watchdog",
    layout="wide",
    initial_sidebar_state="expanded",
)

st_autorefresh(interval=5000, key="watchdog_refresh")


# ── API helpers ────────────────────────────────────────────────────────────────


def _get(path: str, params: dict[str, Any] | None = None) -> dict | list | None:
    try:
        r = requests.get(f"{_API}{path}", params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _post(path: str, json: dict[str, Any] | None = None) -> dict | None:
    try:
        r = requests.post(f"{_API}{path}", json=json, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"error": str(exc)}


# ── Pre-fetch shared data ─────────────────────────────────────────────────────

_summary: dict = _get("/metrics/summary") or {}
_snaps_raw: dict = _get("/metrics/snapshots", {"hours": 24, "limit": 500}) or {}
_snap_items: list[dict] = _snaps_raw.get("items", [])
_all_services: list[str] = sorted({s["service"] for s in _snap_items})

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Controls")

    selected_services: list[str] = st.multiselect(
        "Filter services",
        options=_all_services,
        default=_all_services,
        key="service_filter",
    )

    st.divider()
    st.subheader("Simulate")

    spike_service: str = st.selectbox(
        "Target service",
        options=_all_services or ["auth-service"],
        key="spike_service",
    )

    if st.button("Seed Normal Traffic", use_container_width=True):
        for svc in (_all_services or ["auth-service"]):
            _post("/simulate/normal-traffic", {"service": svc, "count": 50, "error_rate": 0.05})
        st.success("Normal traffic seeded")

    if st.button("Inject Error Spike", use_container_width=True):
        result = _post(
            "/simulate/error-spike",
            {"service": spike_service, "error_count": 30, "spike_duration_minutes": 5},
        )
        if result and "error" not in result:
            st.success(f"Error spike injected into {spike_service}")
        else:
            st.error("Failed to inject spike — is the API running?")

    if st.button("Run Watchdog Now", use_container_width=True):
        _post("/simulate/run-watchdog")
        st.success("Watchdog cycle triggered")


# ── Header + API gate ─────────────────────────────────────────────────────────

st.title("Intelligent Observability & Event Watchdog")

if not _summary:
    st.error("API is not reachable. Start the server: `uvicorn app.main:app --reload`")
    st.stop()


# ── Panel 1: Metric Cards ─────────────────────────────────────────────────────

health_score = float(_summary.get("health_score", 0))
total_logs = int(_summary.get("total_logs_24h", 0))
error_rate = float(_summary.get("error_rate_24h", 0))
active_alerts = int(_summary.get("active_alerts", 0))

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Health Score", f"{health_score:.1f}%")
    if health_score >= 80:
        st.markdown("<span style='color:#22c55e;font-weight:600'>● Healthy</span>", unsafe_allow_html=True)
    elif health_score >= 60:
        st.markdown("<span style='color:#eab308;font-weight:600'>● Warning</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='color:#ef4444;font-weight:600'>● Critical</span>", unsafe_allow_html=True)

with col2:
    st.metric("Total Logs (24h)", f"{total_logs:,}")

with col3:
    st.metric("Error Rate (24h)", f"{error_rate:.2%}", delta_color="inverse")

with col4:
    st.metric("Active Alerts", active_alerts, delta_color="inverse")

st.divider()


# ── Panel 2: Service Health Table ─────────────────────────────────────────────

st.subheader("Service Health")

if _snap_items:
    df_snaps = pd.DataFrame(_snap_items)
    df_snaps["window_start"] = pd.to_datetime(df_snaps["window_start"])

    latest = (
        df_snaps.sort_values("window_start", ascending=False)
        .groupby("service", as_index=False)
        .first()
    )

    _table_cols = [c for c in ["service", "total_logs", "error_count", "error_rate", "avg_latency_ms", "window_start"] if c in latest.columns]
    df_table = latest[_table_cols].copy()
    df_table["error_rate"] = df_table["error_rate"].astype(float)
    if "avg_latency_ms" in df_table.columns:
        df_table["avg_latency_ms"] = df_table["avg_latency_ms"].apply(
            lambda v: f"{v:.0f}ms" if pd.notna(v) else "—"
        )
    if "window_start" in df_table.columns:
        df_table["window_start"] = df_table["window_start"].dt.strftime("%H:%M:%S")

    styled = df_table.style.bar(subset=["error_rate"], color="#d65f5f", width=80).format(
        {"error_rate": "{:.2%}"}
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.info("No snapshot data yet — seed traffic and run the watchdog.")

st.divider()


# ── Panel 3: Health Trend Chart ────────────────────────────────────────────────

st.subheader("Health Trend (24h)")


def _fetch_ts(metric: str, services: list[str]) -> list[dict]:
    if services and len(services) < len(_all_services):
        pts: list[dict] = []
        for svc in services:
            r = _get("/metrics/timeseries", {"metric": metric, "hours": 24, "service": svc}) or {}
            pts.extend(r.get("points", []))
        return pts
    r = _get("/metrics/timeseries", {"metric": metric, "hours": 24}) or {}
    return r.get("points", [])


_err_points = _fetch_ts("error_count", selected_services)
_vol_points = _fetch_ts("total_logs", selected_services)

if _err_points or _vol_points:
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if _err_points:
        df_err = pd.DataFrame(_err_points)
        df_err["timestamp"] = pd.to_datetime(df_err["timestamp"])
        df_err_agg = df_err.groupby("timestamp")["value"].sum().reset_index()
        fig.add_trace(
            go.Scatter(
                x=df_err_agg["timestamp"],
                y=df_err_agg["value"],
                name="Error Count",
                line={"color": "#ef4444", "width": 2},
                mode="lines+markers",
                marker={"size": 4},
            ),
            secondary_y=False,
        )

    if _vol_points:
        df_vol = pd.DataFrame(_vol_points)
        df_vol["timestamp"] = pd.to_datetime(df_vol["timestamp"])
        df_vol_agg = df_vol.groupby("timestamp")["value"].sum().reset_index()
        fig.add_trace(
            go.Scatter(
                x=df_vol_agg["timestamp"],
                y=df_vol_agg["value"],
                name="Total Logs",
                line={"color": "#3b82f6", "width": 1.5, "dash": "dot"},
                mode="lines",
            ),
            secondary_y=True,
        )

    fig.update_layout(
        height=320,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        legend={"orientation": "h", "y": 1.12},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(title_text="Error Count", secondary_y=False, gridcolor="rgba(128,128,128,0.2)")
    fig.update_yaxes(title_text="Total Logs", secondary_y=True)
    fig.update_xaxes(title_text="Time (UTC)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No timeseries data yet.")

st.divider()


# ── Panel 4: Alert Feed ────────────────────────────────────────────────────────

st.subheader("Alert Feed")

_alerts_raw: dict = _get("/alerts", {"limit": 50}) or {}
_alert_items: list[dict] = _alerts_raw.get("items", [])

_SEV_STYLE: dict[str, str] = {
    "CRITICAL": "background-color:#7f1d1d;color:#fca5a5",
    "HIGH":     "background-color:#7c2d12;color:#fdba74",
    "MEDIUM":   "background-color:#713f12;color:#fde68a",
    "LOW":      "background-color:#14532d;color:#86efac",
}


def _alert_row_style(row: pd.Series) -> list[str]:
    status = str(row.get("status", ""))
    if status == "RESOLVED":
        return ["text-decoration:line-through;opacity:0.45"] * len(row)
    if status == "ACKNOWLEDGED":
        return ["opacity:0.60"] * len(row)
    style = _SEV_STYLE.get(str(row.get("severity", "")), "")
    return [style] * len(row)


if _alert_items:
    df_alerts = pd.DataFrame(_alert_items)
    _alert_cols = [
        c for c in
        ["triggered_at", "severity", "alert_type", "service", "title", "status", "zscore"]
        if c in df_alerts.columns
    ]
    df_feed = df_alerts[_alert_cols].copy()
    if "triggered_at" in df_feed.columns:
        df_feed["triggered_at"] = pd.to_datetime(df_feed["triggered_at"]).dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    if "zscore" in df_feed.columns:
        df_feed["zscore"] = df_feed["zscore"].apply(
            lambda v: f"{v:+.2f}" if pd.notna(v) else "—"
        )

    st.dataframe(
        df_feed.style.apply(_alert_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.success("No active alerts — system healthy.")
