
import threading
import requests
import feedparser
import time
import platform
import subprocess
import sys
import json
import os
import signal
import atexit
import shutil
import socket as _socket
import ipaddress as _ipaddress
import concurrent.futures
from queue import Queue as _Queue
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

try:
    import psutil
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "--quiet"])
    import psutil

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR, static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max request size

# SECURITY: Restrict CORS to localhost only
CORS(app, origins=['http://localhost:5000', 'http://127.0.0.1:5000'])

# SECURITY: Rate limiting to prevent abuse
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=['200 per day', '50 per hour']
)

# ── Config ──────────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:latest"
NEWS_FEEDS   = [
    "https://www.bleepingcomputer.com/feed/",
    "https://feeds.feedburner.com/TheHackersNews",
    "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml",
]

OLLAMA_COMMAND = ["ollama", "serve"]
_ollama_process = None
_ollama_locally_started = False


def _is_ollama_running():
    try:
        with _socket.create_connection(("127.0.0.1", 11434), timeout=1.0):
            return True
    except OSError:
        return False


def _start_ollama_service():
    global _ollama_process, _ollama_locally_started
    if _is_ollama_running():
        return
    if shutil.which("ollama") is None:
        print("Warning: ollama executable not found; local LLM service will not be started.")
        return

    try:
        _ollama_process = subprocess.Popen(
            OLLAMA_COMMAND,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        _ollama_locally_started = True

        deadline = time.time() + 15
        while time.time() < deadline:
            if _is_ollama_running():
                return
            time.sleep(0.5)

        print("Warning: ollama service did not become available in time.")
    except Exception as exc:
        print(f"Warning: failed to start ollama service: {exc}")


def _stop_ollama_service():
    global _ollama_process, _ollama_locally_started
    if not _ollama_locally_started or _ollama_process is None:
        return

    try:
        if _ollama_process.poll() is None:
            _ollama_process.terminate()
            _ollama_process.wait(timeout=5)
    except Exception:
        try:
            _ollama_process.kill()
            _ollama_process.wait(timeout=5)
        except Exception:
            pass
    finally:
        _ollama_process = None
        _ollama_locally_started = False


def _shutdown_handler(signum=None, frame=None):
    _stop_ollama_service()
    sys.exit(0)

atexit.register(_stop_ollama_service)
for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT):
    signal.signal(sig, _shutdown_handler)

# ── Pages ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html",
                           model=OLLAMA_MODEL,
                           date=datetime.now().strftime("%a %b %d %Y").upper())

