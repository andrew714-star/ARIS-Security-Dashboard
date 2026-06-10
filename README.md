# ⬡ A.R.I.S. — AI Security Dashboard

**A.R.I.S. (Adaptive Recon & Intelligence System)** is a locally hosted cybersecurity dashboard powered by a local LLM via Ollama. It summarizes real-time threat news, analyzes system logs, scans for open ports, triages phishing emails, looks up CVEs, generates incident response playbooks, and provides an interactive security assistant — all running privately on your own machine with no data leaving your system.

<img width="1512" height="860" alt="Screenshot 2026-06-10 at 1 37 05 PM" src="https://github.com/user-attachments/assets/aafb3e74-82a0-4775-83ee-5a692b6e751e" />


---

## Features

### ⬡ Central Dashboard
A unified command center that loads system vitals and threat intelligence in parallel. Displays CPU, RAM, and disk usage as live-updating metric cards alongside a real-time news feed threat level indicator (CRITICAL / HIGH / MEDIUM / LOW) derived from RSS headlines. Also shows CPU core gauges, uptime ticker, top processes, disk usage bars, network interface status, and OS info — all auto-refreshing every 60 seconds.

<img width="1450" height="805" alt="Screenshot 2026-06-10 at 1 43 27 PM" src="https://github.com/user-attachments/assets/da1064fc-93b2-4a92-8a13-787eb3a43e80" />

### Cybersecurity News Summarizer
Pulls the latest articles from live RSS feeds including BleepingComputer, The Hacker News, and the NIST National Vulnerability Database. The local AI model summarizes each article and explains why it matters — great for staying current on the threat landscape.

<img width="1512" height="860" alt="Screenshot 2026-06-10 at 1 39 48 PM" src="https://github.com/user-attachments/assets/8662f29b-c22b-410b-b93d-2c0a6dc2a603" />

### AI Log Analyzer
Paste in system log entries and A.R.I.S. will analyze them for suspicious activity, flag potential threats like failed login attempts or port scans, rate the severity (LOW / MEDIUM / HIGH), and recommend next steps.

<img width="1512" height="860" alt="Screenshot 2026-06-10 at 1 37 47 PM" src="https://github.com/user-attachments/assets/7524f96d-266f-4a4d-8576-675070816272" />

### Phishing Email Analyzer
Paste raw email content (including headers) for threat analysis. Features a live header parser that extracts FROM and SUBJECT fields as you type, a dynamic threat score (0–10), IOC tag strip highlighting links, attachments, urgency language, IP addresses, and credential keywords, plus a color-coded threat level bar (LOW / MEDIUM / HIGH).

<img width="1512" height="860" alt="Screenshot 2026-06-10 at 1 39 32 PM" src="https://github.com/user-attachments/assets/ca828ecd-6175-479c-afca-9fbca467057d" />

### CVE Lookup
Look up any CVE by ID against the NIST NVD 2.0 API (no API key required). Displays CVSS score, severity rating, publication date, and references. A.R.I.S. then streams a plain-English AI explanation structured as: What It Is, How It Works, Who Is Affected, How To Fix It, and Risk Rating.

<img width="1512" height="860" alt="Screenshot 2026-06-02 at 2 32 20 PM" src="https://github.com/user-attachments/assets/d29db958-bb79-4680-8e79-5672387f38b0" />


### IR Checklist
Paste any alert, log excerpt, or incident description and A.R.I.S. generates a full NIST SP 800-61 incident response playbook. Output includes: Incident Classification, Severity rating, Immediate Actions (first 15 min), Short-Term Containment (first hour), Investigation Checklist, Escalation guidance, and a Lessons Learned prompt. All checklist items are interactive — click to mark complete. Export the full playbook as a .txt file.

<img width="1512" height="860" alt="Screenshot 2026-06-10 at 1 40 08 PM" src="https://github.com/user-attachments/assets/2386cbae-f68d-4d5d-8d5a-ebc56ca1b979" />

