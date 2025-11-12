https://github.com/user-attachments/assets/03a02da6-ba43-4920-9a5f-c743d6262fa8

# PIA_Python 역할

백엔드 서버 main.py 및 흐름도 변환 알고리즘 flowchart_build_online.py로 구성되어 있다.

EPIA 처리 업무별로, '흐름표에서 불러오기' 클릭 시 DB의 흐름표 정보로 흐름도 정보를 변환하여 저장하고 흐름도를 불러온다.

'저장' 클릭 시 현재 화면의 흐름도 정보를 DB에 업데이트한다.

'불러오기' 클릭 시 DB에 저장된 흐름도 정보로 흐름도를 불러온다.

# P1A_Python 실행 방법

1. requirements.txt 제작하기

fastapi==0.115.5

uvicorn[standard]==0.32.0

motor==3.6.0

pydantic==2.9.2

python-dotenv==1.0.1

2. .env 파일 제작하기

MONGO_URI=mongodb+srv://접속주소

MONGO_DB=epia

3. 서버 실행 (venv는 선택사항)
   
P1A_Python> python -m venv .venv

P1A_Python> pip install -r requirements.txt

P1A_Python> uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 도커 실행 방법
1. Dockerfile 제작하기
   
#Dockerfile

FROM python:3.11-slim

#기본 설정

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
    
#시스템 패키지 (필요 시 추가)

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*
  
#작업 디렉토리

WORKDIR /app

#의존성 먼저 복사/설치 (레이어 캐시 최적화)

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#소스 복사

COPY app ./app

#(선택) 비루트 사용자

RUN useradd -m appuser
USER appuser
EXPOSE 8000

#uvicorn 실행 (프로덕션에서는 --workers=2~4 권장)

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

2. .dockerignore 제작하기

3. docker 빌드
   
P1A_Python> docker build -t p1a-python-backend:latest .

4. 실행 (로컬 .env 사용)

docker run -d --name p1a_py_backend \
  --env-file ./.env \
  -p 8000:8000 \
  p1a-python-backend:latest
