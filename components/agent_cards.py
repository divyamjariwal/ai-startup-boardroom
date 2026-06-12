import streamlit as st


def display_agent_card(
    title,
    icon,
    scores,
    strengths,
    weaknesses,
    recommendation
):

    st.divider()

    st.subheader(f"{icon} {title}")

    cols = st.columns(len(scores))

    for col, (name, value) in zip(cols, scores.items()):
        with col:
            st.metric(
                name,
                f"{value}/10"
            )

    st.markdown("### Strengths")

    for item in strengths:
        st.write(f"✅ {item}")

    st.markdown("### Weaknesses")

    for item in weaknesses:
        st.write(f"⚠️ {item}")

    st.markdown("### Recommendation")

    st.success(recommendation)