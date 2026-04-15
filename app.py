"""CloudCall Activity Dashboard — Main entry point."""
import json
import base64
import streamlit as st
import bcrypt
from pathlib import Path

st.set_page_config(
    page_title="OakTree Staffing | Call Activity",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

USERS_FILE      = Path(__file__).parent / "users.json"
TEAM_CONFIG_FILE = Path(__file__).parent / "team_config.json"
LOGO_FILE       = Path(__file__).parent / "assets" / "logo.png"

# ---------------------------------------------------------------------------
# Brand colors
# ---------------------------------------------------------------------------
NAVY   = "#0D2A39"
CYAN   = "#36ADEC"
CORAL  = "#FF6F59"
CREAM  = "#F0E5D5"
LTBLUE = "#BEDCFE"
TEAL   = "#004638"

# ---------------------------------------------------------------------------
# Global CSS — sidebar + header styling
# ---------------------------------------------------------------------------
def _inject_css():
    st.markdown(
        f"""
        <style>
        /* ---- Sidebar ---- */
        [data-testid="stSidebar"] {{
            background-color: {NAVY} !important;
        }}
        [data-testid="stSidebar"] * {{
            color: #FFFFFF !important;
        }}
        [data-testid="stSidebar"] .stRadio label {{
            color: #FFFFFF !important;
            font-size: 1rem;
        }}
        [data-testid="stSidebar"] hr {{
            border-color: rgba(255,255,255,0.2) !important;
        }}
        [data-testid="stSidebar"] .stButton > button {{
            background-color: transparent !important;
            color: #FFFFFF !important;
            border: 1px solid rgba(255,255,255,0.4) !important;
            width: 100%;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background-color: rgba(255,255,255,0.1) !important;
        }}
        /* ---- Top header bar ---- */
        .ots-header {{
            background-color: {NAVY};
            padding: 0.6rem 1.5rem;
            margin: -1rem -1rem 1.5rem -1rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        .ots-header h2 {{
            color: #FFFFFF;
            margin: 0;
            font-size: 1.2rem;
            font-weight: 600;
        }}
        /* ---- Metric cards ---- */
        [data-testid="stMetric"] {{
            background-color: {LTBLUE}22;
            border-left: 4px solid {CYAN};
            border-radius: 6px;
            padding: 0.5rem 1rem !important;
        }}
        /* ---- Dataframe header ---- */
        [data-testid="stDataFrame"] th {{
            background-color: {NAVY} !important;
            color: #FFFFFF !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _logo_b64() -> str:
    if LOGO_FILE.exists():
        return base64.b64encode(LOGO_FILE.read_bytes()).decode()
    return ""


def _header_bar(subtitle: str = ""):
    b64 = _logo_b64()
    img_tag = (
        f'<img src="data:image/png;base64,{b64}" style="height:42px;" alt="OakTree Staffing">'
        if b64 else "<span style='color:#FFFFFF;font-weight:700;font-size:1.4rem;'>OakTree Staffing</span>"
    )
    sub = f'<h2>{subtitle}</h2>' if subtitle else ""
    st.markdown(
        f'<div class="ots-header">{img_tag}{sub}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def load_users() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return {"users": {}}


def load_team_config() -> dict:
    if TEAM_CONFIG_FILE.exists():
        return json.loads(TEAM_CONFIG_FILE.read_text())
    return {"managers": [], "admin_teams": []}


def verify_password(stored_hash: str, password: str) -> bool:
    return bcrypt.checkpw(password.encode(), stored_hash.encode())


def get_teams_for_user(username: str, role: str) -> tuple[str, ...]:
    config = load_team_config()
    if role == "admin":
        return tuple(config.get("admin_teams", []))
    for mgr in config["managers"]:
        if mgr["username"] == username:
            return (mgr["cloudcall_team"],)
    return ()


def get_display_name(username: str) -> str:
    config = load_team_config()
    for mgr in config["managers"]:
        if mgr["username"] == username:
            return mgr["display_name"]
    return username.capitalize()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def login_page():
    _inject_css()

    b64 = _logo_b64()
    logo_html = (
        f'<img src="data:image/png;base64,{b64}" style="height:80px;" alt="OakTree Staffing">'
        if b64 else ""
    )
    st.markdown(
        f"""
        <div style="text-align:center; padding:2.5rem 0 1rem;">
            {logo_html}
            <h1 style="color:{NAVY}; margin-top:1rem;">Call Activity Dashboard</h1>
            <p style="color:#666;">Sign in to view your team's call activity</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button(
                "Sign In", use_container_width=True
            )
            if submitted:
                users = load_users()
                user  = users.get("users", {}).get(username)
                if user and verify_password(user["password_hash"], password):
                    st.session_state["authenticated"] = True
                    st.session_state["username"]      = username
                    st.session_state["role"]          = user["role"]
                    st.rerun()
                else:
                    st.error("Invalid username or password")


def main_app():
    _inject_css()

    username     = st.session_state["username"]
    role         = st.session_state["role"]
    display_name = get_display_name(username)
    teams        = get_teams_for_user(username, role)

    with st.sidebar:
        b64 = _logo_b64()
        if b64:
            st.markdown(
                f'<div style="text-align:center;padding:1rem 0 0.5rem;">'
                f'<img src="data:image/png;base64,{b64}" style="width:80%;max-width:160px;" alt="OakTree Staffing">'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown(f"**Welcome, {display_name}**")
        if role == "admin":
            st.caption("Admin — viewing all teams")
        else:
            team_label = teams[0] if teams else "No team"
            st.caption(f"Team: {team_label}")

        st.divider()
        page = st.radio(
            "Dashboard",
            ["Today", "Weekly", "Monthly"],
            label_visibility="collapsed",
        )
        st.divider()

        if st.button("Sign Out"):
            for key in ["authenticated", "username", "role",
                        "cloudcall_access_token", "cloudcall_refresh_token"]:
                st.session_state.pop(key, None)
            st.rerun()

    # Page header bar
    page_labels = {
        "Today":   "Today's Activity",
        "Weekly":  "Weekly Activity",
        "Monthly": "Monthly Activity",
    }
    _header_bar(page_labels.get(page, ""))

    if page == "Today":
        from views.today import render_today
        render_today(teams)
    elif page == "Weekly":
        from views.weekly import render_weekly
        render_weekly(teams)
    elif page == "Monthly":
        from views.monthly import render_monthly
        render_monthly(teams)


def main():
    if st.session_state.get("authenticated"):
        main_app()
    else:
        login_page()


if __name__ == "__main__":
    main()
