"""
Streamlit monitoring dashboard for the LLM Code Deployment Service.

Provides a visual interface for monitoring task status, viewing logs,
and checking service health. Connects to the FastAPI backend API.

Usage:
    streamlit run dashboard.py

Set the DASHBOARD_API_URL environment variable to point to your
backend (defaults to http://localhost:7860). For example:
    DASHBOARD_API_URL=https://your-space.hf.space streamlit run dashboard.py
"""

import os

import requests
import streamlit as st
import pandas as pd

API_URL = os.getenv("DASHBOARD_API_URL", "http://localhost:7860").rstrip("/")


# ---- page config ----

st.set_page_config(
    page_title="Deployment Dashboard",
    page_icon="🚀",
    layout="wide",
)

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #2a2a4a;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
    }
    .metric-card .label {
        font-size: 0.8rem;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
        margin-top: 0.3rem;
    }
    .status-ok { color: #64ffda; }
    .status-warn { color: #ffd166; }
    .status-err { color: #ff6b6b; }
</style>
""", unsafe_allow_html=True)


# ---- helpers ----

def api_get(endpoint: str, timeout: int = 5):
    """GET a JSON endpoint from the backend. Returns None on failure."""
    try:
        resp = requests.get(f"{API_URL}{endpoint}", timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def api_get_text(endpoint: str, timeout: int = 5) -> str:
    """GET a text endpoint from the backend."""
    try:
        resp = requests.get(f"{API_URL}{endpoint}", timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        return f"Error: {e}"


# ---- header ----

st.title("🚀 LLM Code Deployment — Dashboard")
st.caption(f"Backend: `{API_URL}`")
st.divider()

# ---- health metrics row ----

health = api_get("/health")

col1, col2, col3, col4 = st.columns(4)

if health:
    status_class = "status-ok" if health["status"] == "healthy" else "status-err"
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Status</div>
            <div class="value {status_class}">● {health['status'].upper()}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Version</div>
            <div class="value" style="color:#ccd6f6">{health.get('version', '—')}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Active Tasks</div>
            <div class="value" style="color:#ffd166">{health.get('active_tasks', 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Last Check</div>
            <div class="value" style="color:#8892b0;font-size:0.9rem">{health.get('timestamp', '—')}</div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.error("⚠️ Cannot reach the backend API. Is the service running?")

st.divider()

# ---- task history ----

tab_tasks, tab_logs, tab_submit = st.tabs(["📋 Task History", "📜 Logs", "📤 Submit Task"])

with tab_tasks:
    status_data = api_get("/status")
    if status_data and status_data.get("recent"):
        records = status_data["recent"]
        df = pd.DataFrame(records)

        # colour-code status
        display_cols = [
            "task_id", "round", "status", "received_at",
            "pages_url", "repo_url",
        ]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available],
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Showing {len(records)} of {status_data.get('total_tasks', '?')} total tasks")
    else:
        st.info("No tasks recorded yet.")

with tab_logs:
    log_lines = st.slider("Number of lines", 50, 2000, 300, step=50)
    if st.button("🔄 Refresh Logs"):
        st.rerun()
    log_text = api_get_text(f"/logs?lines={log_lines}")
    st.code(log_text, language="log", line_numbers=True)

with tab_submit:
    st.warning("⚡ Manual submission for testing only. Requires a valid secret.")
    with st.form("submit_task"):
        task_name = st.text_input("Task ID", placeholder="e.g. my-test-task")
        email = st.text_input("Email", placeholder="you@example.com")
        round_num = st.number_input("Round", min_value=1, max_value=10, value=1)
        brief = st.text_area("Brief", placeholder="Describe the app to generate...")
        eval_url = st.text_input("Evaluation URL", placeholder="https://eval-server.example.com/submit")
        nonce = st.text_input("Nonce", placeholder="random-nonce-value")
        secret = st.text_input("Secret", type="password")

        submitted = st.form_submit_button("Submit Task")
        if submitted:
            if not all([task_name, email, brief, eval_url, nonce, secret]):
                st.error("All fields are required.")
            else:
                payload = {
                    "task": task_name,
                    "email": email,
                    "round": round_num,
                    "brief": brief,
                    "evaluation_url": eval_url,
                    "nonce": nonce,
                    "secret": secret,
                    "attachments": [],
                }
                try:
                    resp = requests.post(f"{API_URL}/ready", json=payload, timeout=10)
                    if resp.status_code == 200:
                        st.success(f"✅ Task submitted! Response: {resp.json()}")
                    else:
                        st.error(f"❌ HTTP {resp.status_code}: {resp.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

# ---- footer ----
st.divider()
st.caption("LLM Code Deployment Service — Monitoring Dashboard v1.0")
