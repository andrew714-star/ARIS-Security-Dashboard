# ⬡ A.R.I.S. — AI Security Dashboard

**A.R.I.S. (AI Response & Intelligence System)** is a locally hosted cybersecurity dashboard powered by a local LLM via Ollama. It summarizes real-time threat news, analyzes system logs for suspicious activity, looks up CVE vulnerabilities, and provides an interactive cybersecurity assistant — all running privately on your own machine with no data leaving your system.

Built by Andrew Ruiz as part of an ongoing journey into cybersecurity and Python development.

---

## Features

### System Monitor
A real-time dashboard displaying live system telemetry including CPU usage per core, RAM and swap consumption, disk utilization across all mounted volumes, network interface status and traffic stats, and a live top-processes table sorted by CPU usage. An uptime clock tracks system runtime down to the second. All data is pulled locally via `psutil` — nothing leaves your machine.

<img width="1512" height="860" alt="Screenshot 2026-06-02 at 2 25 05 PM" src="https://github.com/user-attachments/assets/ee00b1b4-535e-47c5-a863-d50de011c273" />

### Cybersecurity News Summarizer
Pulls the latest articles from live RSS feeds including BleepingComputer, The Hacker News, and the NIST National Vulnerability Database. The local AI model summarizes each article and explains why it matters — great for staying current on the threat landscape.

<img width="1512" height="857" alt="Screenshot 2026-05-27 at 3 32 46 PM" src="https://github.com/user-attachments/assets/eea4a12f-b599-4f26-be13-69eac5e1f255" />


### AI Log Analyzer
Paste in system log entries and A.R.I.S. will analyze them for suspicious activity, flag potential threats like failed login attempts or port scans, rate the severity (LOW / MEDIUM / HIGH), and recommend next steps.

<img width="1512" height="857" alt="Screenshot 2026-05-27 at 3 32 41 PM" src="https://github.com/user-attachments/assets/82a43d1b-d250-483f-b579-6c229fed11b8" />


### Phishing Analyzer
Paste in a raw email or headers and A.R.I.S. scans for phishing indicators. Returns a threat score (0–10), a LOW / MEDIUM / HIGH classification, confidence rating, and a recommended action — with inline IOC tags highlighting detected signals like suspicious links, attachments, urgency language, IP addresses, and credential harvesting attempts.

<img width="1512" height="860" alt="Screenshot 2026-06-02 at 2 26 10 PM" src="https://github.com/user-attachments/assets/7e7f1868-60d2-428c-bf8f-9e67518954ae" />


### CVE Lookup
Type any CVE ID (e.g. `CVE-2021-44228`) and A.R.I.S. fetches live data from the NIST National Vulnerability Database, then has the local LLM explain it in plain English. The results include:

- **CVSS score and severity** (CRITICAL / HIGH / MEDIUM / LOW) with a visual bar
- **Published date** pulled directly from NVD
- **Raw NVD description** and up to 10 official references
- **AI plain-English breakdown** covering what the vulnerability is, how it works, who is affected, how to fix it, and an overall risk assessment — streamed in real time

No API key required. The NIST NVD 2.0 API is free for public use.

<img width="1512" height="860" alt="Screenshot 2026-06-02 at 2 32 20 PM" src="https://github.com/user-attachments/assets/6bde6b6e-1ae5-4bd5-ad63-fd8556b6f8fb" />


### Security Chatbot
An interactive chat assistant named A.R.I.S. that answers cybersecurity questions, explains concepts, and helps with security research — running entirely on your local machine.

<img width="1512" height="857" alt="Screenshot 2026-05-27 at 3 30 10 PM" src="https://github.com/user-attachments/assets/78c800a4-79b7-46a3-b1de-7eecd7729171" />

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python | Core backend language |
| Flask | Local web server and API routing |
| Ollama | Local LLM inference (no cloud, no API keys) |
| psutil | Live system telemetry (CPU, RAM, disk, network, processes) |
| feedparser | RSS feed parsing for live news |
| NIST NVD API | Live CVE vulnerability data (free, no key required) |
| Flask-Limiter | Rate limiting to prevent abuse |
| Flask-CORS | Restricted to localhost only for security |
| HTML / CSS / JS | Frontend dashboard interface |

---

## Security Features

- **Localhost only** — CORS restricted to `127.0.0.1`, not accessible from outside your machine
- **Rate limiting** — API endpoints are rate limited to prevent abuse
- **No external AI calls** — all inference runs locally via Ollama, no data sent to third parties
- **5MB request cap** — prevents oversized payloads
- **No CVE API key stored** — NIST NVD is queried directly with no credentials

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

1. **System Monitor** — The default landing page; shows live CPU, RAM, disk, network, and process data
2. **News** — Click the News tab to pull and summarize the latest cybersecurity headlines
3. **Log Analyzer** — Paste log entries into the analyzer and let A.R.I.S. flag anything suspicious
4. **Phishing Analyzer** — Paste a raw email or headers to scan for phishing indicators and get a threat score
5. **CVE Lookup** — Enter any CVE ID to fetch live NVD data and get an AI plain-English explanation
6. **Chat** — Ask A.R.I.S. any cybersecurity question directly in the chat interface

---

## About This Project

This project was built to combine Python development with practical cybersecurity concepts. It demonstrates:

- Building and routing a local web server with Flask
- Integrating a locally hosted LLM for private AI inference
- Parsing and processing live threat intelligence feeds
- Querying public vulnerability databases (NIST NVD) and presenting structured results
- Detecting phishing indicators and scoring email threat levels
- Implementing security best practices (rate limiting, CORS restrictions, input size limits)
- Applying log analysis concepts relevant to SOC operations


---

## Author

**Andrew Ruiz**
[LinkedIn](https://linkedin.com/in/andrew-ruiz-491320366)
