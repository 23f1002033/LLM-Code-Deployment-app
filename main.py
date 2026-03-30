"""
Entry point for the LLM Code Deployment Service.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 7860
"""

from app.routes import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7860, reload=True)
