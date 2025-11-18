# 베이스 이미지 (python 3.11 slim)
FROM python:3.11-slim

# --- 기본 설정 ---
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --- 시스템 패키지 (필요 시 추가) ---
# build-essential은 일부 라이브러리가 C 컴파일을 요구할 수 있어서 미리 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# --- 작업 디렉토리 ---
WORKDIR /app

# --- 의존성 먼저 복사 & 설치 (레이어 캐시 최적화) ---
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- 애플리케이션 소스 복사 ---
COPY app ./app

# --- (선택) 비루트 사용자 사용 ---
RUN useradd -m appuser
USER appuser

# --- 포트 노출 ---
EXPOSE 8000

# --- Uvicorn 실행 ---
# 프로덕션에서는 workers 늘려도 됨: --workers 2~4
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]