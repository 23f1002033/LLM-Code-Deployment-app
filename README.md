---
title: LLM Code Deployment Service
emoji: 🚀
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
---

# LLM Code Deployment Service

An automated pipeline that receives coding tasks, generates complete web applications using Google's Gemini API, deploys them to GitHub Pages, and reports results back to an evaluation server — all without manual intervention.

Built with **FastAPI**, **GitPython**, and the **Gemini 2.5 Flash** model. Deployed on **Hugging Face Spaces** via Docker.

---

## Architecture

```
┌──────────────────┐       POST /ready       ┌─────────────────────────┐
│  Evaluation      │ ──────────────────────►  │  FastAPI Backend        │
│  Server          │                          │  (Hugging Face Spaces)  │
└──────────────────┘                          └──────────┬──────────────┘
                                                         │
                                              ┌──────────▼──────────────┐
                                              │  1. Validate request    │
                                              │  2. Call Gemini API     │
                                              │  3. Generate HTML app   │
                                              │  4. Create GitHub repo  │
                                              │  5. Push code           │
                                              │  6. Enable Pages        │
                                              │  7. Notify eval server  │
                                              └──────────┬──────────────┘
                                                         │
                              ┌───────────────────────────┼───────────────────┐
                              ▼                           ▼                   ▼
                     ┌────────────────┐         ┌─────────────────┐  ┌───────────────┐
                     │  Gemini API    │         │  GitHub API     │  │  GitHub Pages │
                     │  (generation)  │         │  (repo mgmt)   │  │  (hosting)    │
                     └────────────────┘         └─────────────────┘  └───────────────┘
```

### How It Works

1. **Task Reception** — The evaluation server sends a POST request to `/ready` with a task description, round number, and authentication secret.
2. **Code Generation** — The service calls the Gemini API with the task brief (and any image attachments) to generate a complete single-file HTML application.
3. **Repository Management** — For Round 1, a new GitHub repository is created. For subsequent rounds, the existing repo is cloned and updated surgically.
4. **Deployment** — Generated code is committed, pushed, and GitHub Pages is configured automatically.
5. **Notification** — The evaluation server is notified with the repository URL, commit SHA, and live Pages URL.

---

## Project Structure

```
├── app/
│   ├── __init__.py        # Package metadata and version
│   ├── config.py          # Environment-based settings and logging
│   ├── models.py          # Pydantic request/response schemas
│   ├── llm.py             # Gemini API integration and attachment processing
│   ├── github_ops.py      # Git operations and GitHub API calls
│   ├── file_ops.py        # Local filesystem management
│   ├── notifier.py        # Evaluation server callback handler
│   ├── pipeline.py        # Main orchestration (ties everything together)
│   └── routes.py          # FastAPI endpoints and app factory
├── dashboard.py           # Streamlit monitoring UI (optional, local use)
├── main.py                # Application entry point
├── Dockerfile             # Container configuration for HF Spaces
├── requirements.txt       # Pinned Python dependencies
├── .gitignore
├── .dockerignore
├── LICENSE
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.10+
- A GitHub account with a [personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) (repo + pages scope)
- A [Google AI Studio](https://aistudio.google.com/) API key for Gemini

### Environment Variables

Create a `.env` file in the project root (this file is gitignored):

```env
GEMINI_API_KEY=your_gemini_api_key
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_USERNAME=your_github_username
STUDENT_SECRET=your_chosen_secret_key
```

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | ✅ |
| `GITHUB_TOKEN` | GitHub PAT with repo + pages permissions | ✅ |
| `GITHUB_USERNAME` | Your GitHub username | ✅ |
| `STUDENT_SECRET` | Shared secret for request authentication | ✅ |
| `GEMINI_MODEL` | Model name (default: `gemini-2.5-flash-preview-05-20`) | ❌ |
| `MAX_CONCURRENT_TASKS` | Max parallel task processing (default: `2`) | ❌ |
| `LOG_FILE_PATH` | Log file location (default: `logs/app.log`) | ❌ |
| `KEEP_ALIVE_INTERVAL_SECONDS` | Heartbeat interval in seconds (default: `30`) | ❌ |

### Local Development

```bash
# 1. Clone the repository
git clone https://github.com/23f1002033/LLM-Code-Deployment-app.git
cd LLM-Code-Deployment-app

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your .env file (see above)

# 5. Start the server
uvicorn main:app --host 0.0.0.0 --port 7860 --reload
```

The API will be available at `http://localhost:7860`. Interactive docs at `http://localhost:7860/docs`.

### Running the Dashboard (Optional)

The Streamlit dashboard provides a visual interface for monitoring:

```bash
# Default (connects to localhost:7860)
streamlit run dashboard.py

# Connect to a remote backend
DASHBOARD_API_URL=https://your-space.hf.space streamlit run dashboard.py
```

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/ready` | Secret | Submit a code generation task |
| `GET` | `/` | — | Service info |
| `GET` | `/health` | — | Health check with active task count |
| `GET` | `/status` | — | Task history and queue status |
| `GET` | `/logs?lines=200` | — | Tail the application log |
| `GET` | `/docs` | — | Interactive Swagger UI |

### Example: Submit a Task

```bash
curl -X POST http://localhost:7860/ready \
  -H "Content-Type: application/json" \
  -d '{
    "task": "my-calculator-app",
    "email": "you@example.com",
    "round": 1,
    "brief": "Build a responsive calculator with basic arithmetic operations",
    "evaluation_url": "https://eval-server.example.com/submit",
    "nonce": "abc123",
    "secret": "YOUR_SECRET_HERE",
    "attachments": []
  }'
```

---

## Deployment on Hugging Face Spaces

1. Create a new Space on [huggingface.co](https://huggingface.co/new-space) with **Docker** as the SDK.
2. Push this repository to the Space.
3. Add your environment variables as **Space Secrets** in the Settings tab.
4. The service will build and start automatically on port 7860.

---

## Security Notes

- All credentials are loaded from environment variables; nothing is hardcoded.
- The Gemini API key is sent via the `x-goog-api-key` header (not URL parameters) to avoid leaking through access logs.
- Authenticated Git URLs are constructed at runtime and never written to logs.
- The `/ready` endpoint has rate limiting (15 requests/minute per IP) and secret-based authentication.
- The `.env` file is excluded from version control via `.gitignore`.

---

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **LLM**: Google Gemini 2.5 Flash (structured JSON output)
- **Version Control**: GitPython + GitHub REST API v3
- **Hosting**: GitHub Pages (generated apps) + Hugging Face Spaces (this service)
- **Dashboard**: Streamlit (optional, for local monitoring)
- **Containerization**: Docker

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
