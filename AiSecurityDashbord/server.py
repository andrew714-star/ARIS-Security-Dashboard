
import threading
import requests
import feedparser
import json
import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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

# ── Pages ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html",
                           model=OLLAMA_MODEL,
                           date=datetime.now().strftime("%a %b %d %Y").upper())

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

# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  ⬡  A.R.I.S Security Dashboard")
    print(f"  Running at  →  http://localhost:5000\n")
    # SECURITY: Only bind to localhost (127.0.0.1) for local access only
    # NOT accessible from other devices on network or the internet
    # To allow network access, use: host='0.0.0.0' (not recommended for production)
    app.run(debug=False, port=5000, threaded=True)