#___API:System info___________________________________________________________
@app.route("/api/sys-dashboard")
def sysdashboard():
    def uptime_str():
        delta = timedelta(seconds=int(time.time() - psutil.boot_time()))
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        mins, _ = divmod(rem, 60)
        parts = []
        if days:  parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        parts.append(f"{mins}m")
        return " ".join(parts)
 
    def bytes_human(n):
        for unit in ("B","KB","MB","GB","TB"):
            if abs(n) < 1024.0:
                return f"{n:.1f} {unit}"
            n /= 1024.0
        return f"{n:.1f} PB"
 
    uname = platform.uname()
    vm    = psutil.virtual_memory()
    swap  = psutil.swap_memory()
    freq  = psutil.cpu_freq()
    times = psutil.cpu_times_percent(interval=0.3)
 
    # Seed CPU then measure
    for p in psutil.process_iter(["pid","cpu_percent"]):
        try: p.cpu_percent()
        except: pass
    time.sleep(0.4)
 
    procs = []
    for p in psutil.process_iter(["pid","name","username","status","cpu_percent","memory_percent"], ad_value=None):
        try:
            info = p.info
            procs.append({
                "pid":    info["pid"],
                "name":   (info["name"] or "?")[:24],
                "user":   info["username"] or "?",
                "status": info["status"] or "?",
                "cpu":    round(info["cpu_percent"] or 0.0, 1),
                "mem":    round(info["memory_percent"] or 0.0, 2),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x["cpu"], reverse=True)
 
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device":     part.device,
                "mountpoint": part.mountpoint,
                "fstype":     part.fstype,
                "total":      bytes_human(u.total),
                "used":       bytes_human(u.used),
                "free":       bytes_human(u.free),
                "percent":    u.percent,
            })
        except PermissionError:
            pass
 
    net_io = psutil.net_io_counters(pernic=False)
    ifaces = []
    addrs  = psutil.net_if_addrs()
    stats  = psutil.net_if_stats()
    for name, addr_list in addrs.items():
        st  = stats.get(name)
        ips = [a.address for a in addr_list if str(a.family) in ("AddressFamily.AF_INET","2")]
        ifaces.append({
            "name":  name,
            "ips":   ips,
            "up":    st.isup if st else False,
            "speed": st.speed if st else 0,
        })
 
    return jsonify({
        "os": {
            "system":    uname.system,
            "node":      uname.node,
            "release":   uname.release,
            "machine":   uname.machine,
            "processor": uname.processor or platform.processor(),
            "python":    platform.python_version(),
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
            "uptime":    uptime_str(),
        },
        "cpu": {
            "physical":  psutil.cpu_count(logical=False),
            "logical":   psutil.cpu_count(logical=True),
            "total_pct": psutil.cpu_percent(interval=0.3),
            "per_core":  psutil.cpu_percent(interval=0.3, percpu=True),
            "freq_cur":  round(freq.current, 1) if freq else None,
            "freq_max":  round(freq.max,     1) if freq else None,
            "user_pct":  round(times.user,   1),
            "sys_pct":   round(times.system, 1),
            "idle_pct":  round(times.idle,   1),
        },
        "ram": {
            "total":        bytes_human(vm.total),
            "used":         bytes_human(vm.used),
            "available":    bytes_human(vm.available),
            "percent":      vm.percent,
            "swap_total":   bytes_human(swap.total),
            "swap_used":    bytes_human(swap.used),
            "swap_percent": swap.percent,
        },
        "disks":   disks,
        "network": {
            "sent":      bytes_human(net_io.bytes_sent),
            "recv":      bytes_human(net_io.bytes_recv),
            "interfaces": ifaces,
        },
        "processes": procs[:15],
    })
 

# ── API: Chat ────────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
@limiter.limit("30 per hour")
def chat():
    data    = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    prompt = (
        "Your name is A.R.I.S. You are a helpful cybersecurity assistant. "
        "Answer clearly and concisely. If the question is not security related, "
        "still help but gently steer back to security topics.\n\n"
        f"User: {message}"
    )

    def generate():
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                stream=True,
                timeout=60,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'error': 'Ollama service unavailable. Ensure it is running locally.'})}\n\n"
        except requests.exceptions.Timeout:
            yield f"data: {json.dumps({'error': 'Request timeout. Please try again.'})}\n\n"
        except Exception:
            yield f"data: {json.dumps({'error': 'An error occurred processing your request.'})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ── API: Log Analyze ─────────────────────────────────────────────────────────
@app.route("/api/analyze", methods=["POST"])
@limiter.limit("20 per hour")
def analyze():
    data     = request.get_json()
    log_text = data.get("log", "").strip()
    if not log_text:
        return jsonify({"error": "No log content provided"}), 400

    prompt = (
        "You are a cybersecurity expert analyzing system logs. "
        "Review the following log entries and:\n"
        "1. Identify any suspicious or malicious activity\n"
        "2. Flag failed login attempts, port scans, or unusual access patterns\n"
        "3. Rate the severity: LOW / MEDIUM / HIGH\n"
        "4. Recommend next steps\n\n"
        "Be concise and use bullet points.\n\n"
        f"LOG:\n{log_text[:3000]}"
    )

    def generate():
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'error': 'Cannot connect to Ollama at ' + OLLAMA_URL + '. Make sure Ollama is running: ollama serve'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

