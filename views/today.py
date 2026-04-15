"""Today's Activity Dashboard page."""
import streamlit as st
import plotly.express as px
from datetime import date
from api_client import get_daily_activity, build_rep_summary, format_duration, load_user_map


def render_today(teams: tuple[str, ...]):
    st.header("Today's Activity")
    st.caption(date.today().strftime("%A, %B %d, %Y"))

    if not teams:
        st.warning("No teams configured. Update team_config.json.")
        return

    user_map = load_user_map()

    with st.spinner("Loading today's call data..."):
        df = get_daily_activity(teams, date.today())

    if df.empty:
        st.info("No call activity recorded today yet.")
        return

    summary = build_rep_summary(df, user_map)

    total_calls = summary["_total_calls"].sum()
    total_talk = summary["_talk_time_secs"].sum()
    total_answered = summary["Answered"].sum()
    conn_rate = (total_answered / total_calls * 100) if total_calls > 0 else 0
    avg_dur = total_talk / total_answered if total_answered > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Calls", f"{int(total_calls):,}")
    k2.metric("Total Talk Time", format_duration(total_talk))
    k3.metric("Avg Call Duration", format_duration(avg_dur))
    k4.metric("Connection Rate", f"{conn_rate:.1f}%")

    st.divider()

    st.subheader("Recruiter Breakdown")
    display_cols = ["Recruiter", "Outbound", "Inbound", "Answered", "Missed",
                    "Total Talk Time", "Avg Duration", "Connection Rate"]
    st.dataframe(summary[display_cols], use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Calls by Recruiter")
    chart_data = summary[["Recruiter", "Outbound", "Inbound"]].melt(
        id_vars="Recruiter", var_name="Direction", value_name="Calls"
    )
    fig = px.bar(
        chart_data, x="Recruiter", y="Calls", color="Direction",
        barmode="stack",
        color_discrete_map={"Outbound": "#636EFA", "Inbound": "#00CC96"},
    )
    fig.update_layout(xaxis_tickangle=-30, height=400)
    st.plotly_chart(fig, use_container_width=True)
