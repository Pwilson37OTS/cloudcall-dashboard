"""Monthly Activity Dashboard page."""
import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import date
from calendar import monthrange
from api_client import get_monthly_activity, build_rep_summary, format_duration, load_user_map


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last


def render_monthly(teams: tuple[str, ...]):
    if not teams:
        st.warning("No teams configured. Update team_config.json.")
        return

    user_map = load_user_map()
    today = date.today()

    col_m, col_y, col_spacer = st.columns([1, 1, 2])
    with col_m:
        month = st.selectbox("Month", range(1, 13), index=today.month - 1,
                             format_func=lambda m: date(2000, m, 1).strftime("%B"))
    with col_y:
        year = st.selectbox("Year", range(today.year, today.year - 3, -1), index=0)

    start_date, end_date = _month_bounds(year, month)
    if end_date > today:
        end_date = today

    st.caption(f"{date(year, month, 1).strftime('%B %Y')}")

    with st.spinner("Loading monthly call data..."):
        df = get_monthly_activity(teams, start_date, end_date)

    if month == 1:
        prev_start, prev_end = _month_bounds(year - 1, 12)
    else:
        prev_start, prev_end = _month_bounds(year, month - 1)

    with st.spinner("Loading previous month for comparison..."):
        prev_df = get_monthly_activity(teams, prev_start, prev_end)

    if df.empty:
        st.info("No call activity for this month.")
        return

    summary = build_rep_summary(df, user_map)
    prev_summary = build_rep_summary(prev_df, user_map) if not prev_df.empty else None

    total_calls = summary["_total_calls"].sum()
    total_talk = summary["_talk_time_secs"].sum()
    total_answered = summary["Answered"].sum()
    conn_rate = (total_answered / total_calls * 100) if total_calls > 0 else 0
    avg_dur = total_talk / total_answered if total_answered > 0 else 0

    prev_calls = prev_summary["_total_calls"].sum() if prev_summary is not None else 0
    prev_answered = prev_summary["Answered"].sum() if prev_summary is not None else 0
    prev_conn = (prev_answered / prev_calls * 100) if prev_calls > 0 else 0
    calls_delta = int(total_calls - prev_calls) if prev_calls else None
    conn_delta = f"{conn_rate - prev_conn:+.1f}pp" if prev_calls else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Calls", f"{int(total_calls):,}", delta=f"{calls_delta:+,}" if calls_delta is not None else None)
    k2.metric("Total Talk Time", format_duration(total_talk))
    k3.metric("Avg Call Duration", format_duration(avg_dur))
    k4.metric("Connection Rate", f"{conn_rate:.1f}%", delta=conn_delta)

    st.divider()

    st.subheader("Recruiter Rankings")
    summary_sorted = summary.sort_values("_total_calls", ascending=False).reset_index(drop=True)
    summary_sorted.insert(0, "Rank", range(1, len(summary_sorted) + 1))
    display_cols = ["Rank", "Recruiter", "Outbound", "Inbound", "Answered", "Missed",
                    "Total Talk Time", "Avg Duration", "Connection Rate"]
    st.dataframe(summary_sorted[display_cols], use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Daily Call Volume")
    if "time_day" in df.columns:
        daily = df.groupby("time_day")["total_count"].sum().reset_index()
        daily.columns = ["Date", "Calls"]
        daily["Date"] = pd.to_datetime(daily["Date"])
        daily = daily.sort_values("Date")
        fig = px.bar(daily, x="Date", y="Calls", color_discrete_sequence=["#36ADEC"])
        fig.update_layout(
            height=350,
            xaxis_tickformat="%b %d",
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font_color="#0D2A39",
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    if prev_summary is not None and not prev_summary.empty:
        st.subheader("Month-over-Month Comparison")
        current = summary[["Recruiter", "_total_calls"]].rename(columns={"_total_calls": "This Month"})
        previous = prev_summary[["Recruiter", "_total_calls"]].rename(columns={"_total_calls": "Last Month"})
        comparison = current.merge(previous, on="Recruiter", how="outer").fillna(0)
        comparison["Change"] = comparison["This Month"] - comparison["Last Month"]
        comparison["% Change"] = comparison.apply(
            lambda r: f"{(r['Change'] / r['Last Month'] * 100):+.1f}%" if r["Last Month"] > 0 else "N/A",
            axis=1,
        )
        comparison["This Month"] = comparison["This Month"].astype(int)
        comparison["Last Month"] = comparison["Last Month"].astype(int)
        comparison["Change"] = comparison["Change"].astype(int)
        st.dataframe(comparison, use_container_width=True, hide_index=True)
