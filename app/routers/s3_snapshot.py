# /api/s3/flow-snapshot
from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from ..core.db import get_company
from ..core.s3 import s3, BUCKET_NAME, sanitize_filename

router = APIRouter(
    prefix="/api",
    tags=["flow-snapshot"],
)

# (결과보고서에 포함)
@router.post("/s3/flow-snapshot")
async def upload_flow_snapshot(
    company_id: str = Query(...),
    task_id: str = Query(...),
    file: UploadFile = File(...),
):
    try:
        comp = await get_company(company_id)
        task_name = "flow"
        for t in comp.get("processingTasks", []):
            cand = t.get("id") or t.get("_id") or t.get("task_id")
            if (cand is not None) and (str(cand) == str(task_id)):
                task_name = t.get("taskName") or t.get("name") or "flow"
                break

        fname = sanitize_filename(task_name, default="flow") + ".png"
        key = f"{company_id}/개인정보흐름도/{task_id}/{fname}"

        content = await file.read()
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType="image/png",
            CacheControl="no-cache",
        )
        return {"ok": True, "key": key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"s3 upload failed: {e}")

# (포함 취소)
@router.delete("/s3/flow-snapshot")
async def delete_flow_snapshot(
    company_id: str = Query(...),
    task_id: str = Query(...),
):
    try:
        comp = await get_company(company_id)
        task_name = "flow"
        for t in comp.get("processingTasks", []):
            cand = t.get("id") or t.get("_id") or t.get("task_id")
            if (cand is not None) and (str(cand) == str(task_id)):
                task_name = t.get("taskName") or t.get("name") or "flow"
                break

        fname = sanitize_filename(task_name, default="flow") + ".png"
        key = f"{company_id}/개인정보흐름도/{task_id}/{fname}"

        s3.delete_object(Bucket=BUCKET_NAME, Key=key)
        return {"ok": True, "deleted_key": key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"s3 delete failed: {e}")