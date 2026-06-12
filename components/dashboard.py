import streamlit as st
import plotly.graph_objects as go

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
            width=0.35
        )
    )

    fig.update_layout(
        title="Boardroom Score Comparison",
        yaxis=dict(
            range=[0, 100],
            title="Score"
        ),
        xaxis_title="Departments",
        height=400,
        showlegend=False,
        bargap = 0.6
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

    st.subheader("📊 Executive Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "💰 Investor",
            f"{int(investor_score)}/100"
        )

    with col2:
        st.metric(
            "⚙️ CTO",
            f"{int(cto_score)}/100"
        )

    with col3:
        st.metric(
            "📈 Marketing",
            f"{int(marketing_score)}/100"
        )

    with col4:
        st.metric(
            "🎯 Product",
            f"{int(product_score)}/100"
        )

    display_executive_bar_chart(
        investor_score,
        cto_score,
        marketing_score,
        product_score
    )