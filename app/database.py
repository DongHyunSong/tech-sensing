import os
import json
import logging
from datetime import datetime, timedelta, timezone
from app.config import config

logger = logging.getLogger("PhilTVTech.Database")

# 로컬 저장용 디렉토리 설정
LOCAL_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

class BaseDatabase:
    """데이터베이스 공통 인터페이스 정의"""
    def save_sensing_note(self, text: str, source: str, author: str) -> bool:
        raise NotImplementedError
        
    def get_sensing_notes_since(self, days: int = 7) -> list:
        raise NotImplementedError
        
    def save_report(self, report_text: str) -> bool:
        raise NotImplementedError
        
    def get_recent_reports(self, limit: int = 5) -> list:
        raise NotImplementedError
        
    def add_subscriber(self, chat_id: str) -> bool:
        raise NotImplementedError
        
    def get_subscribers(self) -> list:
        raise NotImplementedError
        
    def remove_subscriber(self, chat_id: str) -> bool:
        raise NotImplementedError


class LocalJsonDatabase(BaseDatabase):
    """로컬 개발 환경용 JSON 파일 데이터베이스"""
    def __init__(self):
        os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
        self.notes_file = os.path.join(LOCAL_DATA_DIR, "notes.json")
        self.reports_file = os.path.join(LOCAL_DATA_DIR, "reports.json")
        self.subscribers_file = os.path.join(LOCAL_DATA_DIR, "subscribers.json")
        
        # 파일 초기화
        for f in [self.notes_file, self.reports_file]:
            if not os.path.exists(f):
                with open(f, "w", encoding="utf-8") as file:
                    json.dump([], file, ensure_ascii=False, indent=2)
                    
        if not os.path.exists(self.subscribers_file):
            with open(self.subscribers_file, "w", encoding="utf-8") as file:
                # 기본 TELEGRAM_CHAT_ID가 환경변수에 있다면 기본으로 구독 추가
                initial_subs = []
                if config.TELEGRAM_CHAT_ID:
                    initial_subs.append(str(config.TELEGRAM_CHAT_ID))
                json.dump(initial_subs, file, ensure_ascii=False, indent=2)

    def _read_file(self, filepath: str) -> list:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"파일 읽기 오류 ({filepath}): {str(e)}")
            return []

    def _write_file(self, filepath: str, data: list) -> bool:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"파일 쓰기 오류 ({filepath}): {str(e)}")
            return False

    def save_sensing_note(self, text: str, source: str, author: str) -> bool:
        notes = self._read_file(self.notes_file)
        new_note = {
            "text": text,
            "source": source,
            "author": author,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        notes.append(new_note)
        logger.info(f"로컬 센싱 노트 저장 완료: {text[:20]}...")
        return self._write_file(self.notes_file, notes)

    def get_sensing_notes_since(self, days: int = 7) -> list:
        notes = self._read_file(self.notes_file)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        filtered = []
        for n in notes:
            try:
                note_time = datetime.fromisoformat(n["timestamp"])
                if note_time >= cutoff:
                    filtered.append(n)
            except Exception:
                # 타임스탬프 파싱 실패 시 예외 처리
                filtered.append(n)
                
        return filtered

    def save_report(self, report_text: str) -> bool:
        reports = self._read_file(self.reports_file)
        new_report = {
            "report_text": report_text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        reports.append(new_report)
        logger.info("로컬 인사이트 리포트 저장 완료.")
        return self._write_file(self.reports_file, reports)

    def get_recent_reports(self, limit: int = 5) -> list:
        reports = self._read_file(self.reports_file)
        # 타임스탬프 기준으로 정렬 후 최근 순으로 반환
        try:
            reports.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        except Exception as e:
            logger.error(f"로컬 리포트 정렬 실패: {str(e)}")
        return reports[:limit]

    def add_subscriber(self, chat_id: str) -> bool:
        subs = self._read_file(self.subscribers_file)
        chat_id_str = str(chat_id)
        if chat_id_str not in subs:
            subs.append(chat_id_str)
            logger.info(f"로컬 구독자 추가: {chat_id_str}")
            return self._write_file(self.subscribers_file, subs)
        return True

    def get_subscribers(self) -> list:
        return self._read_file(self.subscribers_file)

    def remove_subscriber(self, chat_id: str) -> bool:
        subs = self._read_file(self.subscribers_file)
        chat_id_str = str(chat_id)
        if chat_id_str in subs:
            subs.remove(chat_id_str)
            logger.info(f"로컬 구독자 제거: {chat_id_str}")
            return self._write_file(self.subscribers_file, subs)
        return True


class FirestoreDatabase(BaseDatabase):
    """GCP 배포용 Firestore 데이터베이스"""
    def __init__(self):
        try:
            from google.cloud import firestore
            # 프로젝트 ID를 명시적으로 주입하거나 기본 ADC(Application Default Credentials)를 사용
            if config.FIRESTORE_PROJECT_ID:
                self.db = firestore.Client(project=config.FIRESTORE_PROJECT_ID)
            else:
                self.db = firestore.Client()
            logger.info("GCP Firestore 클라이언트 초기화 완료.")
        except Exception as e:
            logger.error(f"Firestore 초기화 실패, 로컬 JSON 모드로 폴백을 제안합니다. 에러: {str(e)}")
            raise e

    def save_sensing_note(self, text: str, source: str, author: str) -> bool:
        try:
            doc_ref = self.db.collection("raw_sensing_notes").document()
            doc_ref.set({
                "text": text,
                "source": source,
                "author": author,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            logger.info("Firestore 센싱 노트 저장 완료.")
            return True
        except Exception as e:
            logger.error(f"Firestore 센싱 노트 저장 실패: {str(e)}")
            return False

    def get_sensing_notes_since(self, days: int = 7) -> list:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            notes_ref = self.db.collection("raw_sensing_notes")
            query = notes_ref.where("timestamp", ">=", cutoff).order_by("timestamp", direction=firestore.Query.DESCENDING)
            
            results = []
            for doc in query.stream():
                data = doc.to_dict()
                # Firestore Timestamp를 ISO format 스트링으로 변환
                if "timestamp" in data and data["timestamp"]:
                    data["timestamp"] = data["timestamp"].isoformat()
                results.append(data)
            return results
        except Exception as e:
            logger.error(f"Firestore 센싱 노트 조회 실패: {str(e)}")
            return []

    def save_report(self, report_text: str) -> bool:
        try:
            doc_ref = self.db.collection("sent_reports").document()
            doc_ref.set({
                "report_text": report_text,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            logger.info("Firestore 인사이트 리포트 저장 완료.")
            return True
        except Exception as e:
            logger.error(f"Firestore 리포트 저장 실패: {str(e)}")
            return False

    def get_recent_reports(self, limit: int = 5) -> list:
        try:
            reports_ref = self.db.collection("sent_reports")
            query = reports_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
            
            results = []
            for doc in query.stream():
                data = doc.to_dict()
                if "timestamp" in data and data["timestamp"]:
                    data["timestamp"] = data["timestamp"].isoformat()
                results.append(data)
            return results
        except Exception as e:
            logger.error(f"Firestore 리포트 조회 실패: {str(e)}")
            return []

    def add_subscriber(self, chat_id: str) -> bool:
        try:
            chat_id_str = str(chat_id)
            doc_ref = self.db.collection("subscribers").document(chat_id_str)
            doc_ref.set({
                "chat_id": chat_id_str,
                "subscribed_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Firestore 구독자 추가: {chat_id_str}")
            return True
        except Exception as e:
            logger.error(f"Firestore 구독자 추가 실패: {str(e)}")
            return False

    def get_subscribers(self) -> list:
        try:
            subs_ref = self.db.collection("subscribers")
            results = []
            for doc in subs_ref.stream():
                data = doc.to_dict()
                results.append(data.get("chat_id"))
            
            # 기본 TELEGRAM_CHAT_ID가 구독 목록에 없으면 자동으로 포함
            if config.TELEGRAM_CHAT_ID and str(config.TELEGRAM_CHAT_ID) not in results:
                results.append(str(config.TELEGRAM_CHAT_ID))
                
            return results
        except Exception as e:
            logger.error(f"Firestore 구독자 조회 실패: {str(e)}")
            # 실패 시 기본 TELEGRAM_CHAT_ID라도 반환하도록 폴백
            if config.TELEGRAM_CHAT_ID:
                return [str(config.TELEGRAM_CHAT_ID)]
            return []

    def remove_subscriber(self, chat_id: str) -> bool:
        try:
            chat_id_str = str(chat_id)
            doc_ref = self.db.collection("subscribers").document(chat_id_str)
            doc_ref.delete()
            logger.info(f"Firestore 구독자 제거: {chat_id_str}")
            return True
        except Exception as e:
            logger.error(f"Firestore 구독자 제거 실패: {str(e)}")
            return False


# 데이터베이스 인스턴스 팩토리 및 싱글톤 로더
def initialize_database() -> BaseDatabase:
    if config.FIRESTORE_PROJECT_ID:
        try:
            return FirestoreDatabase()
        except Exception:
            logger.warning("GCP Firestore 초기화에 실패하여 Local JSON 데이터베이스 모드로 강제 폴백합니다.")
            return LocalJsonDatabase()
    else:
        logger.info("Firestore 설정이 없으므로 Local JSON 데이터베이스를 활성화합니다.")
        return LocalJsonDatabase()

# 전역 데이터베이스 인스턴스
db = initialize_database()
