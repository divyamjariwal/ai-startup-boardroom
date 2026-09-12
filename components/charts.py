import plotly.graph_objects as go
import streamlit as st

from components.theme import PRIMARY, PRIMARY_FILL, GRIDLINE, TEXT, TEXT_SECONDARY


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
            name=title,
            line=dict(color=PRIMARY, width=2),
            fillcolor=PRIMARY_FILL,
        )
    )

    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                gridcolor=GRIDLINE,
            ),
            angularaxis=dict(gridcolor=GRIDLINE),
        ),
        showlegend=False,
        title=dict(text=title, font=dict(size=15, family="Inter, sans-serif", color=TEXT)),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=TEXT_SECONDARY),
        margin=dict(t=48, b=24, l=32, r=32),
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )