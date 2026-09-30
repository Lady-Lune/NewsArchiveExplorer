from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from data_loader import DataStore

BASE = Path(__file__).resolve().parent
store = DataStore(BASE / "data")

app = FastAPI(title="BERTopic Visualizer")
templates = Jinja2Templates(directory=BASE / "templates")


# ---- pages -------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={
        "request": request,
        "topics": store.topics,
        "total_docs": store.total_documents,
        "num_topics": len(store.topics),
    })


@app.get("/topic/{topic_id}", response_class=HTMLResponse)
async def topic_page(request: Request, topic_id: int):
    topic = store.get_topic(topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    return templates.TemplateResponse(request=request, name="topic.html", context={
        "request": request,
        "topic": topic,
    })


# ---- API ---------------------------------------------------------------

@app.get("/api/topics")
async def api_topics():
    return store.topics


@app.get("/api/topics/{topic_id}/documents")
async def api_documents(
    topic_id: int,
    page: int = 1,
    limit: int = 20,
    min_probability: float = 0.0,
    sort: str = "default",
    order: str = "desc",
):
    if not store.get_topic(topic_id):
        raise HTTPException(404, "Topic not found")
    limit = max(1, min(limit, 100))
    page = max(1, page)
    min_probability = max(0.0, min(1.0, min_probability))
    if sort not in ("default", "strength"):
        raise HTTPException(400, "Sort must be 'default' or 'strength'")
    if order not in ("asc", "desc"):
        raise HTTPException(400, "Order must be 'asc' or 'desc'")
    all_docs = store.get_documents(topic_id)
    docs = [d for d in all_docs if d["probability"] >= min_probability]
    if sort == "strength":
        docs.sort(key=lambda d: d["probability"], reverse=order == "desc")
    start = (page - 1) * limit
    return {
        "documents": docs[start:start + limit],
        "total": len(docs),
        "total_unfiltered": len(all_docs),
        "filtered_out": len(all_docs) - len(docs),
        "filtered_percentage": round((len(all_docs) - len(docs)) / len(all_docs) * 100, 1) if all_docs else 0,
        "page": page,
        "has_more": start + limit < len(docs),
    }


@app.get("/api/topics/{topic_id}/time_frequency")
async def api_time_frequency(topic_id: int, granularity: str = "month"):
    if not store.get_topic(topic_id):
        raise HTTPException(404, "Topic not found")
    if granularity not in ("day", "month"):
        raise HTTPException(400, "Granularity must be 'day' or 'month'")
    return {"data": store.get_time_frequency(topic_id, granularity)}


@app.get("/api/metadata")
async def api_metadata():
    return {
        "total_documents": store.total_documents,
        "num_topics": len(store.topics),
    }