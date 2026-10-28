import os
import time
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
import requests
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import settings
from app.db.models import AIRequest, UserConsent

logger = logging.getLogger("bosol.gemini_adapter")

class CircuitState:
    CLOSED = "CLOSED"      # Bình thường, cho phép gọi Cloud
    OPEN = "OPEN"          # Đang ngắt mạch, chặn gọi Cloud
    HALF_OPEN = "HALF_OPEN"# Đang thử nghiệm phục hồi


class CircuitBreakerException(Exception):
    """Ngoại lệ ném ra khi Circuit Breaker đang OPEN hoặc ngân sách vượt ngưỡng"""
    pass


class GeminiRescueAdapter:
    """
    TẦNG CỨU VIỆN CLOUD AI (Module 3.1 & 3.2):
    - Đảm bảo Local-First: Chỉ kích hoạt khi Local OCR thất bại / độ tin cậy thấp.
    - An toàn tài chính: Kiểm soát ngân sách hàng ngày < 2.0 USD (~50.000 VNĐ).
    - Bảo vệ hệ thống: Circuit Breaker 3 trạng thái chống treo máy khi mất mạng.
    - Bảo mật dữ liệu: Bắt buộc kỹ sư ký chấp thuận (User Consent) trước khi gửi ảnh crop.
    """

    # Giá niêm yết Google Gemini 2.5 Flash Lite (USD / 1.000.000 tokens)
    COST_PER_M_INPUT_TOKENS = 0.075
    COST_PER_M_OUTPUT_TOKENS = 0.300

    def __init__(self):
        self.state: str = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: Optional[float] = None
        self.max_failures: int = settings.CIRCUIT_BREAKER_FAILURES
        self.recovery_timeout_sec: float = float(settings.CIRCUIT_BREAKER_RECOVERY_SEC)
        self.timeout_sec: float = settings.GEMINI_TIMEOUT_SEC
        self.model_id: str = settings.GEMINI_MODEL_ID
        self.api_key: str = settings.GEMINI_API_KEY

    def _check_circuit_state(self) -> None:
        """Kiểm tra và chuyển đổi trạng thái Circuit Breaker"""
        now = time.time()
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (now - self.last_failure_time >= self.recovery_timeout_sec):
                logger.info("[CircuitBreaker] Hết thời gian cách ly (cooldown). Chuyển sang HALF_OPEN để thử kết nối lại.")
                self.state = CircuitState.HALF_OPEN
            else:
                remaining = int(self.recovery_timeout_sec - (now - (self.last_failure_time or now)))
                raise CircuitBreakerException(
                    f"Circuit Breaker đang OPEN (ngắt mạch). Tự động fallback về OCR máy cục bộ. Cooldown còn: {remaining}s"
                )

    def _record_success(self) -> None:
        """Ghi nhận yêu cầu thành công -> Đặt lại trạng thái CLOSED"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _record_failure(self, error_msg: str) -> None:
        """Ghi nhận lỗi -> Đếm lỗi và ngắt mạch nếu vượt ngưỡng"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.warning(f"[CircuitBreaker] Lỗi lần {self.failure_count}/{self.max_failures}: {error_msg}")
        if self.failure_count >= self.max_failures:
            self.state = CircuitState.OPEN
            logger.error(f"[CircuitBreaker] ĐÃ CHUYỂN SANG TRẠNG THÁI OPEN! Chặn toàn bộ cuộc gọi Cloud trong {self.recovery_timeout_sec}s.")

    def check_daily_budget(self, db: Session) -> Tuple[bool, float]:
        """
        Kiểm tra tổng chi tiêu Gemini trong ngày hiện tại.
        Trả về: (cho_phép_chạy: bool, tổng_chi_tiêu_hôm_nay: float)
        """
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            total_cost = db.query(func.sum(AIRequest.cost_usd)).filter(
                AIRequest.created_at >= today_start
            ).scalar() or 0.0

            if total_cost >= settings.MAX_DAILY_AI_COST_USD:
                logger.warning(
                    f"[BudgetGuard] ĐÃ VƯỢT HẠN MỨC NGÀY! Chi tiêu hôm nay: ${total_cost:.4f} / ${settings.MAX_DAILY_AI_COST_USD:.2f}"
                )
                return False, float(total_cost)
            return True, float(total_cost)
        except Exception as e:
            logger.error(f"[BudgetGuard] Lỗi kiểm tra chi phí CSDL: {e}")
            # Nếu CSDL lỗi, mặc định bảo vệ ngân sách (cho phép nếu là môi trường dev nhưng ghi log)
            return True, 0.0

    def verify_user_consent(self, db: Session, user_id: str = "default_engineer") -> bool:
        """
        Xác nhận kỹ sư đã đồng ý (Consent) gửi dữ liệu ảnh crop lên Cloud.
        """
        try:
            now = datetime.now(timezone.utc)
            consent = db.query(UserConsent).filter(
                UserConsent.user_id == user_id,
                UserConsent.consent_given == True,
                (UserConsent.expires_at == None) | (UserConsent.expires_at > now)
            ).first()
            return consent is not None
        except Exception as e:
            logger.error(f"[ConsentGuard] Lỗi kiểm tra User Consent: {e}")
            return False

    def rescue_crop_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/webp",
        prompt_instruction: str = "Đọc chính xác chữ số, ký tự dung sai trong ảnh crop bản vẽ kỹ thuật này. Trả về đúng định dạng JSON: {\"text\": \"...\", \"confidence\": 0.95}",
        job_id: Optional[str] = None,
        db: Optional[Session] = None,
        user_id: str = "default_engineer",
        force_bypass_consent: bool = False
    ) -> Dict[str, Any]:
        """
        Thực hiện cứu viện ô ảnh mờ (multimodal):
        - Đầu vào: byte ảnh crop (WebP/PNG)
        - Trả về: Dictionary kết quả {'success': bool, 'text': str, 'confidence': float, 'fallback': bool, ...}
        """
        # 1. Kiểm tra Circuit Breaker
        self._check_circuit_state()

        # 2. Kiểm tra Ngân sách Hàng ngày (nếu có kết nối DB)
        if db:
            budget_ok, current_spent = self.check_daily_budget(db)
            if not budget_ok:
                raise CircuitBreakerException(
                    f"Ngân sách Cloud AI hôm nay đã chạm trần (${current_spent:.4f} >= ${settings.MAX_DAILY_AI_COST_USD:.2f}). Chuyển sang OCR cục bộ 0 VNĐ!"
                )

        # 3. Kiểm tra User Consent
        if not force_bypass_consent:
            has_consent = self.verify_user_consent(db, user_id) if db else False
            if not has_consent:
                raise PermissionError(
                    f"Chưa có User Consent (Sự đồng ý của Kỹ sư) để gửi ảnh lên Cloud. Từ chối thực hiện gọi API cứu viện."
                )

        # 4. Chuẩn bị payload multimodal cho Gemini REST API
        start_time = time.time()
        base64_img = base64.b64encode(image_bytes).decode("utf-8")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_id}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_instruction},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64_img
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 300,
                "responseMimeType": "application/json"
            }
        }

        # 5. Gửi HTTP Request kèm retry ngắn cho 503/429
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout_sec)
                latency_ms = int((time.time() - start_time) * 1000)

                # Nếu bị 503 (High demand) hoặc 429 (Rate limit), chờ nhẹ rồi thử lại
                if resp.status_code in (503, 429) and attempt < max_retries:
                    wait_sec = 1.5 * (attempt + 1)
                    logger.warning(f"[GeminiAdapter] Gặp HTTP {resp.status_code}. Tự động thử lại lần {attempt + 1} sau {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue

                if resp.status_code != 200:
                    self._record_failure(f"Gemini API returned status {resp.status_code}: {resp.text[:120]}")
                    return {
                        "success": False,
                        "fallback_to_local_ocr": True,
                        "reason": f"API_ERROR_{resp.status_code}",
                        "latency_ms": latency_ms
                    }

                # Phản hồi thành công
                break
            except (requests.Timeout, requests.ConnectionError) as req_err:
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                latency_ms = int((time.time() - start_time) * 1000)
                self._record_failure(f"Network timeout / ConnectionError: {req_err}")
                return {
                    "success": False,
                    "fallback_to_local_ocr": True,
                    "reason": "NETWORK_TIMEOUT_FALLBACK",
                    "latency_ms": latency_ms
                }
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                self._record_failure(f"Unexpected error: {e}")
                return {
                    "success": False,
                    "fallback_to_local_ocr": True,
                    "reason": str(e),
                    "latency_ms": latency_ms
                }

        # 6. Xử lý phản hồi thành công
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            self._record_failure("Empty candidates from Gemini")
            return {
                "success": False,
                "fallback_to_local_ocr": True,
                "reason": "EMPTY_RESPONSE",
                "latency_ms": latency_ms
            }

        result_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        candidates_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", 0)

        # Tính toán chi phí thực tế cho lượt gọi này
        cost_usd = (
            (prompt_tokens / 1_000_000) * self.COST_PER_M_INPUT_TOKENS +
            (candidates_tokens / 1_000_000) * self.COST_PER_M_OUTPUT_TOKENS
        )

        # Cập nhật trạng thái thành công cho Circuit Breaker
        self._record_success()

        # 7. Ghi nhật ký vào CSDL bảng ai_requests (Audit Trail)
        if db:
            try:
                ai_req = AIRequest(
                    job_id=job_id,
                    model_id=self.model_id,
                    prompt_tokens=prompt_tokens,
                    candidates_tokens=candidates_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    circuit_state=self.state
                )
                db.add(ai_req)
                db.commit()
            except Exception as db_err:
                logger.error(f"[AuditTrail] Không thể lưu bản ghi ai_requests: {db_err}")
                db.rollback()

        return {
            "success": True,
            "text": result_text,
            "prompt_tokens": prompt_tokens,
            "candidates_tokens": candidates_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "circuit_state": self.state,
            "fallback_to_local_ocr": False
        }

# Singleton instance
gemini_rescue_adapter = GeminiRescueAdapter()
