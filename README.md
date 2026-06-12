# AI Startup Boardroom

A multi-agent AI system that simulates a startup boardroom and evaluates startup ideas from different executive perspectives.

## Overview

AI Startup Boardroom is a project that explores how multiple AI agents can collaborate to evaluate startup ideas.

When a startup idea is submitted, different AI agents analyze it from their own perspective. Each agent focuses on a specific business function and provides feedback, observations, and a score. These individual evaluations are then combined to generate a final boardroom verdict and investment recommendation.

The goal of this project was to understand how multi-agent AI systems can be used for decision-making tasks while gaining hands-on experience with prompt engineering, LLM orchestration, and Streamlit application development.

The current version includes:

* Investor Agent
* CTO Agent
* Marketing Agent
* Product Agent
* Summary Agent

---

## Features

### Investor Agent

Evaluates:

* Market Potential
* Revenue Potential
* Scalability
* Investment Risk

### CTO Agent

Evaluates:

* Technical Feasibility
* Infrastructure Complexity
* Security Risks
* Development Cost

### Marketing Agent

Evaluates:

* Market Demand
* Customer Acquisition Strategy
* Competitive Positioning
* Growth Potential

### Product Agent

Evaluates:

* Product-Market Fit
* User Value Proposition
* Product Differentiation
* Adoption Potential

### Summary Agent

Generates:

* Executive Summary
* Agreements
* Disagreements
* Opportunities
* Risks
* Final Verdict

---

## Dashboard Features

* Multi-Agent Startup Evaluation
* Department-wise Scoring
* Overall Boardroom Score
* Investment Recommendation
* Interactive Visualizations
* Score Comparison Charts
* Downloadable PDF Reports

---

## Tech Stack

* Python
* Streamlit
* Groq API
* Llama 3.3 70B
* Plotly
* Pandas
* ReportLab
* Git
* GitHub

---

## Project Structure

```text
ai-startup-boardroom/

├── agents/
│   ├── investor.py
│   ├── cto.py
│   ├── marketing.py
│   ├── product.py
│   └── summary.py
│
├── components/
│   └── agent_cards.py
│
├── services/
│   ├── scoring.py
│   └── pdf_generator.py
│
├── app.py
├── requirements.txt
└── README.md
```

---

## How It Works

1. The user submits a startup idea.
2. The Investor Agent evaluates business and investment potential.
3. The CTO Agent evaluates technical feasibility.
4. The Marketing Agent analyzes market opportunities.
5. The Product Agent evaluates product viability.
6. Individual scores are generated for each department.
7. The system calculates an overall Boardroom Score.
8. The Summary Agent combines all evaluations into a final verdict.
9. Results are displayed through an interactive dashboard and can be exported as a PDF report.

---

## Future Improvements

* Financial Advisor Agent
* Legal Advisor Agent
* Competitor Analysis Agent
* Startup Valuation Prediction
* Boardroom Debate Mode
* User Authentication
* Cloud Deployment

---

## Contributors

* Divyam Jariwal
* Collaborator Name

---

## Screenshots

Add screenshots of:

* Dashboard Overview
* Agent Evaluation Results
* Score Comparison Charts
* Final Boardroom Verdict

---

## What I Learned

While building this project, I gained hands-on experience with:

* Multi-Agent AI Systems
* Prompt Engineering
* LLM Orchestration
* Streamlit Development
* Data Visualization with Plotly
* PDF Report Generation
* End-to-End AI Application Development

This project was developed as part of my M.Tech journey in Artificial Intelligence and Machine Learning.