### Port Scanner
A multithreaded TCP port scanner that scans localhost and private LAN ranges only. Supports four scan modes: Quick (22 key ports), Top 100, Full (all 1024 well-known ports), and Attack Surface (21 attacker-targeted ports). Streams open ports to the UI in real time with service names, risk ratings (CRITICAL / HIGH / MEDIUM / LOW), and banner grabbing. Follows with an AI-generated attack surface assessment and hardening recommendations.
<img width="1512" height="860" alt="Screenshot 2026-06-10 at 1 40 20 PM" src="https://github.com/user-attachments/assets/55fa2189-5739-460e-92d7-231fb372d503" />


### Security Chatbot
An interactive chat assistant named A.R.I.S. that answers cybersecurity questions, explains concepts, and helps with security research — running entirely on your local machine.

<img width="1512" height="860" alt="Screenshot 2026-06-10 at 1 38 04 PM" src="https://github.com/user-attachments/assets/39946687-b819-4cdb-8718-b6d967ff81aa" />

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python | Core backend language |
| Flask | Local web server and API routing |
| Ollama | Local LLM inference (no cloud, no API keys) |
| psutil | System metrics (CPU, RAM, disk, network, processes) |
| feedparser | RSS feed parsing for live news |
| requests | HTTP client for NVD API and Ollama |
| Flask-Limiter | Rate limiting to prevent abuse |
| Flask-CORS | Restricted to localhost only for security |
| HTML / CSS / JS | Frontend dashboard interface |

---

## Security Features

- **Localhost only** — CORS restricted to `127.0.0.1`, not accessible from outside your machine
- **Rate limiting** — API endpoints are individually rate limited to prevent abuse
- **No external AI calls** — all inference runs locally via Ollama, no data sent to third parties
- **5MB request cap** — prevents oversized payloads
- **LAN-only port scanning** — scanner restricted to RFC-1918 private ranges and loopback; public IPs are blocked

---

## Requirements

- Python 3.8+
- [Ollama](https://ollama.com) installed and running locally
- `llama3.1` model pulled via Ollama (`ollama pull llama3.1`)

---

## Installation

```bash
# Clone the repository
git clone https://github.com/andrew714-star/ARIS-Security-Dashboard.git
cd ARIS-Security-Dashboard

# Install dependencies
pip install flask flask-cors flask-limiter feedparser requests psutil

# Make sure Ollama is running
ollama serve

# Start the dashboard
python server.py
```

Then open your browser and go to: `http://localhost:5000`

---

## Usage

1. **Dashboard** — Landing page with live system vitals and threat intelligence feed
2. **News** — Fetch and AI-summarize the latest cybersecurity headlines
3. **Log Analyzer** — Paste log entries and let A.R.I.S. flag suspicious activity
4. **Phishing Analyzer** — Paste email content for threat scoring and IOC detection
5. **CVE Lookup** — Enter a CVE ID for NVD data and AI plain-English explanation
6. **IR Checklist** — Paste an alert to generate an interactive incident response playbook
7. **Port Scanner** — Scan localhost or LAN hosts for open ports and attack surface exposure
8. **Chat** — Ask A.R.I.S. any cybersecurity question directly

---

## About This Project

This project was built to combine Python development with practical cybersecurity concepts. It demonstrates:

- Building and routing a local web server with Flask
- Integrating a locally hosted LLM for private AI inference
- Parsing and processing live threat intelligence feeds
- Writing a multithreaded port scanner engine from scratch
- Querying external security databases (NIST NVD 2.0 API)
- Implementing NIST SP 800-61 incident response workflows
- Collecting real-time system telemetry with psutil
- Implementing security best practices (rate limiting, CORS restrictions, input size limits, LAN-only scanning enforcement)
- Applying log analysis, phishing detection, and CVE triage concepts relevant to SOC operations

---

## Author

**Andrew Ruiz**
[LinkedIn](https://linkedin.com/in/andrew-ruiz-491320366)
