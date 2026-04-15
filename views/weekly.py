"""Weekly Activity Dashboard page."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta
from api_client import get_weekly_activity, get_hourly_activity, build_rep_summary, format_duration, load_user_map


def _week_bounds(ref_date: date) -> tuple[date, date]:
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def render_weekly(teams: tuple[str, ...]):
    if not teams:
        st.warning("No teams configured. Update team_config.json.")
        return

    user_map = load_user_map()
    today = date.today()

    col_date, col_spacer = st.columns([1, 3])
    with col_date:
        selected_date = st.date_input("Select a date within the week", value=today, max_value=today)

    start_date, end_date = _week_bounds(selected_date)
    if end_date > today:
        end_date = today

    st.caption(f"Week of {start_date.strftime('%B %d')} – {end_date.strftime('%B %d, %Y')}")

    with st.spinner("Loading weekly call data..."):
        df = get_weekly_activity(teams, start_date, end_date)

    if df.empty:
        st.info("No call activity for this week.")
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

    st.subheader("Daily Call Volume")
    if "time_day" in df.columns:
        daily = df.groupby("time_day")["total_count"].sum().reset_index()
        daily.columns = ["Date", "Calls"]
        daily["Date"] = pd.to_datetime(daily["Date"])
        daily = daily.sort_values("Date")
        fig_line = px.line(daily, x="Date", y="Calls", markers=True,
                           color_discrete_sequence=["#36ADEC"])
        fig_line.update_layout(
            height=350,
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font_color="#0D2A39",
        )
        st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    st.subheader("Activity by Hour of Day")
    with st.spinner("Loading hourly data..."):
        hourly_df = get_hourly_activity(teams, start_date, end_date)

    if not hourly_df.empty and "time_hour" in hourly_df.columns:
        hourly_df["time_hour"] = pd.to_datetime(hourly_df["time_hour"])
        hourly_df["hour"] = hourly_df["time_hour"].dt.hour
        hourly_df["day"] = hourly_df["time_hour"].dt.strftime("%a")

        pivot = hourly_df.groupby(["day", "hour"])["total_count"].sum().reset_index()
        pivot_table = pivot.pivot(index="hour", columns="day", values="total_count").fillna(0)

        day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        pivot_table = pivot_table.reindex(columns=[d for d in day_order if d in pivot_table.columns])

        fig_heat = go.Figure(data=go.Heatmap(
            z=pivot_table.values,
            x=pivot_table.columns.tolist(),
            y=[f"{h:02d}:00" for h in pivot_table.index],
            colorscale=[[0, "#F0E5D5"], [0.5, "#36ADEC"], [1, "#0D2A39"]],
        ))
        fig_heat.update_layout(
            height=450,
            yaxis_title="Hour",
            xaxis_title="Day",
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font_color="#0D2A39",
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Hourly data not available for this period.")
