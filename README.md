
# ⬡ A.R.I.S. — AI Security Dashboard

**A.R.I.S. (AI Response & Intelligence System)** is a locally hosted cybersecurity dashboard powered by a local LLM via Ollama. It summarizes real-time threat news, analyzes system logs for suspicious activity, and provides an interactive cybersecurity assistant — all running privately on your own machine with no data leaving your system.

Built by Andrew Ruiz as part of an ongoing journey into cybersecurity and Python development.

---

## Features

### Cybersecurity News Summarizer
Pulls the latest articles from live RSS feeds including BleepingComputer, The Hacker News, and the NIST National Vulnerability Database. The local AI model summarizes each article and explains why it matters — great for staying current on the threat landscape.

<img width="1512" height="857" alt="Screenshot 2026-05-27 at 3 32 46 PM" src="https://github.com/user-attachments/assets/eea4a12f-b599-4f26-be13-69eac5e1f255" />


### AI Log Analyzer
Paste in system log entries and A.R.I.S. will analyze them for suspicious activity, flag potential threats like failed login attempts or port scans, rate the severity (LOW / MEDIUM / HIGH), and recommend next steps.

<img width="1512" height="857" alt="Screenshot 2026-05-27 at 3 32 41 PM" src="https://github.com/user-attachments/assets/82a43d1b-d250-483f-b579-6c229fed11b8" />


### Security Chatbot
An interactive chat assistant named A.R.I.S. that answers cybersecurity questions, explains concepts, and helps with security research — running entirely on your local machine.


<img width="1512" height="857" alt="Screenshot 2026-05-27 at 3 30 10 PM" src="https://github.com/user-attachments/assets/78c800a4-79b7-46a3-b1de-7eecd7729171" />
---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python | Core backend language |
| Flask | Local web server and API routing |
| Ollama | Local LLM inference (no cloud, no API keys) |
| feedparser | RSS feed parsing for live news |
| Flask-Limiter | Rate limiting to prevent abuse |
| Flask-CORS | Restricted to localhost only for security |
| HTML / CSS / JS | Frontend dashboard interface |

---

## Security Features

- **Localhost only** — CORS restricted to `127.0.0.1`, not accessible from outside your machine
- **Rate limiting** — API endpoints are rate limited to prevent abuse
- **No external AI calls** — all inference runs locally via Ollama, no data sent to third parties
- **5MB request cap** — prevents oversized payloads

---

## Requirements

- Python 3.8+
- [Ollama](https://ollama.com) installed and running locally
- llama3.1 model pulled via Ollama (`ollama pull llama3.1`)

---

## Installation

```bash
# Clone the repository
git clone https://github.com/andrew714-star/ARIS-Security-Dashboard.git
cd ARIS-Security-Dashboard

# Install dependencies
pip install flask flask-cors flask-limiter feedparser requests

# Make sure Ollama is running
ollama serve

# Start the dashboard
python server.py
```

Then open your browser and go to: `http://localhost:5000`

---

## Usage

1. **News** — Click the News tab to pull and summarize the latest cybersecurity headlines
2. **Log Analyzer** — Paste log entries into the analyzer and let A.R.I.S. flag anything suspicious
3. **Chat** — Ask A.R.I.S. any cybersecurity question directly in the chat interface

---

## About This Project

This project was built to combine Python development with practical cybersecurity concepts. It demonstrates:

- Building and routing a local web server with Flask
- Integrating a locally hosted LLM for private AI inference
- Parsing and processing live threat intelligence feeds
- Implementing security best practices (rate limiting, CORS restrictions, input size limits)
- Applying log analysis concepts relevant to SOC operations

---

## Author

**Andrew Ruiz**
[LinkedIn](https://linkedin.com/in/andrew-ruiz-491320366)
