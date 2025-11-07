# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import os
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
# ---- import: flowchart builder (아래 2번 코드) ----
from .flowchart_build_online import build_from_sheets  

app = FastAPI(title="Flow Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ==== Mongo ====
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://ekdus20040415_db_user:20040415a@cluster0.9gwnjkb.mongodb.net/epia?retryWrites=true&w=majority"
)
client = AsyncIOMotorClient(MONGO_URI)
db = client.get_database("epia")
companies = db.get_collection("companies")

# ===== Pydantic Schemas =====
class Sheets(BaseModel):
    collect: List[Dict[str, Any]] = Field(default_factory=list)
    retain:  List[Dict[str, Any]] = Field(default_factory=list)
    use:     List[Dict[str, Any]] = Field(default_factory=list)
    provide: List[Dict[str, Any]] = Field(default_factory=list)
    discard: List[Dict[str, Any]] = Field(default_factory=list)

class FlowUpsertIn(BaseModel):
    title: Optional[str] = None
    table_schema_version: Optional[str] = "1.0.0"
    converter_version: Optional[str] = None
    sheets: Sheets

# ---------- helpers ----------
def oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid company_id")

def now():
    return datetime.utcnow()

# ---------- endpoints ----------
@app.get("/companies/{company_id}/tasks/{task_idx}/flow")
async def get_flow(company_id: str, task_idx: int):
    doc = await companies.find_one({"_id": oid(company_id)}, {
        f"processingTasks.{task_idx}.flow": 1, "_id": 0
    })
    if not doc or "processingTasks" not in doc or len(doc["processingTasks"]) <= task_idx:
        raise HTTPException(status_code=404, detail="flow not found")
    flow = doc["processingTasks"][task_idx].get("flow")
    if flow is None:
        raise HTTPException(status_code=404, detail="flow not initialized")
    return flow

@app.put("/companies/{company_id}/tasks/{task_idx}/flow/sheets")
async def upsert_sheets_and_derive(company_id: str, task_idx: int, payload: FlowUpsertIn):
    """
    1) sheets 저장
    2) Python 변환기로 derived 생성(원형숫자/description 포함)
    3) 한 번의 $set 으로 flow 갱신(rev++, updated_at)
    """
    # 1) 기존 flow 조회(없어도 OK)
    proj = await companies.find_one({"_id": oid(company_id)}, {"_id": 1, f"processingTasks.{task_idx}": 1})
    if not proj or "processingTasks" not in proj or len(proj["processingTasks"]) <= task_idx:
        raise HTTPException(status_code=404, detail="processing task not found")

    flow_path = f"processingTasks.{task_idx}.flow"
    # 기존 rev/status 가져오기
    cur_flow = proj["processingTasks"][task_idx].get("flow", {}) if proj else {}
    cur_rev = cur_flow.get("rev", 0)
    status  = cur_flow.get("status", "init")

    # 2) 변환 실행 (엑셀 없이 sheets로)
    #    title은 없으면 기존 title -> 없으면 빈 문자열
    title = payload.title or cur_flow.get("title") or ""
    combined = build_from_sheets(payload.sheets.dict(), title=title)

    # 3) flow 문서 구성
    new_flow = {
        "title": title,
        "status": "draft" if status == "init" else status,   # init -> draft 승격
        "rev": int(cur_rev) + 1,
        "table_schema_version": payload.table_schema_version or cur_flow.get("table_schema_version", "1.0.0"),
        "converter_version": payload.converter_version or cur_flow.get("converter_version", "online"),
        "sheets": payload.sheets.dict(),
        "derived": combined,  # diagram/pii/description
        "created_at": cur_flow.get("created_at") or now(),
        "updated_at": now()
    }

    # 4) 업데이트
    res = await companies.update_one(
        {"_id": oid(company_id)},
        {"$set": {flow_path: new_flow}}
    )
    if res.matched_count != 1:
        raise HTTPException(status_code=500, detail="failed to update flow")

    return {"ok": True, "rev": new_flow["rev"], "status": new_flow["status"]}

@app.post("/flows/convert")
async def convert_only(payload: FlowUpsertIn):
    """
    DB 저장 없이 변환 결과만 리턴 (테스트/디버그용)
    """
    combined = build_from_sheets(payload.sheets.dict(), title=payload.title or "")
    return combined
