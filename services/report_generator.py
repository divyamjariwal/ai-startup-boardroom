def display_investor_report(analysis, startup_health_score):

    print("\n" + "=" * 50)
    print("INVESTOR ANALYSIS")
    print("=" * 50)

    print("\nStartup Health Score:", startup_health_score)

    print(f"\nMarket Score: {analysis['market_score']}/10")
    print(f"Revenue Score: {analysis['revenue_score']}/10")
    print(f"Scalability Score: {analysis['scalability_score']}/10")
    print(f"Risk Score: {analysis['risk_score']}/10")

    print("\nSTRENGTHS")
    print("-" * 20)

    for strength in analysis["strengths"]:
        print(f"• {strength}")

    print("\nWEAKNESSES")
    print("-" * 20)

    for weakness in analysis["weaknesses"]:
        print(f"• {weakness}")

    print("\nRECOMMENDATION")
    print("-" * 20)
    print(analysis["recommendation"])

def display_cto_report(cto_analysis):

    print("\n" + "=" * 50)
    print("CTO ANALYSIS")
    print("=" * 50)

    print(f"\nTechnical Feasibility Score: {cto_analysis['technical_feasibility_score']}/10")
    print(f"Scalability Score: {cto_analysis['scalability_score']}/10")
    print(f"Infrastructure Complexity Score: {cto_analysis['infrastructure_complexity_score']}/10")
    print(f"Security Risk Score: {cto_analysis['security_risk_score']}/10")
    print(f"Development Cost Score: {cto_analysis['development_cost_score']}/10")

    print("\nSTRENGTHS")
    print("-" * 20)

    for strength in cto_analysis["strengths"]:
        print(f"• {strength}")

    print("\nWEAKNESSES")
    print("-" * 20)

    for weakness in cto_analysis["weaknesses"]:
        print(f"• {weakness}")

    print("\nRECOMMENDATION")
    print("-" * 20)
    print(cto_analysis["recommendation"])

def display_marketing_report(marketing_analysis):

    print("\n" + "=" * 50)
    print("MARKETING ANALYSIS")
    print("=" * 50)

    print(f"\nCustomer Acquisition Score: {marketing_analysis['customer_acquisition_score']}/10")
    print(f"Brand Differentiation Score: {marketing_analysis['brand_differentiation_score']}/10")
    print(f"Growth Potential Score: {marketing_analysis['growth_potential_score']}/10")
    print(f"Go-To-Market Score: {marketing_analysis['go_to_market_score']}/10")
    print(f"Retention Score: {marketing_analysis['retention_score']}/10")

    print("\nSTRENGTHS")
    print("-" * 20)

    for strength in marketing_analysis["strengths"]:
        print(f"• {strength}")

    print("\nWEAKNESSES")
    print("-" * 20)

    for weakness in marketing_analysis["weaknesses"]:
        print(f"• {weakness}")

    print("\nRECOMMENDATION")
    print("-" * 20)

    print(marketing_analysis["recommendation"])

def display_product_report(product_analysis):

    print("\n" + "=" * 50)
    print("PRODUCT ANALYSIS")
    print("=" * 50)

    print(f"\nProduct-Market Fit Score: {product_analysis['product_market_fit_score']}/10")
    print(f"User Experience Score: {product_analysis['user_experience_score']}/10")
    print(f"Feature Differentiation Score: {product_analysis['feature_differentiation_score']}/10")
    print(f"Retention Score: {product_analysis['retention_score']}/10")
    print(f"Product Vision Score: {product_analysis['product_vision_score']}/10")

    print("\nSTRENGTHS")
    print("-" * 20)

    for strength in product_analysis["strengths"]:
        print(f"• {strength}")

    print("\nWEAKNESSES")
    print("-" * 20)

    for weakness in product_analysis["weaknesses"]:
        print(f"• {weakness}")

    print("\nRECOMMENDATION")
    print("-" * 20)

    print(product_analysis["recommendation"])

def display_boardroom_report(summary_analysis):

    print("\n" + "=" * 50)
    print("BOARDROOM VERDICT")
    print("=" * 50)

    print("\nAGREEMENTS")
    print("-" * 20)

    for item in summary_analysis["agreements"]:
        print(f"• {item}")

    print("\nDISAGREEMENTS")
    print("-" * 20)

    for item in summary_analysis["disagreements"]:
        print(f"• {item}")

    print("\nOPPORTUNITIES")
    print("-" * 20)

    for item in summary_analysis["opportunities"]:
        print(f"• {item}")

    print("\nRISKS")
    print("-" * 20)

    for item in summary_analysis["risks"]:
        print(f"• {item}")

    print("\nFINAL VERDICT")
    print("-" * 20)

    print(summary_analysis["final_verdict"])