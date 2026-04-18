"""
LLM Client — 3 mode tự động:

  1. Groq API  (GROQ_API_KEY set)  → dùng khi deploy cloud, miễn phí
  2. Ollama    (đang chạy local)   → dùng khi dev local có Ollama
  3. Mock      (fallback)          → luôn hoạt động, không cần config

Ưu tiên: Groq > Ollama > Mock

Lấy Groq key miễn phí: https://console.groq.com
"""
import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")

SALES_SYSTEM_PROMPT = """Bạn là trợ lý tư vấn bán hàng chuyên nghiệp của cửa hàng TechShop.

Nhiệm vụ:
- Giúp khách hàng tìm sản phẩm phù hợp nhu cầu và ngân sách
- Tư vấn laptop, điện thoại, phụ kiện công nghệ
- Giải đáp thắc mắc về thông số kỹ thuật, giá cả, bảo hành
- Đề xuất sản phẩm thay thế khi cần

Sản phẩm nổi bật:
- MacBook Air M2 (2024): 28.990.000đ — chip M2, pin 18h, 256GB SSD
- Dell XPS 15: 35.500.000đ — màn 4K OLED, Core i9, RTX 4060
- iPhone 15 Pro: 27.990.000đ — chip A17 Pro, camera 48MP, titanium
- Samsung Galaxy S24 Ultra: 29.990.000đ — bút S Pen, zoom 100x, 200MP
- AirPods Pro 2: 6.490.000đ — ANC tốt nhất, chip H2
- Logitech MX Master 3S: 2.290.000đ — chuột văn phòng cao cấp

Phong cách:
- Thân thiện, chuyên nghiệp, ngắn gọn (3-5 câu mỗi lượt)
- Luôn hỏi thêm nhu cầu để tư vấn chính xác
- Trả lời bằng tiếng Việt
"""

MOCK_RESPONSES = [
    "Chào bạn! Tôi là trợ lý tư vấn TechShop. Bạn đang tìm kiếm sản phẩm gì hôm nay?",
    "Dựa trên nhu cầu của bạn, tôi gợi ý **MacBook Air M2** — hiệu năng tốt, pin 18h, giá 28.990.000đ. Bạn chủ yếu dùng để làm gì?",
    "**Dell XPS 15** là lựa chọn tuyệt vời cho đồ họa và lập trình với màn 4K OLED. Ngân sách của bạn khoảng bao nhiêu?",
    "Để tư vấn chính xác hơn, bạn có thể cho biết ngân sách dự kiến không? Dưới 20 triệu, 20-30 triệu, hay trên 30 triệu?",
    "**iPhone 15 Pro** có camera 48MP và chip A17 Pro mạnh nhất hiện tại, bảo hành 12 tháng chính hãng tại 27.990.000đ.",
    "**Samsung Galaxy S24 Ultra** nổi bật với bút S Pen và zoom quang học 100x — rất phù hợp cho người hay chụp ảnh sáng tạo.",
    "**AirPods Pro 2** là lựa chọn số 1 về chống ồn. Bạn đang dùng iPhone hay Android? Tôi sẽ tư vấn tai nghe phù hợp hơn.",
    "Chúng tôi có chính sách **trả góp 0% lãi suất** 12 tháng và bảo hành chính hãng. Bạn muốn xem thêm sản phẩm nào không?",
]

_ollama_available: bool | None = None  # None = not checked yet

_KEYWORD_MAP = [
    (["macbook", "m2", "mac", "apple laptop"], MOCK_RESPONSES[1]),
    (["dell", "xps", "windows laptop", "đồ họa", "gaming", "rtx"], MOCK_RESPONSES[2]),
    (["iphone", "ios", "apple phone"], MOCK_RESPONSES[4]),
    (["samsung", "android", "galaxy", "s24"], MOCK_RESPONSES[5]),
    (["airpod", "tai nghe", "earphone", "headphone"], MOCK_RESPONSES[6]),
    (["ngân sách", "budget", "giá", "bao nhiêu", "rẻ", "tiền"], MOCK_RESPONSES[3]),
    (["trả góp", "installment", "bảo hành", "warranty"], MOCK_RESPONSES[7]),
    (["chào", "hello", "hi", "xin chào"], MOCK_RESPONSES[0]),
]

def _mock_response(question: str) -> str:
    q = question.lower()
    for keywords, response in _KEYWORD_MAP:
        if any(kw in q for kw in keywords):
            return response
    return MOCK_RESPONSES[0]


def _call_groq(messages: list) -> str:
    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
    }).encode()

    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]


def _check_ollama() -> bool:
    global _ollama_available
    if _ollama_available is not None:
        return _ollama_available
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            _ollama_available = resp.status == 200
    except Exception:
        _ollama_available = False
    return _ollama_available


def _call_ollama(messages: list) -> str:
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 512},
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        return data["message"]["content"]


def ask(question: str, history: list | None = None) -> tuple[str, str]:
    """
    Gọi LLM theo thứ tự ưu tiên: Groq → Ollama → Mock.
    Returns: (answer, backend_name)
    """
    messages = [{"role": "system", "content": SALES_SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": question})

    # 1. Groq (cloud deployment)
    if GROQ_API_KEY:
        try:
            answer = _call_groq(messages)
            logger.info(f"LLM backend: groq/{GROQ_MODEL}")
            return answer, f"groq/{GROQ_MODEL}"
        except Exception as e:
            logger.warning(f"Groq failed: {e} — trying Ollama")

    # 2. Ollama (local dev)
    if _check_ollama():
        try:
            answer = _call_ollama(messages)
            logger.info(f"LLM backend: ollama/{OLLAMA_MODEL}")
            return answer, f"ollama/{OLLAMA_MODEL}"
        except Exception as e:
            logger.warning(f"Ollama failed: {e} — using mock")

    # 3. Mock fallback
    logger.warning("Using mock response — set GROQ_API_KEY for real LLM")
    return _mock_response(question), "mock"
