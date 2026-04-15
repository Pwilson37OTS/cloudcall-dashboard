"""CloudCall Activity Dashboard — Main entry point."""
import json
import streamlit as st
import bcrypt
from pathlib import Path

st.set_page_config(
    page_title="CloudCall Activity Dashboard",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

USERS_FILE = Path(__file__).parent / "users.json"
TEAM_CONFIG_FILE = Path(__file__).parent / "team_config.json"


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
    """Return the CloudCall team name(s) this user can see."""
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


def login_page():
    st.markdown(
        """
        <div style="text-align: center; padding: 2rem 0;">
            <h1>📞 CloudCall Activity Dashboard</h1>
            <p style="color: #888;">Sign in to view your team's call activity</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                users = load_users()
                user = users.get("users", {}).get(username)
                if user and verify_password(user["password_hash"], password):
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username
                    st.session_state["role"] = user["role"]
                    st.rerun()
                else:
                    st.error("Invalid username or password")


def main_app():
    username = st.session_state["username"]
    role = st.session_state["role"]
    display_name = get_display_name(username)
    teams = get_teams_for_user(username, role)

    with st.sidebar:
        st.markdown(f"### Welcome, {display_name}")
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
