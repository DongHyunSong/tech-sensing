import os
import logging
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("PhilTVTech.Config")

# 로컬 .env 파일이 존재하는 경우 로드
load_dotenv()

class Config:
    # 텔레그램 설정
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # 구글 제미나이 설정
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
    # 데이터베이스 설정 (비워둘 시 Local JSON 데이터베이스로 폴백)
    FIRESTORE_PROJECT_ID = os.getenv("FIRESTORE_PROJECT_ID", "")
    
    # 보안 설정
    CRON_SECRET_TOKEN = os.getenv("CRON_SECRET_TOKEN", "PhilTVTechCronSecret2026")
    WEB_PASSWORD = os.getenv("WEB_PASSWORD", "admin1234")
    
    # 앱 실행 설정
    PORT = int(os.getenv("PORT", "8080"))
    
    @classmethod
    def validate(cls):
        """환경 변수 유효성 검사 및 로그 출력"""
        logger.info("필리핀 TV 기술 센싱 서비스 환경 변수 유효성 검사를 시작합니다.")
        
        has_errors = False
        
        if not cls.TELEGRAM_BOT_TOKEN:
            logger.warning("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다. 텔레그램 봇 연동이 작동하지 않습니다.")
            has_errors = True
        else:
            logger.info("TELEGRAM_BOT_TOKEN: 설정됨 (확인)")
            
        if not cls.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY가 설정되지 않았습니다. AI 인사이트 분석 엔진이 작동하지 않습니다.")
            has_errors = True
        else:
            logger.info("GEMINI_API_KEY: 설정됨 (확인)")
            
        if not cls.FIRESTORE_PROJECT_ID:
            logger.info("FIRESTORE_PROJECT_ID가 설정되지 않았습니다. -> 로컬 JSON 데이터베이스 모드로 실행합니다.")
        else:
            logger.info(f"FIRESTORE_PROJECT_ID: '{cls.FIRESTORE_PROJECT_ID}' -> GCP Firestore 모드로 실행합니다.")
            
        if cls.CRON_SECRET_TOKEN == "PhilTVTechCronSecret2026":
            logger.warning("기본 CRON_SECRET_TOKEN을 사용 중입니다. 프로덕션 환경에서는 변경을 권장합니다.")
            
        return not has_errors

# 싱글톤 설정 객체 생성
config = Config()
