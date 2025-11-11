# main.py
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# 같은 디렉토리라면 점(.) 없이 임포트
from .flowchart_build_online import build_from_sheets

load_dotenv()
# ---- 환경변수에서 Mongo URI 읽기 ----
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB  = os.environ.get("MONGO_DB", "epia") 

app = FastAPI(title="Flow Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ==== Mongo (단일 컬렉션: processingTasks, company_id 없음) ====
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://ekdus20040415_db_user:20040415a@cluster0.9gwnjkb.mongodb.net/epia?retryWrites=true&w=majority"
)
client = AsyncIOMotorClient(MONGO_URI)
db = client.get_database(MONGO_DB)
tasks = db.get_collection("processingTasks")   # ← 여기 하나만 씀 (task_idx 기준)

# ===== Schemas =====
class Sheets(BaseModel):
    collect: List[Dict[str, Any]] = Field(default_factory=list)
    retain:  List[Dict[str, Any]] = Field(default_factory=list)
    use:     List[Dict[str, Any]] = Field(default_factory=list)
    provide: List[Dict[str, Any]] = Field(default_factory=list)
    discard: List[Dict[str, Any]] = Field(default_factory=list)

class FlowDoc(BaseModel):
    title: Optional[str] = ""
    rev: int = 0
    sheets: Sheets = Field(default_factory=Sheets)
    derived: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

# ---------- helpers ----------
async def _get_task(task_idx: int) -> Dict[str, Any]:
    doc = await tasks.find_one({"_id": task_idx})
    return doc or {}

async def _ensure_task(task_idx: int) -> Dict[str, Any]:
    doc = await _get_task(task_idx)
    if not doc:
        # 초기 문서 생성
        doc = {
            "_id": task_idx,
            "flow": FlowDoc().dict()
        }
        await tasks.insert_one(doc)
    return doc

# ---------- endpoints ----------

@app.get("/api/combined/{task_idx}")
async def get_combined(task_idx: int):
    """
    현재 DB에 저장된 derived(combined)를 그대로 리턴
    """
    doc = await _get_task(task_idx)
    if not doc or "flow" not in doc or not doc["flow"].get("derived"):
        raise HTTPException(status_code=404, detail="derived not found")
    return doc["flow"]["derived"]

@app.put("/api/derived/{task_idx}")
async def put_derived(task_idx: int, combined: Dict[str, Any] = Body(...)):
    """
    프런트(화면)의 현재 상태를 그대로 DB의 derived에 저장
    """
    doc = await _ensure_task(task_idx)
    flow = doc.get("flow", {})
    flow["derived"] = combined
    flow["rev"] = int(flow.get("rev", 0)) + 1
    flow["updated_at"] = datetime.utcnow()
    if not flow.get("created_at"):
        flow["created_at"] = flow["updated_at"]
    await tasks.update_one({"_id": task_idx}, {"$set": {"flow": flow}})
    return {"ok": True, "rev": flow["rev"]}

@app.post("/api/build")
async def post_build(task_idx: int):
    """
    DB에 저장된 sheets를 읽어 변환기(build_from_sheets) 실행 → derived 갱신
    (= '흐름도에서 불러오기' 버튼의 서버 측 동작)
    """
    doc = await _ensure_task(task_idx)
    flow = doc.get("flow", {})
    sheets = flow.get("sheets") or {}

    # sheets가 없다면 에러
    if not isinstance(sheets, dict) or all(len(sheets.get(k, [])) == 0 for k in ["collect","retain","use","provide","discard"]):
        raise HTTPException(status_code=400, detail="no sheets to build")

    title = flow.get("title", "")
    combined = build_from_sheets(sheets, title=title)

    flow["derived"] = combined
    flow["rev"] = int(flow.get("rev", 0)) + 1
    flow["updated_at"] = datetime.utcnow()
    if not flow.get("created_at"):
        flow["created_at"] = flow["updated_at"]

    await tasks.update_one({"_id": task_idx}, {"$set": {"flow": flow}})
    return {"ok": True, "rev": flow["rev"]}

# (선택) sheets 저장용: 프런트/다른 페이지에서 입력한 표를 저장할 때 사용
@app.put("/api/sheets/{task_idx}")
async def put_sheets(task_idx: int, payload: Dict[str, Any] = Body(...)):
    """
    { title?: str, sheets: Sheets } 형태 저장
    """
    doc = await _ensure_task(task_idx)
    flow = doc.get("flow", {})
    flow["title"] = payload.get("title") or flow.get("title") or ""
    flow["sheets"] = payload.get("sheets") or flow.get("sheets") or Sheets().dict()
    flow["updated_at"] = datetime.utcnow()
    if not flow.get("created_at"):
        flow["created_at"] = flow["updated_at"]
    await tasks.update_one({"_id": task_idx}, {"$set": {"flow": flow}})
    return {"ok": True}