#__API: Phishing Analyze ─────────────────────────────────────────────────────────
@app.route("/api/emailanalyze", methods=["POST"])
@limiter.limit("50 per hour")
def emailanalyze():
    data     = request.get_json()
    email_text = data.get("email", "").strip()
    if not email_text:
        return jsonify({"error": "No email content provided"}), 400

    prompt = (
        "You are a cybersecurity expert analyzing email content for phishing attempts. "
        "Review the following email and output the analysis using clear labels. "
        "Include:\n"
        "1. A short summary of the email intent.\n"
        "2. A single line starting with 'Score:' followed by a number from 0 to 10.\n"
        "3. A single line starting with 'Threat:' followed by LOW, MEDIUM, or HIGH.\n"
        "4. A single line starting with 'Confidence:' followed by High, Medium, or Low.\n"
        "5. Recommended action in one sentence.\n\n"
        "Be concise and avoid extra commentary.\n\n"
        f"EMAIL:\n{email_text[:3000]}"
    )

    def generate():
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'error': 'Cannot connect to Ollama at ' + OLLAMA_URL + '. Make sure Ollama is running: ollama serve'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

# ── API: News ────────────────────────────────────────────────────────────────
@app.route("/api/news")
@limiter.limit("10 per hour")
def news():
    def generate():
        articles = []
        for url in NEWS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    articles.append({
                        "title":   entry.get("title", "No title"),
                        "summary": (entry.get("summary") or entry.get("description", ""))[:400],
                        "link":    entry.get("link", ""),
                    })
            except Exception as e:
                yield f"data: {json.dumps({'status': f'⚠️ Could not load {url}: {e}'})}\n\n"

        if not articles:
            yield f"data: {json.dumps({'error': 'No articles found. Check your internet connection.'})}\n\n"
            return

        yield f"data: {json.dumps({'status': f'✅ Found {len(articles)} articles. Summarizing with {OLLAMA_MODEL}...'})}\n\n"

        for i, art in enumerate(articles):
            yield f"data: {json.dumps({'article_start': {'index': i+1, 'total': len(articles), 'title': art['title'], 'link': art['link']}})}\n\n"

            prompt = (
                f"You are a cybersecurity analyst. Summarize this article in a few sentences, "
                f"then in one sentence explain why it matters to someone learning cybersecurity.\n\n"
                f"Title: {art['title']}\nContent: {art['summary']}"
            )
            try:
                resp = requests.post(
                    OLLAMA_URL,
                    json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                    stream=True,
                    timeout=120,
                )
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        if chunk.get("done"):
                            yield f"data: {json.dumps({'article_end': art['link']})}\n\n"
                            break
            except Exception as e:
                yield f"data: {json.dumps({'token': f'Error: {str(e)}'})}\n\n"
                yield f"data: {json.dumps({'article_end': art['link']})}\n\n"

        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
