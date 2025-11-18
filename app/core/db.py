# Mongo 클라이언트 + helper
from typing import Any, Dict, Tuple
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId, errors as bson_errors
from fastapi import HTTPException

from .config import MONGO_URI

# Mongo 클라이언트/컬렉션
client = AsyncIOMotorClient(MONGO_URI)
db = client["epia"]
companies = db.get_collection("companies")

# companies에서 company + processingTasks만 가져오는 공통 헬퍼
async def get_company(company_id: str):
    try:
        oid = ObjectId(company_id)
    except bson_errors.InvalidId:
        raise HTTPException(status_code=400, detail="invalid company_id")
    comp = await companies.find_one({"_id": oid}, projection={"processingTasks": 1})
    if not comp:
        raise HTTPException(status_code=404, detail="company not found")
    return comp

# company processingTasks의 index, flow dict, sheets dict를 반환하는 헬퍼
async def get_flow_and_sheets_by_task_id(
    company_id: str,
    task_id: str,
) -> Tuple[Dict[str, Any], int, Dict[str, Any], Dict[str, Any]]:
    """
    - company 문서
    - processingTasks의 index
    - flow dict
    - sheets dict
    를 리턴.
    """
    comp = await get_company(company_id)
    pts = comp.get("processingTasks", [])

    # task_id를 ObjectId로도 시도
    try:
        task_oid = ObjectId(task_id)
    except Exception:
        task_oid = None

    for i, t in enumerate(pts):
        cand = t.get("id") or t.get("_id") or t.get("task_id")
        if cand is None:
            continue
        if (task_oid is not None and cand == task_oid) or str(cand) == str(task_id):
            flow = t.get("flow") or {}
            sheets = flow.get("sheets") or {}
            return comp, i, flow, sheets

    raise HTTPException(status_code=404, detail=f"task_id {task_id} not found")
