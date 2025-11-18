
https://github.com/user-attachments/assets/6ca85b0c-8890-41b1-b77b-aeb8769faba0


# PIA_Python 역할

백엔드 서버 main.py 및 흐름도 변환 알고리즘 flowchart_build_online.py로 구성되어 있다.

'흐름표에서 불러오기' : DB의 흐름표 정보로 흐름도 정보를 변환하여 저장하고 흐름도를 불러온다.

'저장' 클릭 : 현재 화면의 흐름도 정보를 DB에 업데이트한다.

'불러오기' : DB에 저장된 흐름도 정보로 흐름도를 불러온다.

우측 상단 '사진으로 다운로드(.png)' : S3 bucket에 사진을 저장하고, 사용자 PC에 다운로드 한 뒤 S3 bucket에서 삭제한다.

우측 상단 '결과보고서에 포함' : S3 bucket에 사진을 저장한다.

우측 상단 '포함 취소' : S3 bucket에서 사진을 삭제한다.

# .env 파일 제작 방법

MONGO_URI=mongodb+srv://{접속주소}

MONGO_DB=epia

AWS_ACCESS_KEY_ID={S3버킷 ID}

AWS_SECRET_ACCESS_KEY={S3버킷 패스워드}

AWS_S3_BUCKET_NAME=epia

AWS_REGION=ap-southeast-2

# 직접 실행하기 (venv는 선택사항)
   
P1A_Python> python -m venv .venv

P1A_Python> pip install -r requirements.txt

P1A_Python> uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 도커로 실행하기
1. 도커 빌드
   
P1A_Python> docker build -t p1a-python-backend:latest .

2. 도커 실행 (로컬 .env 사용)

docker run -d --name p1a_py_backend \
  --env-file ./.env \
  -p 8000:8000 \
  p1a-python-backend:latest
