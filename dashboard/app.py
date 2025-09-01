import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
import plotly.graph_objects as go

st.set_page_config(
    page_title="VoC Dashboard",
    page_icon="🎙️",
    layout="wide"
)

@st.cache_resource
def init_connection():
    load_dotenv()
    return psycopg2.connect(
        host="localhost",
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        port=5432
    )

@st.cache_data(ttl=300) 
def load_data(_conn):
    with _conn.cursor() as cur:
        cur.execute("SELECT * FROM feedback WHERE is_analyzed = TRUE ORDER BY timestamp DESC")
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        df = pd.DataFrame(rows, columns=colnames)
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('America/Los_Angeles')
        df['date'] = df['timestamp'].dt.date
        return df

def create_donut_chart(data, title):
    labels = data.index
    values = data.values
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4,
                                 marker_colors=['#ff4b4b', '#21a5ff', '#f0f2f6'],
                                 textinfo='percent+label')])
    fig.update_layout(
        title_text=title,
        showlegend=False,
        annotations=[dict(text=str(sum(values)), x=0.5, y=0.5, font_size=20, showarrow=False)],
        margin=dict(l=20, r=20, t=40, b=20),
        height=300
    )
    return fig

conn = init_connection()
df = load_data(conn)

st.title("VoC Dashboard")
st.markdown(f"Live feedback analysis from Reddit. *Last updated: {pd.Timestamp.now(tz='America/Los_Angeles').strftime('%Y-%m-%d %I:%M %p')}*")

st.sidebar.header("Filter Data")

min_date = df['date'].min()
max_date = df['date'].max()
selected_date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if len(selected_date_range) == 2:
    df_filtered = df[(df['date'] >= selected_date_range[0]) & (df['date'] <= selected_date_range[1])]
else:
    df_filtered = df.copy()

sentiment_options = ["All"] + sorted(df_filtered['sentiment'].unique().tolist())
selected_sentiment = st.sidebar.selectbox("Filter by Sentiment", sentiment_options)

theme_options = ["All"] + sorted(df_filtered['theme'].unique().tolist())
selected_theme = st.sidebar.selectbox("Filter by Theme", theme_options)

if selected_sentiment != "All":
    df_filtered = df_filtered[df_filtered['sentiment'] == selected_sentiment]
if selected_theme != "All":
    df_filtered = df_filtered[df_filtered['theme'] == selected_theme]


tab1, tab2, tab3 = st.tabs(["Summary", "Insights", "Data Explorer"])

with tab1:
    st.header("High-Level Summary")
    
    total_feedback = len(df_filtered)
    negative_feedback_count = len(df_filtered[df_filtered['sentiment'] == 'negative'])
    avg_severity = df_filtered[df_filtered['sentiment'] == 'negative']['severity'].mean() if negative_feedback_count > 0 else 0
    top_theme = df_filtered['theme'].mode()[0] if not df_filtered.empty else "N/A"

    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    kpi_col1.metric("Total Feedback", f"{total_feedback}")
    kpi_col2.metric("Negative Feedback", f"{negative_feedback_count}")
    kpi_col3.metric("Avg. Severity", f"{avg_severity:.2f}")
    kpi_col4.metric("Top Theme", top_theme)

    st.divider()

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        sentiment_counts = df_filtered['sentiment'].value_counts()
        st.plotly_chart(create_donut_chart(sentiment_counts, "Sentiment Breakdown"), use_container_width=True)
    with chart_col2:
        theme_counts = df_filtered['theme'].value_counts().nlargest(5)
        st.plotly_chart(create_donut_chart(theme_counts, "Top 5 Themes"), use_container_width=True)

    st.subheader("Feedback Trend Over Time")
    trend_data = df_filtered.set_index('timestamp').resample('D').size()
    st.line_chart(trend_data)

with tab2:
    st.header("Actionable Insights")
    
    actionable_df = df_filtered[
        (df_filtered['sentiment'] == 'negative') &
        (df_filtered['severity'] >= 3)
    ].sort_values(by=['severity', 'timestamp'], ascending=[False, False])
    
    if actionable_df.empty:
        st.success("No high-severity negative feedback in the selected range. Great job! ✨")
    else:
        for index, row in actionable_df.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**Theme:** `{row['theme']}`")
                with col2:
                    st.metric("Severity", f"{row['severity']}/4", delta=f"{row['severity']}/4", delta_color="inverse")
                with col3:
                    st.markdown(f"**Date:** {row['timestamp'].strftime('%Y-%m-%d')}")
                
                st.markdown(f"> {row['text_content']}")
                st.markdown(f"[Source Link ]({row['url_to_source']})")

with tab3:
    st.header("Data Explorer")

    if df_filtered.empty: 
        st.warning("No data matches the current filter settings.")
    else:
        st.dataframe(
            df_filtered[['timestamp', 'sentiment', 'theme', 'severity', 'text_content', 'url_to_source']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD h:mm A"),
                "url_to_source": st.column_config.LinkColumn("Source", display_text="🔗 Reddit")
            }
        )