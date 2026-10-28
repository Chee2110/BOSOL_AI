import os
import io
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.db.database import get_db, init_db
from app.db.models import AIRequest, UserConsent
from app.pipeline.gemini_adapter import (
    GeminiRescueAdapter,
    CircuitState,
    CircuitBreakerException,
)

class TestGeminiAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = next(get_db())
        self.adapter = GeminiRescueAdapter()

    def tearDown(self):
        self.db.close()

    def test_01_circuit_breaker_logic(self):
        """Kiểm tra cơ chế ngắt mạch: 3 lần lỗi liên tiếp phải chuyển sang trạng thái OPEN"""
        adapter = GeminiRescueAdapter()
        self.assertEqual(adapter.state, CircuitState.CLOSED)
        self.assertEqual(adapter.failure_count, 0)

        # Mô phỏng lỗi 1 và 2
        adapter._record_failure("Lỗi giả lập mạng lần 1")
        self.assertEqual(adapter.state, CircuitState.CLOSED)
        self.assertEqual(adapter.failure_count, 1)

        adapter._record_failure("Lỗi giả lập mạng lần 2")
        self.assertEqual(adapter.state, CircuitState.CLOSED)
        self.assertEqual(adapter.failure_count, 2)

        # Lỗi lần 3 -> Đạt ngưỡng max_failures (3) -> OPEN
        adapter._record_failure("Lỗi giả lập mạng lần 3")
        self.assertEqual(adapter.state, CircuitState.OPEN)
        self.assertEqual(adapter.failure_count, 3)

        # Khi đang OPEN, gọi hàm phải ném CircuitBreakerException
        with self.assertRaises(CircuitBreakerException):
            adapter._check_circuit_state()

        # Khi gọi _record_success -> Quay lại CLOSED
        adapter._record_success()
        self.assertEqual(adapter.state, CircuitState.CLOSED)
        self.assertEqual(adapter.failure_count, 0)

    def test_02_user_consent_guard(self):
        """Kiểm tra chặn gọi Cloud nếu kỹ sư chưa cấp phép (User Consent)"""
        adapter = GeminiRescueAdapter()
        test_user = "engineer_test_unconsented"

        # Đảm bảo không có consent
        has_consent = adapter.verify_user_consent(self.db, user_id=test_user)
        self.assertFalse(has_consent)

        # Cố tình gọi cứu viện khi chưa có consent -> Phải ném ngoại lệ PermissionError
        dummy_img = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        with self.assertRaises(PermissionError):
            adapter.rescue_crop_image(
                image_bytes=dummy_img,
                db=self.db,
                user_id=test_user,
                force_bypass_consent=False
            )

        # Bây giờ cấp User Consent hợp lệ trong CSDL
        consent = UserConsent(
            user_id=test_user,
            consent_given=True,
            scope="gemini_rescue_crop",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8)
        )
        self.db.add(consent)
        self.db.commit()

        # Kiểm tra lại: lúc này phải xác nhận có consent
        has_consent_after = adapter.verify_user_consent(self.db, user_id=test_user)
        self.assertTrue(has_consent_after)

    def test_03_budget_guard(self):
        """Kiểm tra chặn gọi Cloud khi ngân sách trong ngày vượt quá trần quy định (MAX_DAILY_AI_COST_USD)"""
        adapter = GeminiRescueAdapter()
        
        # Thêm 1 bản ghi AIRequest với chi phí giả lập $2.50 (> $2.00)
        over_budget_req = AIRequest(
            model_id="gemini-test",
            prompt_tokens=10000,
            candidates_tokens=10000,
            total_tokens=20000,
            cost_usd=2.50,
            latency_ms=500,
            circuit_state=CircuitState.CLOSED
        )
        self.db.add(over_budget_req)
        self.db.commit()

        is_allowed, total_spent = adapter.check_daily_budget(self.db)
        self.assertFalse(is_allowed)
        self.assertGreaterEqual(total_spent, 2.0)

        # Dọn dẹp bản ghi test để không ảnh hưởng môi trường
        self.db.delete(over_budget_req)
        self.db.commit()

    def test_04_live_multimodal_gemini_rescue(self):
        """
        Kiểm tra thực tế với ảnh vẽ chữ số kỹ thuật:
        Tạo ảnh crop chứa chữ 'Ø25 ± 0.05' và gửi tới Gemini rescue adapter.
        """
        # 1. Tạo ảnh test bằng PIL
        img = Image.new("RGB", (200, 60), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((15, 18), "O25 +- 0.05", fill=(0, 0, 0))
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        # 2. Gọi adapter với force_bypass_consent=True để kiểm tra chức năng cứu viện
        adapter = GeminiRescueAdapter()
        result = adapter.rescue_crop_image(
            image_bytes=image_bytes,
            mime_type="image/png",
            prompt_instruction="Đọc chính xác chuỗi chữ/số trong ảnh bản vẽ kỹ thuật này. Trả về JSON: {\"text\": \"...\", \"confidence\": 0.95}",
            force_bypass_consent=True,
            db=self.db
        )

        print("\n--- KẾT QUẢ CỨU VIỆN ĐA PHƯƠNG THỨC TỪ GEMINI ---")
        print(f"Success: {result['success']}")
        print(f"Latency: {result['latency_ms']} ms")
        print(f"Cost: ${result.get('cost_usd', 0.0):.6f}")
        print(f"Response: {result.get('text')}")
        print("-------------------------------------------------")

        self.assertTrue(result["success"])
        self.assertIn("text", result)
        self.assertGreater(result["latency_ms"], 0)
        self.assertEqual(result["fallback_to_local_ocr"], False)

if __name__ == "__main__":
    unittest.main()
