import os
import uvicorn
from app.main import app

if __name__ == "__main__":
    # GCP Cloud Run은 PORT 환경변수를 주입합니다. 기본값은 8080입니다.
    port = int(os.getenv("PORT", 8080))
    # app/main.py 안의 FastAPI 객체(app)를 로드하여 uvicorn 실행
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
