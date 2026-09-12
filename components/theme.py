"""Shared design tokens for the dark-mode Streamlit UI and Plotly charts.

Single source of truth so streamlit_app.py, components/dashboard.py, and
components/charts.py never re-declare a hex value. Values are the dark-mode
steps from a validated palette (contrast + CVD-separation checked against the
#1a1a19 dark surface with the project's dataviz skill) rather than hand-picked.
"""

# ---------------------------------------------------------------------------
# Surfaces & ink
# ---------------------------------------------------------------------------
PAGE_BG = "#0d0d0d"           # app background (page plane)
SURFACE = "#1a1a19"           # card / metric / chart surface
SURFACE_ELEVATED = "#242423"  # slightly raised surface (hero, primary card)

TEXT = "#FFFFFF"              # primary ink
TEXT_SECONDARY = "#C3C2B7"    # secondary ink (captions, helper text)
TEXT_MUTED = "#898781"        # muted ink (axis labels, disabled)

BORDER = "rgba(255, 255, 255, 0.10)"   # hairline ring
GRIDLINE = "#2c2c2a"                    # chart gridlines
BASELINE = "#383835"                    # chart axis/baseline

# ---------------------------------------------------------------------------
# Brand accent (indigo family, stepped for legibility on a near-black surface)
# ---------------------------------------------------------------------------
PRIMARY = "#818CF8"           # bright accent: links, active states, radar line
PRIMARY_STRONG = "#6366F1"    # solid fills: primary button, hero
ACCENT = "#22D3EE"            # secondary accent (sparingly, e.g. hover states)

PRIMARY_TINT = "rgba(129, 140, 248, 0.16)"   # active tab background
PRIMARY_FILL = "rgba(129, 140, 248, 0.22)"   # radar chart fill
PRIMARY_SHADOW = "rgba(99, 102, 241, 0.35)"  # button/hero shadow
CARD_SHADOW = "rgba(0, 0, 0, 0.45)"          # neutral elevation shadow

# ---------------------------------------------------------------------------
# Categorical palette (validated: dark-mode steps, fixed order, do not cycle)
# Used only where 2+ distinct named categories appear side by side, e.g. the
# Investor/CTO/Marketing/Product comparison bar chart.
# ---------------------------------------------------------------------------
CATEGORICAL = [
    "#3987e5",  # slot 1 - blue
    "#d95926",  # slot 2 - orange
    "#199e70",  # slot 3 - aqua
    "#c98500",  # slot 4 - yellow
]
CHART_SERIES = CATEGORICAL  # alias used by the executive bar chart

# ---------------------------------------------------------------------------
# Status palette (fixed meaning - never reused for series identity)
# ---------------------------------------------------------------------------
STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_SERIOUS = "#ec835a"
STATUS_CRITICAL = "#d03b3b"

STATUS_COLORS = {
    "good": STATUS_GOOD,
    "warning": STATUS_WARNING,
    "serious": STATUS_SERIOUS,
    "critical": STATUS_CRITICAL,
}


def badge_html(label: str, status: str) -> str:
    """Return a small inline HTML pill for the given status key.

    ``status`` must be one of ``STATUS_COLORS``. Rendered with
    ``st.markdown(..., unsafe_allow_html=True)`` by the caller. Color never
    carries meaning alone - the label text always states the status in words.
    """

    color = STATUS_COLORS[status]
    return (
        f'<span style="display:inline-block;padding:0.28rem 0.75rem;'
        f'border-radius:999px;font-weight:600;font-size:0.85rem;'
        f'background:{color}26;color:{color};border:1px solid {color}55;">'
        f"{label}</span>"
    )
