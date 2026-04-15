"""CloudCall Report API client with automatic token refresh."""
import os
import json
import requests
import streamlit as st
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from config import (
    REPORT_ENDPOINT, TOKEN_ENDPOINT, CACHE_TTL, ENV_FILE,
    CLOUDCALL_CLIENT_ID,
)

USER_MAP_FILE = Path(__file__).parent / "user_map.json"


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def _load_token_from_env() -> str:
    """Read token from Streamlit secrets (Cloud) or .env file (local)."""
    # Streamlit Cloud: check st.secrets first
    try:
        val = st.secrets.get("CLOUDCALL_API_TOKEN", "")
        if val:
            return val
    except Exception:
        pass
    # Local: read from .env file
    env_path = Path(ENV_FILE)
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("CLOUDCALL_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _load_refresh_token_from_env() -> str:
    """Read refresh token from Streamlit secrets (Cloud) or .env file (local)."""
    try:
        val = st.secrets.get("CLOUDCALL_REFRESH_TOKEN", "")
        if val:
            return val
    except Exception:
        pass
    env_path = Path(ENV_FILE)
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("CLOUDCALL_REFRESH_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _get_token() -> str:
    return st.session_state.get("cloudcall_access_token") or _load_token_from_env()


def _get_refresh_token() -> str:
    return st.session_state.get("cloudcall_refresh_token") or _load_refresh_token_from_env()


def _update_env_file(new_access: str, new_refresh: str):
    """Persist refreshed tokens. On Streamlit Cloud, only session_state is used."""
    env_path = Path(ENV_FILE)
    if not env_path.exists():
        return  # Running on Streamlit Cloud — tokens live in session_state only
    lines = env_path.read_text().splitlines()
    updated = []
    for line in lines:
        if line.startswith("CLOUDCALL_API_TOKEN="):
            updated.append(f"CLOUDCALL_API_TOKEN={new_access}")
        elif line.startswith("CLOUDCALL_REFRESH_TOKEN="):
            updated.append(f"CLOUDCALL_REFRESH_TOKEN={new_refresh}")
        else:
            updated.append(line)
    env_path.write_text("\n".join(updated) + "\n")


def refresh_access_token() -> bool:
    refresh_tok = _get_refresh_token()
    if not refresh_tok:
        st.error("No refresh token configured. Add CLOUDCALL_REFRESH_TOKEN to your .env file.")
        return False
    try:
        resp = requests.post(
            TOKEN_ENDPOINT,
            data={
                "client_id": CLOUDCALL_CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": refresh_tok,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to refresh CloudCall token: {e}")
        return False

    data = resp.json()
    new_access = data.get("access_token", "")
    new_refresh = data.get("refresh_token", refresh_tok)

    if not new_access:
        st.error("Token refresh returned empty access token.")
        return False

    st.session_state["cloudcall_access_token"] = new_access
    st.session_state["cloudcall_refresh_token"] = new_refresh
    _update_env_file(new_access, new_refresh)
    return True


# ---------------------------------------------------------------------------
# User map helpers
# ---------------------------------------------------------------------------

def load_user_map() -> dict[str, str]:
    """Load cloudcall_user_id -> display name mapping."""
    if USER_MAP_FILE.exists():
        data = json.loads(USER_MAP_FILE.read_text())
        return data.get("users", {})
    return {}


def get_display_name(cloudcall_user_id: str, user_map: dict) -> str:
    return user_map.get(cloudcall_user_id, cloudcall_user_id[:8] + "...")


# ---------------------------------------------------------------------------
# Core API fetch
# ---------------------------------------------------------------------------

def _headers():
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
    }


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S-05:00")


def fetch_report(
    report_type: str,
    from_dt: datetime,
    to_dt: datetime,
    dimensions: list[str],
    metrics: list[str],
    team_filter: list[str],
    collect: list[str] | None = None,
    extra_filters: list[dict] | None = None,
    order_by_dim: str | None = None,
    _retried: bool = False,
) -> list[dict]:
    """Fetch report data from CloudCall API.

    API rules (learned from live testing):
    - order_by must use uppercase 'ASC'/'DESC'
    - filter must have at least 1 item
    - pgnum is not a valid field
    - user_name is not a valid dimension or collect field
    - Use cloudcall_user_id as the user dimension
    - Use team_name in filter to scope by team
    """
    if collect is None:
        collect = ["team_name", "number"]
    if extra_filters is None:
        extra_filters = []

    token = _get_token()
    if not token:
        st.error("CloudCall API token not configured. Add CLOUDCALL_API_TOKEN to your .env file.")
        return []

    # Always filter by team — ensures filter has at least 1 item
    filters = [{"dimension": "team_name", "values": team_filter}] + extra_filters

    order_dim = order_by_dim or dimensions[0]
    payload = {
        "type": report_type,
        "from": _fmt_dt(from_dt),
        "to": _fmt_dt(to_dt),
        "dimensions": dimensions,
        "collect": collect,
        "metrics": metrics,
        "order_by": [{"dimension": order_dim, "order": "ASC"}],
        "filter": filters,
    }

    try:
        resp = requests.post(REPORT_ENDPOINT, json=payload, headers=_headers(), timeout=30)

        # Auto-refresh on 401/403
        if resp.status_code in (401, 403) and not _retried:
            if refresh_access_token():
                return fetch_report(
                    report_type, from_dt, to_dt, dimensions, metrics,
                    team_filter, collect, extra_filters, order_by_dim, _retried=True,
                )
            else:
                st.error("Authentication failed and token refresh failed.")
                return []

        resp.raise_for_status()

    except requests.exceptions.HTTPError as e:
        st.error(f"CloudCall API error (HTTP {resp.status_code}): {resp.json().get('Message', str(e))}")
        return []
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to CloudCall API. Check your network.")
        return []
    except requests.exceptions.Timeout:
        st.error("CloudCall API request timed out. Please try again.")
        return []

    return resp.json().get("Data", [])


# ---------------------------------------------------------------------------
# High-level query functions
# ---------------------------------------------------------------------------

@st.cache_data(ttl=CACHE_TTL)
def get_daily_activity(teams: tuple[str, ...], target_date: date) -> pd.DataFrame:
    from_dt = datetime.combine(target_date, datetime.min.time())
    to_dt = datetime.combine(target_date, datetime.max.time().replace(microsecond=0))
    data = fetch_report(
        report_type="call",
        from_dt=from_dt, to_dt=to_dt,
        dimensions=["cloudcall_user_id", "call_direction", "is_missed_call"],
        metrics=["total_count", "total_duration", "avg_duration", "connected_duration", "avg_connected_duration"],
        team_filter=list(teams),
    )
    return _to_df(data)


@st.cache_data(ttl=CACHE_TTL)
def get_weekly_activity(teams: tuple[str, ...], start_date: date, end_date: date) -> pd.DataFrame:
    from_dt = datetime.combine(start_date, datetime.min.time())
    to_dt = datetime.combine(end_date, datetime.max.time().replace(microsecond=0))
    data = fetch_report(
        report_type="call",
        from_dt=from_dt, to_dt=to_dt,
        dimensions=["cloudcall_user_id", "time_day", "call_direction", "is_missed_call"],
        metrics=["total_count", "total_duration", "avg_duration", "connected_duration", "avg_connected_duration"],
        team_filter=list(teams),
        order_by_dim="cloudcall_user_id",
    )
    return _to_df(data)


@st.cache_data(ttl=CACHE_TTL)
def get_hourly_activity(teams: tuple[str, ...], start_date: date, end_date: date) -> pd.DataFrame:
    from_dt = datetime.combine(start_date, datetime.min.time())
    to_dt = datetime.combine(end_date, datetime.max.time().replace(microsecond=0))
    data = fetch_report(
        report_type="call",
        from_dt=from_dt, to_dt=to_dt,
        dimensions=["cloudcall_user_id", "time_hour"],
        metrics=["total_count"],
        team_filter=list(teams),
        collect=["team_name"],
        order_by_dim="cloudcall_user_id",
    )
    return _to_df(data)


@st.cache_data(ttl=CACHE_TTL)
def get_monthly_activity(teams: tuple[str, ...], start_date: date, end_date: date) -> pd.DataFrame:
    from_dt = datetime.combine(start_date, datetime.min.time())
    to_dt = datetime.combine(end_date, datetime.max.time().replace(microsecond=0))
    data = fetch_report(
        report_type="call",
        from_dt=from_dt, to_dt=to_dt,
        dimensions=["cloudcall_user_id", "time_day", "call_direction", "is_missed_call"],
        metrics=["total_count", "total_duration", "avg_duration", "connected_duration", "avg_connected_duration"],
        team_filter=list(teams),
        order_by_dim="cloudcall_user_id",
    )
    return _to_df(data)


def _to_df(data: list[dict]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    numeric_cols = ["total_count", "total_duration", "avg_duration", "connected_duration", "avg_connected_duration"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


# ---------------------------------------------------------------------------
# Formatting / summary helpers
# ---------------------------------------------------------------------------

def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def build_rep_summary(df: pd.DataFrame, user_map: dict | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "Recruiter", "Outbound", "Inbound", "Answered", "Missed",
            "Total Talk Time", "Avg Duration", "Connection Rate",
            "_talk_time_secs", "_total_calls",
        ])
    if user_map is None:
        user_map = load_user_map()

    summary_rows = []
    for uid, group in df.groupby("cloudcall_user_id"):
        total_calls = group["total_count"].sum()
        outbound = group.loc[group.get("call_direction", pd.Series(dtype=str)) == "outbound", "total_count"].sum() if "call_direction" in group.columns else 0
        inbound = group.loc[group.get("call_direction", pd.Series(dtype=str)) == "inbound", "total_count"].sum() if "call_direction" in group.columns else 0
        answered = group.loc[group.get("is_missed_call", pd.Series(dtype=str)) == "0", "total_count"].sum() if "is_missed_call" in group.columns else 0
        missed = group.loc[group.get("is_missed_call", pd.Series(dtype=str)) == "1", "total_count"].sum() if "is_missed_call" in group.columns else 0
        talk_time = group["connected_duration"].sum() if "connected_duration" in group.columns else 0
        avg_dur = group["avg_duration"].mean() if "avg_duration" in group.columns else 0
        conn_rate = (answered / total_calls * 100) if total_calls > 0 else 0

        summary_rows.append({
            "Recruiter": get_display_name(uid, user_map),
            "Outbound": int(outbound),
            "Inbound": int(inbound),
            "Answered": int(answered),
            "Missed": int(missed),
            "Total Talk Time": format_duration(talk_time),
            "Avg Duration": format_duration(avg_dur),
            "Connection Rate": f"{conn_rate:.1f}%",
            "_talk_time_secs": talk_time,
            "_total_calls": int(total_calls),
        })

    return pd.DataFrame(summary_rows)
