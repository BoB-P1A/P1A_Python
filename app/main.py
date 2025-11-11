from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from bson import ObjectId, errors as bson_errors
from .flowchart_build_online import build_from_sheets

load_dotenv()
MONGO_URI = os.environ.get("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client["epia"]
companies = db.get_collection("companies")

app = FastAPI(title="Flow Backend", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- helpers ----------
async def _get_company(company_id: str):
    try:
        oid = ObjectId(company_id)
    except bson_errors.InvalidId:
        raise HTTPException(status_code=400, detail="invalid company_id")
    comp = await companies.find_one({"_id": oid}, projection={"processingTasks": 1})
    if not comp:
        raise HTTPException(status_code=404, detail="company not found")
    return comp

async def _get_flow_and_sheets_by_task_id(company_id: str, task_id: str):
    comp = await _get_company(company_id)
    pts = comp.get("processingTasks", [])
    for i, t in enumerate(pts):
        if str(t.get("id")) == str(task_id):
            flow = t.get("flow") or {}
            sheets = flow.get("sheets") or {}
            return comp, i, flow, sheets
    raise HTTPException(status_code=404, detail=f"task_id {task_id} not found")

# ---------- endpoints ----------
@app.get("/api/combined")
async def get_combined(company_id: str = Query(...), task_id: str = Query(...)):
    _, _, flow, _ = await _get_flow_and_sheets_by_task_id(company_id, task_id)
    derived = flow.get("derived")
    if not derived:
        raise HTTPException(status_code=404, detail="derived not built yet")
    return derived

@app.put("/api/derived")
async def put_derived(
    company_id: str = Query(...),
    task_id: str = Query(...),
    payload: Dict[str, Any] = Body(...)
):
    comp, zi, _, _ = await _get_flow_and_sheets_by_task_id(company_id, task_id)
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="invalid payload")
    now = datetime.utcnow()
    await companies.update_one(
        {"_id": comp["_id"]},
        {"$set": {
            f"processingTasks.{zi}.flow.derived": payload,
            f"processingTasks.{zi}.flow.updated_at": now,
        }}
    )
    return {"ok": True, "updated_at": now.isoformat()}

@app.post("/api/build")
async def post_build(company_id: str = Query(...), task_id: str = Query(...)):
    comp, zi, flow, sheets = await _get_flow_and_sheets_by_task_id(company_id, task_id)
    has_rows = any(len(sheets.get(k, [])) for k in ("collect","retain","use","provide","discard"))
    if not has_rows:
        raise HTTPException(status_code=400, detail="no sheets to build")

    derived = build_from_sheets(sheets)
    now = datetime.utcnow()
    await companies.update_one(
        {"_id": comp["_id"]},
        {"$set": {
            f"processingTasks.{zi}.flow.derived": derived,
            f"processingTasks.{zi}.flow.updated_at": now,
        }}
    )
    return {"ok": True, "updated_at": now.isoformat()}

@app.put("/api/sheets")
async def put_sheets(company_id: str = Query(...), task_id: str = Query(...), payload: Dict[str, Any] = Body(...)):
    comp, zi, flow, _ = await _get_flow_and_sheets_by_task_id(company_id, task_id)
    title  = payload.get("title") or flow.get("title") or ""
    sheets = payload.get("sheets") or {}
    now = datetime.utcnow()
    await companies.update_one(
        {"_id": comp["_id"]},
        {"$set": {
            f"processingTasks.{zi}.flow.title": title,
            f"processingTasks.{zi}.flow.sheets": sheets,
            f"processingTasks.{zi}.flow.updated_at": now,
        }}
    )
    return {"ok": True}

# companies 컬렉션의 processingTasks에서 id와 taskName만 뽑아 반환
@app.get("/api/tasks")
async def list_tasks(company_id: str = Query(...)):
    comp = await _get_company(company_id)
    rows = []
    for t in comp.get("processingTasks", []):
        # id 후보를 순서대로 탐색
        raw_id = t.get("id") or t.get("_id") or t.get("task_id")
        try:
            tid = str(raw_id) if raw_id is not None else ""
        except Exception:
            tid = ""
        name = t.get("taskName") or t.get("name") or "(무제)"
        rows.append({"id": tid, "taskName": name})
    return rows