# ── API: CVE Lookup ──────────────────────────────────────────────────────────
@app.route("/api/cve", methods=["POST"])
@limiter.limit("30 per hour")
def cve_lookup():
    data   = request.get_json()
    cve_id = data.get("cve_id", "").strip().upper()
 
    if not cve_id or not cve_id.startswith("CVE-"):
        return jsonify({"error": "Invalid CVE ID. Use format CVE-YYYY-NNNNN"}), 400
 
    # NIST NVD 2.0 API — no key required for moderate usage
    nvd_url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    try:
        resp = requests.get(nvd_url, timeout=10,
                            headers={"User-Agent": "ARIS-Security-Dashboard/1.0"})
        resp.raise_for_status()
        body = resp.json()
    except requests.exceptions.Timeout:
        return jsonify({"error": "NIST NVD request timed out. Try again."}), 504
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"NIST NVD returned {resp.status_code}"}), 502
    except Exception as e:
        return jsonify({"error": f"Failed to contact NIST NVD: {str(e)}"}), 502
 
    vulns = body.get("vulnerabilities", [])
    if not vulns:
        return jsonify({"error": f"{cve_id} not found in NVD database."}), 404
 
    cve_data = vulns[0].get("cve", {})
 
    # Description (prefer English)
    descriptions = cve_data.get("descriptions", [])
    description = next(
        (d["value"] for d in descriptions if d.get("lang") == "en"),
        descriptions[0]["value"] if descriptions else "No description available."
    )
 
    # CVSS score + severity — try v3.1 first, fall back to v3.0, then v2
    metrics = cve_data.get("metrics", {})
    cvss_score = None
    severity   = "UNKNOWN"
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key, [])
        if entries:
            cvss_data = entries[0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            severity   = (
                entries[0].get("baseSeverity")
                or cvss_data.get("baseSeverity")
                or "UNKNOWN"
            )
            break
 
    # References
    refs = [r.get("url", "") for r in cve_data.get("references", []) if r.get("url")]
 
    # Dates
    published = cve_data.get("published", "")
    modified  = cve_data.get("lastModified", "")
 
    return jsonify({
        "cve_id":      cve_id,
        "description": description,
        "cvss_score":  cvss_score,
        "severity":    severity.upper(),
        "published":   published,
        "modified":    modified,
        "references":  refs[:10],
    })
 
 

#__API: CVE Explain ────────────────────────────────────────────────────────────────
@app.route("/api/cve-explain", methods=["POST"])
@limiter.limit("20 per hour")
def cve_explain():
    data       = request.get_json()
    cve_id    = data.get("cve_id", "").strip() if isinstance(data.get("cve_id"), str) else ""
    description = data.get("description", "").strip() if isinstance(data.get("description"), str) else ""
    cvss_score  = data.get("cvss_score")
    severity    = data.get("severity", "UNKNOWN").strip() if isinstance(data.get("severity"), str) else "UNKNOWN"

    if not description:
        return jsonify({"error": "No CVE description provided"}), 400
    
    # Format score line for prompt
    if cvss_score is not None:
        try:
            score_float = float(cvss_score)
            score_line = f"CVSS Score: {score_float}/10 ({severity})"
        except (ValueError, TypeError):
            score_line = f"Severity: {severity}"
    else:
        score_line = f"Severity: {severity}"
    prompt = (
        f"You are A.R.I.S, a cybersecurity expert assistant."
        f"Explain the following CVE to a security analyst in clear, plain English."
        f"Structure your response as:\n"
        f"1. WHAT IT IS - one short paragraph on what the vulnerability is.\n"
        f"2. HOW IT WORKS - briefly explain the attack vector and how an attaker could exploit it.\n"
        f"3. WHO IS AFFECTED - affected software, versions, or systems.\n"
        f"4. HOW TO FIX IT - patch, workaround, or mitigation steps.\n"
        f"5. RISK RATING - your one-sentence assessment given {score_line}.\n\n"
        f"CVE ID: {cve_id}\n"
        f"{score_line}\n"
        f"Official Description:\n{description[:2000]}"

    )

    def generate():
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'error': 'Cannot connect to Ollama at ' + OLLAMA_URL + '. Make sure Ollama is running: ollama serve'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ── API: IR Checklist ────────────────────────────────────────────────────────
@app.route("/api/ir-checklist", methods=["POST"])
@limiter.limit("20 per hour")
def ir_checklist():
    data       = request.get_json()
    alert_text = data.get("alert", "").strip()
    if not alert_text:
        return jsonify({"error": "No alert content provided"}), 400

    prompt = (
        "You are A.R.I.S., a senior SOC analyst and incident responder. "
        "A security alert has been pasted below. Your job is to:\n\n"
        "1. INCIDENT CLASSIFICATION — Identify the incident type in one line "
        "(e.g. Brute Force Attack, Ransomware, Data Exfiltration, Phishing, "
        "Privilege Escalation, Port Scan, Malware Infection, Insider Threat, DDoS, Other).\n"
        "2. SEVERITY — Rate it: CRITICAL / HIGH / MEDIUM / LOW with a one-sentence justification.\n"
        "3. IMMEDIATE ACTIONS (first 15 minutes) — Numbered list, 3-5 steps. Be specific.\n"
        "4. SHORT-TERM CONTAINMENT (first hour) — Numbered list, 3-5 steps.\n"
        "5. INVESTIGATION CHECKLIST — Bulleted list of artifacts to collect and questions to answer.\n"
        "6. ESCALATION — Who should be notified and when.\n"
        "7. LESSONS LEARNED PROMPT — One question to drive a post-incident review.\n\n"
        "Format each section with its heading in ALL CAPS followed by a colon. "
        "Be direct and actionable — this is a live incident.\n\n"
        f"ALERT:\n{alert_text[:3000]}"
    )

    def generate():
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
        except requests.exceptions.ConnectionError:
            yield f"data: {json.dumps({'error': 'Cannot connect to Ollama. Make sure it is running: ollama serve'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ── API: Alert Dashboard snapshot ────────────────────────────────────────────
@app.route("/api/dashboard-snapshot")
@limiter.limit("30 per hour")
def dashboard_snapshot():
    """Returns a lightweight JSON snapshot used by the Alert Dashboard."""
    import re

    # System vitals (reuse psutil already imported)
    vm      = psutil.virtual_memory()
    cpu_pct = psutil.cpu_percent(interval=0.5)
    disks   = []
    for part in psutil.disk_partitions(all=False):
        try:
            u = psutil.disk_usage(part.mountpoint)
            disks.append({"mount": part.mountpoint, "percent": u.percent})
        except PermissionError:
            pass

    # Pull latest headlines from feeds (no LLM — fast)
    headlines = []
    for url in NEWS_FEEDS[:2]:          # only first two to keep it snappy
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                title = entry.get("title", "")
                link  = entry.get("link", "")
                # Rough severity heuristic from title keywords
                t = title.lower()
                if any(w in t for w in ["critical","zero-day","ransomware","exploit","rce","remote code"]):
                    sev = "CRITICAL"
                elif any(w in t for w in ["high","vulnerability","breach","attack","malware","backdoor"]):
                    sev = "HIGH"
                elif any(w in t for w in ["medium","patch","update","warn","phish"]):
                    sev = "MEDIUM"
                else:
                    sev = "LOW"
                headlines.append({"title": title, "link": link, "severity": sev})
        except Exception:
            pass

    return jsonify({
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "vitals": {
            "cpu":  round(cpu_pct, 1),
            "ram":  round(vm.percent, 1),
            "disk": disks[0]["percent"] if disks else 0,
        },
        "headlines": headlines[:6],
        "threat_level": (
            "CRITICAL" if any(h["severity"] == "CRITICAL" for h in headlines) else
            "HIGH"     if any(h["severity"] == "HIGH"     for h in headlines) else
            "MEDIUM"   if any(h["severity"] == "MEDIUM"   for h in headlines) else
            "LOW"
        ),
    })


# ── Port Scanner — multithreaded engine (by Andrew Ruiz) ────────────────────
import socket as _socket
import ipaddress as _ipaddress
from queue import Queue as _Queue

# Expanded service name map (50+ entries)
_SERVICE_NAMES = {
     20: "FTP-data",   21: "FTP",         22: "SSH",        23: "Telnet",
     25: "SMTP",       53: "DNS",         67: "DHCP",       68: "DHCP",
     69: "TFTP",       80: "HTTP",       110: "POP3",      119: "NNTP",
    123: "NTP",       135: "RPC",        137: "NetBIOS",   139: "NetBIOS",
    143: "IMAP",      161: "SNMP",       162: "SNMP-trap", 179: "BGP",
    389: "LDAP",      443: "HTTPS",      445: "SMB",       465: "SMTPS",
    514: "Syslog",    587: "SMTP-sub",   636: "LDAPS",     993: "IMAPS",
    995: "POP3S",    1080: "SOCKS",     1194: "OpenVPN",  1433: "MSSQL",
   1521: "OracleDB", 1723: "PPTP",      2049: "NFS",      2181: "ZooKeeper",
   2375: "Docker",   3000: "Dev-HTTP",  3306: "MySQL",    3389: "RDP",
   4444: "Metasploit",5000: "Dev-HTTP", 5432: "PostgreSQL",5900: "VNC",
   5985: "WinRM",    5986: "WinRM-SSL", 6379: "Redis",    6443: "K8s-API",
   8080: "HTTP-alt", 8443: "HTTPS-alt", 8888: "Jupyter",  9200: "Elasticsearch",
   9418: "Git",     27017: "MongoDB",  27018: "MongoDB",
}

# Top-100 most scanned ports
_TOP_100_PORTS = [
     7,  9, 13, 21, 22, 23, 25, 26, 37, 53, 79, 80, 81, 88,106,
   110,111,113,119,135,139,143,144,179,199,389,427,443,444,445,
   465,513,514,515,543,544,548,554,587,631,646,873,990,993,995,
  1080,1099,1194,1433,1521,1720,1723,1755,1900,2000,2001,2049,
  2121,2181,2375,3000,3128,3306,3389,3986,4444,4899,5000,5009,
  5051,5101,5190,5357,5432,5631,5666,5800,5900,5985,5986,6000,
  6001,6379,6443,7070,8008,8009,8080,8081,8443,8888,9100,9200,
  9418,9999,10000,32768,49152,27017,
]

# Risk classification
_CRITICAL_PORTS = {23, 4444, 5900, 5985, 5986}
_HIGH_PORTS     = {21, 69, 135, 137, 139, 389, 445, 636, 1433, 1521,
                   2375, 3306, 3389, 5432, 6379, 6443, 9200, 27017, 27018}
_MEDIUM_PORTS   = {22, 25, 53, 80, 110, 143, 587, 993, 995, 1080,
                   3000, 5000, 8080, 8888}

def _port_risk(port: int) -> str:
    if port in _CRITICAL_PORTS: return "CRITICAL"
    if port in _HIGH_PORTS:     return "HIGH"
    if port in _MEDIUM_PORTS:   return "MEDIUM"
    return "LOW"

def _grab_banner(host: str, port: int, timeout: float = 1.0) -> str:
    """Attempt to grab a service banner from an open port."""
    try:
        s = _socket.socket()
        s.settimeout(timeout)
        s.connect((host, port))
        # Send proper HTTP request for web ports
        if port in (80, 8080, 3000, 5000, 8000, 8081):
            s.send(b"GET / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
        raw = s.recv(1024).decode("utf-8", errors="replace").strip()
        s.close()
        for line in raw.splitlines():
            line = line.strip()
            if line:
                return line[:80]
    except Exception:
        pass
    return ""


class _PortScanner:
    """
    Multithreaded TCP port scanner.
    Runs all ports concurrently via a thread pool and a Queue,
    then calls back on_found(entry) for each open port as it's discovered.
    """
    def __init__(self, host: str, timeout: float = 0.7,
                 num_threads: int = 150, grab_banner: bool = True):
        self.host        = host
        self.timeout     = timeout
        self.num_threads = num_threads
        self.grab_banner = grab_banner
        self._lock       = threading.Lock()
        self._queue: _Queue = _Queue()

    def scan(self, ports: list, on_found=None) -> list:
        """
        Scan the given port list.  For each open port, call on_found(entry)
        immediately (thread-safe), then return the sorted list when done.
        """
        open_ports = []

        def _scan_port(port: int):
            try:
                s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                s.settimeout(self.timeout)
                result = s.connect_ex((self.host, port))
                s.close()
                if result != 0:
                    return

                # Service name — try OS first, fall back to our map
                try:
                    service = _socket.getservbyport(port, "tcp")
                except OSError:
                    service = _SERVICE_NAMES.get(port, f"unknown({port})")

                banner = _grab_banner(self.host, port, self.timeout) if self.grab_banner else ""
                risk   = _port_risk(port)

                entry = {"port": port, "service": service,
                         "banner": banner, "risk": risk}
                with self._lock:
                    open_ports.append(entry)
                if on_found:
                    on_found(entry)   # called while lock is NOT held
            except Exception:
                pass

        def _worker():
            while True:
                port = self._queue.get()
                if port is None:
                    break
                _scan_port(port)
                self._queue.task_done()

        for port in ports:
            self._queue.put(port)

        n_workers = min(self.num_threads, len(ports))
        workers = [threading.Thread(target=_worker, daemon=True)
                   for _ in range(n_workers)]
        for w in workers:
            w.start()

        self._queue.join()          # wait for all ports to finish
        for _ in workers:
            self._queue.put(None)   # poison pills
        for w in workers:
            w.join()

        open_ports.sort(key=lambda x: x["port"])
        return open_ports


# ── API: Vulnerability Scanner ───────────────────────────────────────────────
@app.route("/api/scan", methods=["POST"])
@limiter.limit("10 per hour")
def vuln_scan():
    """
    Multithreaded port + service scanner.
    LEGAL NOTICE: Only scan hosts you own or have explicit permission to scan.
    Restricted to private/loopback (RFC-1918) ranges.
    """
    data   = request.get_json()
    target = data.get("target", "").strip()
    mode   = data.get("mode", "quick")   # quick | top100 | full | stealth

    if not target:
        return jsonify({"error": "No target provided"}), 400

    # Resolve hostname → IP
    try:
        resolved_ip = _socket.gethostbyname(target)
    except _socket.gaierror:
        return jsonify({"error": f"Could not resolve host: {target}"}), 400

    # Safety guard — private/loopback only
    try:
        addr    = _ipaddress.ip_address(resolved_ip)
        allowed = addr.is_loopback or addr.is_private
    except ValueError:
        allowed = False

    if not allowed:
        return jsonify({"error": (
            "A.R.I.S. restricts scanning to localhost and private network ranges "
            "(10.x.x.x, 172.16-31.x.x, 192.168.x.x) to prevent unauthorized scanning. "
            "Only scan systems you own or have explicit written permission to test."
        )}), 403

    # Port list by mode
    if mode == "quick":
        ports = [21,22,23,25,53,80,110,143,443,445,1433,1521,
                 3306,3389,5432,5900,6379,8080,8443,8888,9200,27017]
    elif mode == "top100":
        ports = _TOP_100_PORTS
    elif mode == "full":
        ports = list(range(1, 1025))
    else:  # stealth / attack-surface
        ports = [21,22,23,25,53,80,443,445,1433,1521,2375,3306,
                 3389,4444,5900,5985,6379,8080,8443,9200,27017]

    def generate():
        yield f"data: {json.dumps({'status': f'Starting {mode.upper()} scan of {target} ({resolved_ip}) — {len(ports)} ports, multithreaded...'})}\n\n"

        found_ports = []

        def on_found(entry):
            found_ports.append(entry)
            # Stream each discovered port immediately to the frontend
            yield_queue.put(entry)

        # Use a queue to bridge the scanner threads → Flask generator
        yield_queue = _Queue()
        scan_done   = threading.Event()

        def run_scan():
            scanner = _PortScanner(
                host=resolved_ip,
                timeout=0.7,
                num_threads=150,
                grab_banner=True,
            )
            scanner.scan(ports, on_found=on_found)
            scan_done.set()

        scan_thread = threading.Thread(target=run_scan, daemon=True)
        scan_thread.start()

        # Stream port results as they arrive
        while not scan_done.is_set() or not yield_queue.empty():
            try:
                entry = yield_queue.get(timeout=0.2)
                yield f"data: {json.dumps({'port_found': entry})}\n\n"
            except Exception:
                pass   # timeout — loop back and check scan_done

        scan_thread.join()

        # AI risk assessment
        if found_ports:
            found_ports.sort(key=lambda x: x["port"])
            port_summary = "\n".join(
                f"  {p['port']}/tcp  {p['service']}  [{p['risk']}]  {p['banner']}"
                for p in found_ports
            )
            prompt = (
                "You are A.R.I.S., a cybersecurity expert. "
                f"A port scan of {target} found the following open ports:\n\n"
                f"{port_summary}\n\n"
                "Provide a concise security assessment:\n"
                "1. ATTACK SURFACE SUMMARY — what exposure does this represent?\n"
                "2. HIGH-RISK FINDINGS — call out any immediately concerning ports/services.\n"
                "3. RECOMMENDED HARDENING — 3-5 specific steps to reduce risk.\n\n"
                "Be direct and actionable."
            )
            yield f"data: {json.dumps({'status': f'Scan complete — {len(found_ports)} port(s) open. Generating AI assessment...'})}\n\n"
            try:
                resp = requests.post(
                    OLLAMA_URL,
                    json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                    stream=True, timeout=120,
                )
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield f"data: {json.dumps({'ai_token': token})}\n\n"
                        if chunk.get("done"):
                            break
            except Exception as e:
                yield f"data: {json.dumps({'ai_token': f'AI assessment unavailable: {e}'})}\n\n"
        else:
            yield f"data: {json.dumps({'status': 'No open ports found in scanned range.'})}\n\n"

        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _start_ollama_service()
    print("\n  ⬡  A.R.I.S Security Dashboard")
    print(f"  Running at  →  http://localhost:5000\n")
    # SECURITY: Only bind to localhost (127.0.0.1) for local access only
    # NOT accessible from other devices on network or the internet
    # To allow network access, use: host='0.0.0.0' (not recommended for production)

    try:
        app.run(debug=False, port=5000, threaded=True, use_reloader=False)
    finally:
        _stop_ollama_service()
