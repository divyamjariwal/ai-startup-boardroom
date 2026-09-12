import streamlit as st
from models.claim import VerifiedClaim
from services.verifier import evidence_coverage


def display_agent_card(
    title,
    scores,
    strengths,
    weaknesses,
    recommendation,
    verified_claims: list[VerifiedClaim] | None = None,
):

    st.subheader(title)

    with st.container(border=True):

        cols = st.columns(len(scores))

        for col, (name, value) in zip(cols, scores.items()):
            with col:
                st.metric(
                    name,
                    f"{value}/10"
                )

        col_strengths, col_weaknesses = st.columns(2)

        with col_strengths:
            st.markdown("**Strengths**")
            for item in strengths:
                st.write(f"• {item}")

        with col_weaknesses:
            st.markdown("**Weaknesses**")
            for item in weaknesses:
                st.write(f"• {item}")

        st.markdown("**Recommendation**")
        st.success(recommendation)

        if verified_claims is not None:
            st.caption(f"Evidence Coverage: {evidence_coverage(verified_claims)}% ({len(verified_claims)} factual claims reviewed; not an accuracy score)")
            if verified_claims:
                with st.expander("Inspect verified claims"):
                    for claim in verified_claims:
                        st.write(f"{claim.status.value.replace('_', ' ').title()} · {claim.confidence:.0%} · {claim.text}")
