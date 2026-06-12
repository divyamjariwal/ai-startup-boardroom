def calculate_boardroom_score(
    investor,
    cto,
    marketing,
    product
):

    investor_score = (
        investor["market_score"] +
        investor["revenue_score"] +
        investor["scalability_score"] +
        (10 - investor["risk_score"])
    ) / 4


    cto_score = (
        cto["technical_feasibility_score"] +
        cto["scalability_score"] +
        (10 - cto["security_risk_score"]) +
        cto["development_cost_score"]
    ) / 4


    marketing_score = (
        marketing["customer_acquisition_score"] +
        marketing["brand_differentiation_score"] +
        marketing["growth_potential_score"] +
        marketing["retention_score"]
    ) / 4


    product_score = (
        product["product_market_fit_score"] +
        product["user_experience_score"] +
        product["retention_score"] +
        product["product_vision_score"]
    ) / 4


    final_score = (
        investor_score +
        cto_score +
        marketing_score +
        product_score
    ) / 4

    return round(final_score * 10)

# services/scoring.py

def get_investment_decision(score):

    if score >= 85:
        return "🟢 STRONG INVESTMENT"

    elif score >= 70:
        return "🟡 PROCEED WITH CAUTION"

    else:
        return "🔴 HIGH RISK"