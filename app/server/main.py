
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from .parser import parse as parse_text
from .search import search as search_logic
from .schema import SearchRequest
import json
from pathlib import Path

app = FastAPI(title="Food Search v2", version="0.1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend from / and /web
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/web", StaticFiles(directory=WEB_DIR, html=True), name="web")

@app.get("/")
def root():
    return RedirectResponse(url="/web/index.html")

@app.post("/parse")
def parse_endpoint(payload: dict = Body(...)):
    text = payload.get("text","")
    parsed = parse_text(text)
    return parsed

@app.post("/search")
def search_endpoint(payload: dict = Body(...)):
    return search_logic(payload)

@app.get("/catalog")
def catalog():
    data = json.loads((Path(__file__).resolve().parent.parent / "data" / "catalog.json").read_text(encoding="utf-8"))
    return {"count": len(data), "items": data}
