# AI Startup Boardroom

A Multi-Agent AI System that simulates a startup boardroom and evaluates startup ideas from different executive perspectives.

## Overview

AI Startup Boardroom allows users to submit a startup idea and receive evaluations from multiple AI executives.

The system currently includes:

- Investor Agent
- CTO Agent
- Boardroom Summary Agent

Each agent provides a unique perspective and the Summary Agent combines all opinions into a final boardroom verdict.

---

## Architecture

Startup Idea
↓
Investor Agent
↓
CTO Agent
↓
Summary Agent
↓
Final Boardroom Verdict

---

## Features

### Investor Agent

Evaluates:

- Market Potential
- Revenue Potential
- Scalability
- Investment Risk

### CTO Agent

Evaluates:

- Technical Feasibility
- Infrastructure Complexity
- Security Risks
- Development Cost

### Summary Agent

Generates:

- Agreements
- Disagreements
- Opportunities
- Risks
- Final Verdict

---

## Tech Stack

- Python
- Groq API
- Llama 3.3 70B
- Git
- GitHub

---

## Project Structure
ai-startup-boardroom/

├── agents/
├── prompts/
├── services/
├── app.py
├── requirements.txt

---

## Future Roadmap

- Marketing Agent
- Product Manager Agent
- Streamlit Dashboard
- Startup Score Visualization
- Boardroom Debate Mode
- Deployment on Render

---

## Author

Divyam Jariwal
M.Tech AI & ML