from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import flow, tasks, s3_snapshot, ai_flow  # 각 router 모듈

app = FastAPI(redirect_slashes=False)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# router 등록 (각 router에서 prefix="/api"를 미리 걸어둘 예정)
app.include_router(flow.router)
app.include_router(tasks.router)
app.include_router(s3_snapshot.router)
app.include_router(ai_flow.router)
