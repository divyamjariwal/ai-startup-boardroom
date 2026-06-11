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