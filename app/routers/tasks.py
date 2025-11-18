# /api/tasks
from fastapi import APIRouter, Query

from ..core.db import get_company

router = APIRouter(
    prefix="/api",
    tags=["tasks"],
)

# (업무리스트 조회 및 선택) companies 컬렉션의 processingTasks에서 id와 taskName만 뽑아 반환
@router.get("/tasks")
async def list_tasks(
    company_id: str = Query(...),
):
    comp = await get_company(company_id)
    rows = []
    for t in comp.get("processingTasks", []):
        raw_id = t.get("id") or t.get("_id") or t.get("task_id")
        try:
            tid = str(raw_id) if raw_id is not None else ""
        except Exception:
            tid = ""
        name = t.get("taskName") or t.get("name") or "(무제)"
        rows.append({"id": tid, "taskName": name})
    return rows