def calculate_startup_score(analysis):

    market_score = analysis["market_score"]
    revenue_score = analysis["revenue_score"]
    scalability_score = analysis["scalability_score"]
    risk_score = analysis["risk_score"]

    startup_health_score = (
        market_score +
        revenue_score +
        scalability_score +
        (10 - risk_score)
    ) / 4

    return round(startup_health_score * 10, 2)