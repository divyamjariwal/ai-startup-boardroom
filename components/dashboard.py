import streamlit as st
import plotly.graph_objects as go

from components.theme import CHART_SERIES, GRIDLINE, TEXT, TEXT_SECONDARY

def display_executive_bar_chart(
    investor_score,
    cto_score,
    marketing_score,
    product_score
):

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=["Investor", "CTO", "Marketing", "Product"],
            y=[
                investor_score,
                cto_score,
                marketing_score,
                product_score
            ],
            text=[
                f"{int(investor_score)}",
                f"{int(cto_score)}",
                f"{int(marketing_score)}",
                f"{int(product_score)}"
            ],
            textposition="outside",
            width=0.35,
            marker=dict(
                color=CHART_SERIES,
                line=dict(width=0),
            ),
        )
    )

    fig.update_layout(
        title=dict(text="Boardroom Score Comparison", font=dict(size=16, family="Inter, sans-serif", color=TEXT)),
        yaxis=dict(
            range=[0, 100],
            title="Score",
            gridcolor=GRIDLINE,
        ),
        xaxis=dict(title="Departments", showgrid=False),
        height=400,
        showlegend=False,
        bargap=0.6,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=TEXT_SECONDARY),
        margin=dict(t=48, b=40, l=40, r=20),
    )

    st.plotly_chart(
        fig,
        use_container_width=False
    )

def display_executive_dashboard(
    investor_score,
    cto_score,
    marketing_score,
    product_score
):

    st.subheader("Executive Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        with st.container(border=True):
            st.metric(
                "Investor",
                f"{int(investor_score)}/100"
            )

    with col2:
        with st.container(border=True):
            st.metric(
                "CTO",
                f"{int(cto_score)}/100"
            )

    with col3:
        with st.container(border=True):
            st.metric(
                "Marketing",
                f"{int(marketing_score)}/100"
            )

    with col4:
        with st.container(border=True):
            st.metric(
                "Product",
                f"{int(product_score)}/100"
            )

    display_executive_bar_chart(
        investor_score,
        cto_score,
        marketing_score,
        product_score
    )