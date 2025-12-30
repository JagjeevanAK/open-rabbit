"""
Simple test server for running code reviews without database dependencies.
"""
import uvicorn
from fastapi import FastAPI
from routes.bot_webhook import router as bot_router
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Open Rabbit Test Server")

# Include only the bot webhook routes (no DB required)
app.include_router(bot_router)

@app.get("/")
def root():
    return {"msg": "Open Rabbit Test Server", "status": "running"}

@app.get("/healthz")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    logger.info("Starting Open Rabbit Test Server on port 8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
