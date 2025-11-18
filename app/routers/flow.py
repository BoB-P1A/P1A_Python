# /api/combined, /api/derived, /api/build, /api/sheets
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Body
from datetime import datetime

from ..core.db import companies, get_flow_and_sheets_by_task_id
from ..flowchart_build_online import build_from_sheets

router = APIRouter(
    prefix="/api",
    tags=["flow"],
)

# (흐름표에서 불러오기) DB sheets 정보를 기반으로 derived를 생성하고 저장한 후 불러오기
@router.post("/build")
async def post_build(
    company_id: str = Query(...),
    task_id: str = Query(...),
):
    comp, zi, flow, sheets = await get_flow_and_sheets_by_task_id(company_id, task_id)
    has_rows = any(
        len(sheets.get(k, []))
        for k in ("collect", "retain", "use", "provide", "discard")
    )
    if not has_rows:
        raise HTTPException(status_code=400, detail="no sheets to build")

    derived = build_from_sheets(sheets)
    now = datetime.utcnow()
    await companies.update_one(
        {"_id": comp["_id"]},
        {
            "$set": {
                f"processingTasks.{zi}.flow.derived": derived,
                f"processingTasks.{zi}.flow.updated_at": now,
            }
        },
    )
    return {"ok": True, "updated_at": now.isoformat()}

# (아이콘 없음) DB sheet에 정보 저장
@router.put("/sheets")
async def put_sheets(
    company_id: str = Query(...),
    task_id: str = Query(...),
    payload: Dict[str, Any] = Body(...),
):
    comp, zi, flow, _ = await get_flow_and_sheets_by_task_id(company_id, task_id)

    title = payload.get("title") or flow.get("title") or ""
    sheets = payload.get("sheets") or {}
    now = datetime.utcnow()

    await companies.update_one(
        {"_id": comp["_id"]},
        {
            "$set": {
                f"processingTasks.{zi}.flow.title": title,
                f"processingTasks.{zi}.flow.sheets": sheets,
                f"processingTasks.{zi}.flow.updated_at": now,
            }
        },
    )
    return {"ok": True}

# (저장) 현재 웹에 그려진 흐름도를 DB derived에 저장하기
@router.put("/derived")
async def put_derived(
    company_id: str = Query(...),
    task_id: str = Query(...),
    payload: Dict[str, Any] = Body(...),
):
    comp, zi, _, _ = await get_flow_and_sheets_by_task_id(company_id, task_id)
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="invalid payload")

    now = datetime.utcnow()
    await companies.update_one(
        {"_id": comp["_id"]},
        {
            "$set": {
                f"processingTasks.{zi}.flow.derived": payload,
                f"processingTasks.{zi}.flow.updated_at": now,
            }
        },
    )
    return {"ok": True, "updated_at": now.isoformat()}

# (불러오기) DB derived에 현재 저장된 흐름도 정보 가져오기
@router.get("/combined")
async def get_combined(
    company_id: str = Query(...),
    task_id: str = Query(...),
):
    _, _, flow, _ = await get_flow_and_sheets_by_task_id(company_id, task_id)
    derived = flow.get("derived")
    if not derived:
        raise HTTPException(status_code=404, detail="derived not built yet")
    return derived

