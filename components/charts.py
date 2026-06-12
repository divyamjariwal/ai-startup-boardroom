import plotly.graph_objects as go
import streamlit as st


def display_radar_chart(title, scores):

    categories = list(scores.keys())
    values = list(scores.values())

    values += values[:1]
    categories += categories[:1]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            name=title
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10]
            )
        ),
        showlegend=False,
        title=title
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )