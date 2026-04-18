#  Delivery Checklist — Day 12 Lab Submission

> **Student Name:** Vương Hoàng Giang  
> **Student ID:** 2A202600349  
> **Date:** 17/04/2026

---

##  Submission Requirements

Submit a **GitHub repository** containing:

### 1. Mission Answers (40 points)

Create a file `MISSION_ANSWERS.md` with your answers to all exercises:

```markdown
# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. API key và DB password hardcode trong code
2. Secret bị log ra console
3. Không có authentication
4. Không có rate limiting
5. Không có config management
5. Port hardcore 8000 không đọc từ PORT env
6. host="localhost" không bind được trên cloud
7. print() thay vì proper logging
8. Không có heath check endpoint
9. Không có error handling
10. reload=True trong production

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config management | Hardcode trực tiếp trong code (`OPENAI_API_KEY`, `DATABASE_URL`) | Đọc từ environment variables | Cloud platform inject config qua env vars — hardcode không thể thay đổi giữa môi trường |
| Logging | `print()` thô, không có level/timestamp | Structured JSON logging | Cloud platform (Railway, GCP) thu thập log theo format chuẩn — `print` không có level để filter/alert |
| Health check endpoint | Không có `/health` | Có `/health` endpoint | Platform dùng health check để biết app sẵn sàng; thiếu → không route traffic, không tự restart khi crash |
| Graceful shutdown | Không xử lý signal shutdown | Xử lý SIGTERM/shutdown event | Container bị kill đột ngột → request đang xử lý bị mất; graceful shutdown cho phép hoàn thành request trước khi dừng |
| Host binding | `host="localhost"` — chỉ nhận traffic nội bộ |  `host="0.0.0.0"` — nhận traffic từ mọi interface | Trong container/cloud, app phải bind `0.0.0.0` mới nhận được request từ bên ngoài |
| Port config | `port=8000` hardcode | `port=int(os.getenv("PORT", 8000))` | Railway/Render inject `$PORT` động — hardcode sẽ sai port, app không nhận được request |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: python 3.11
2. Working directory: là `/app` bên trong container
3. Tại sao COPY requirements.txt trước? 
- Docker build theo từng layer, mỗi lệnh = 2 layer, và layer được cache lại.
- Nếu chỉ sửa app.py, layer A và B vẫn dùng cache. Chỉ rebuild layer C.
- Nếu copy code trước, mỗi lần sửa code dù nhỏ sẽ pip install lại từ đầu.
4. CMD vs ENTRYPOINT khác nhau thế nào? 
- CND được dùng với lệnh mặc định khi start. Được dùng khi app có thể chạy nhiều cách.
- ENTRYPOINT được dùng với cố định, luôn chạy. Được đùng khi app chỉ có 1 mục đích duy nhất.

### Exercise 2.3: Image size comparison
- Develop: 424 MB
- Production: 56.6 MB
- Difference: 86.65%

1. Stage 1 làm gì? Stage 1: Builder. Stage này để cài đặt dependencies không dùng để deploy. Stage này sẽ bị bỏ đi sau khi build xong.
2. Stage 2 làm gì? Stage 2: Runtime. Stage này chỉ chứa thứ cần thiết để chạy app. 
3. Tại sao image nhỏ hơn? Multi-stage build cho phép dùng image nặng để build, nhưng image cuối chỉ chứa kết quả trong quá trình build không cần compliler, không cần buil tools nên image nhỏ hơn.

### Exercise 2.4: Docker Compose Stack

**Architecture Diagram:**
```
                        Internet
                           │
                    port 80/443
                           │
                    ┌──────▼──────┐
                    │    Nginx    │  ← Reverse proxy / Load balancer
                    │  (alpine)   │    nginx.conf mount từ host
                    └──────┬──────┘
                           │ internal network
              ┌────────────▼────────────┐
              │         agent           │  ← FastAPI (port 8000)
              │    (runtime stage)      │    KHÔNG expose ra ngoài trực tiếp
              └────────┬────────────────┘
                       │
            ┌──────────┴──────────┐
            │                     │
     ┌──────▼──────┐      ┌───────▼──────┐
     │    Redis     │      │    Qdrant    │
     │  :6379       │      │   :6333      │
     │  (alpine)    │      │  v1.9.0      │
     │  256MB LRU   │      │  Vector DB   │
     └─────────────┘      └─────────────┘
            │                     │
     redis_data vol        qdrant_data vol  ← persistent storage
```

**Services được start:** 4 services — nginx, agent, redis, qdrant

**Cách communicate:**
- Tất cả services nằm trong `internal` bridge network, giao tiếp qua tên service (DNS nội bộ)
- Agent kết nối Redis qua `redis://redis:6379/0`
- Agent kết nối Qdrant qua `http://qdrant:6333`
- Chỉ Nginx được expose ra ngoài (port 80/443), agent không có port mapping trực tiếp
- Startup order: Redis healthy → Qdrant healthy → Agent start → Nginx start

## Part 3: Cloud Deployment

### Exercise 3.1: Render deployment
- URL: https://day-12-5mjp.onrender.com
- Screenshot: [Deploy screenshot](Screenshot%202026-04-17%20163721.png)

## Part 4: API Security

### Exercise 4.1-4.3: Test results

**4.1 - Gọi API không có key → 401:**
```
curl http://localhost:8000/ask -X POST -H "Content-Type: application/json" -d '{"question": "Hello"}'
```
Output:
```json
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

**4.2 - Gọi API với JWT token hợp lệ → 200:**
```
curl -X POST http://localhost:8000/ask -H "Authorization: Bearer eyJhbGci..." -H "Content-Type: application/json" -d '{"question": "what is docker?"}'
```
Output:
```json
{"question":"what is docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

**4.3 - Rate limiting (Sliding Window, 5 req/10s):**
```
python rate_limiter.py
```
Output:
```
=== Test Sliding Window Rate Limiter ===

Request  1: ✅ OK  — remaining=4
Request  2: ✅ OK  — remaining=3
Request  3: ✅ OK  — remaining=2
Request  4: ✅ OK  — remaining=1
Request  5: ✅ OK  — remaining=0
Request  6: ❌ 429 — Rate limit exceeded (retry after 10s)
Request  7: ❌ 429 — Rate limit exceeded (retry after 10s)

--- Admin bypass (100 req/min) ---
Admin req 1: ✅ OK  — remaining=99
Admin req 2: ✅ OK  — remaining=98
Admin req 3: ✅ OK  — remaining=97
```
- Algorithm: Sliding Window Counter
- User limit: 10 req/phút, Admin limit: 100 req/phút
- Admin bypass: dùng instance `RateLimiter` riêng với `max_requests=100`

### Exercise 4.4: Cost guard implementation

**Approach:** Dùng class `CostGuard` với in-memory tracking, kiểm tra budget trước mỗi request LLM.

**Cơ chế hoạt động:**
- Mỗi user có `UsageRecord` lưu số tokens dùng trong ngày (reset lúc 0h UTC)
- Trước khi gọi LLM: `check_budget()` → raise `402` nếu user vượt $1/ngày, raise `503` nếu global vượt $10/ngày
- Sau khi gọi LLM: `record_usage()` cộng dồn input/output tokens và tính chi phí theo giá GPT-4o-mini
- Cảnh báo log khi user dùng ≥ 80% budget

**Giá token áp dụng:**
- Input: $0.15/1M tokens
- Output: $0.60/1M tokens

**Giới hạn:**
- Per-user: $1.0/ngày → trả về `402 Payment Required`
- Global: $10.0/ngày → trả về `503 Service Unavailable`

**Hạn chế của in-memory:** Reset khi restart server. Production cần lưu vào Redis/DB để persist qua restart và scale nhiều instance.

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes

**5.1 - Health Check & Readiness Probe:**
- `/health` — Liveness probe: kiểm tra memory qua psutil, trả về `status: ok/degraded`
- `/ready` — Readiness probe: kiểm tra Redis (`r.ping()`) và DB (`db.execute("SELECT 1")`), trả về 503 khi chưa sẵn sàng

**5.2 - Graceful Shutdown (SIGTERM handler):**
```python
def handle_sigterm(signum, frame):
    # 1. Stop accepting new requests (_is_ready = False)
    # 2. Finish current requests (chờ _in_flight_requests == 0, timeout 30s)
    # 3. Close connections
    # 4. sys.exit(0)
```

**5.3 - Test graceful shutdown:**
```bash
python app.py &
PID=$!
curl http://localhost:8000/ask -X POST -H "Content-Type: application/json" -d '{"question": "Long task"}' &
kill -TERM $PID
```
Output:
```
Agent starting up...
✅ Agent is ready!
Application startup complete.
🔄 Graceful shutdown initiated...
✅ Shutdown complete
Application shutdown complete.
```

**5.4 - In-flight request tracking:**
- Middleware `track_requests` đếm số request đang xử lý qua biến `_in_flight_requests`
- Graceful shutdown chờ counter về 0 trước khi exit

**5.5 - Stateless scaling test (docker compose up --scale agent=3):**
```
python test_stateless.py
```
Output:
```
Session ID: bb63031e-097d-43a0-8c1e-0f95709e4ab8

Request 1: [instance-8fe463]  Q: What is Docker?
Request 2: [instance-5e7cf1]  Q: Why do we need containers?
Request 3: [instance-00cafb]  Q: What is Kubernetes?
Request 4: [instance-8fe463]  Q: How does load balancing work?
Request 5: [instance-5e7cf1]  Q: What is Redis used for?

Total requests: 5
Instances used: {'instance-00cafb', 'instance-8fe463', 'instance-5e7cf1'}
✅ All requests served despite different instances!

Total messages: 10
✅ Session history preserved across all instances via Redis!
```
- 5 requests được phân phối qua **3 instance khác nhau** (load balancing hoạt động)
- Session history có đủ **10 messages** (5 user + 5 assistant) dù mỗi request đến instance khác nhau
- **Redis** là chìa khóa: tất cả instance đọc/ghi chung 1 Redis → stateless thành công

**Vấn đề gặp phải:**
- Port 8000 bị chiếm khi chạy nhiều app → dùng `PORT=8001 python app.py`
- `kill -TERM $PID` trên Windows Git Bash không hoạt động → dùng `taskkill /PID X /F`
```

---

### 2. Full Source Code - Lab 06 Complete (60 points)

Your final production-ready agent with all files:

```
your-repo/
├── app/
│   ├── main.py              # Main application
│   ├── config.py            # Configuration
│   ├── auth.py              # Authentication
│   ├── rate_limiter.py      # Rate limiting
│   └── cost_guard.py        # Cost protection
├── utils/
│   └── mock_llm.py          # Mock LLM (provided)
├── Dockerfile               # Multi-stage build
├── docker-compose.yml       # Full stack
├── requirements.txt         # Dependencies
├── .env.example             # Environment template
├── .dockerignore            # Docker ignore
├── railway.toml             # Railway config (or render.yaml)
└── README.md                # Setup instructions
```

**Requirements:**
-  All code runs without errors
-  Multi-stage Dockerfile (image < 500 MB)
-  API key authentication
-  Rate limiting (10 req/min)
-  Cost guard ($10/month)
-  Health + readiness checks
-  Graceful shutdown
-  Stateless design (Redis)
-  No hardcoded secrets

---

### 3. Service Domain Link

Create a file `DEPLOYMENT.md` with your deployed service information:

```markdown
# Deployment Information

## Public URL
https://twoa202600349-v-ng-ho-ng-giang-day12-ha.onrender.com/

## Platform
Render

## Test Commands

### Health Check
```bash
curl https://twoa202600349-v-ng-ho-ng-giang-day12-ha.onrender.com/health
# Result: {"status":"ok","version":"1.0.0","environment":"development","redis":false,"llm":"ollama/mock"}
```

### API Test (with authentication)
```bash
curl -X POST https://twoa202600349-v-ng-ho-ng-giang-day12-ha.onrender.com/chat \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "Tư vấn MacBook Air M2"}'
```

## Environment Variables Set
- AGENT_API_KEY (auto-generated by Render)
- GROQ_API_KEY
- GROQ_MODEL
- ENVIRONMENT
- RATE_LIMIT_PER_MINUTE
- DAILY_BUDGET_USD

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
```

##  Pre-Submission Checklist

- [ ] Repository is public (or instructor has access)
- [ ] `MISSION_ANSWERS.md` completed with all exercises
- [ ] `DEPLOYMENT.md` has working public URL
- [ ] All source code in `app/` directory
- [ ] `README.md` has clear setup instructions
- [ ] No `.env` file committed (only `.env.example`)
- [ ] No hardcoded secrets in code
- [ ] Public URL is accessible and working
- [ ] Screenshots included in `screenshots/` folder
- [ ] Repository has clear commit history

---

##  Self-Test

Before submitting, verify your deployment:

```bash
# 1. Health check
curl https://your-app.railway.app/health

# 2. Authentication required
curl https://your-app.railway.app/ask
# Should return 401

# 3. With API key works
curl -H "X-API-Key: YOUR_KEY" https://your-app.railway.app/ask \
  -X POST -d '{"user_id":"test","question":"Hello"}'
# Should return 200

# 4. Rate limiting
for i in {1..15}; do 
  curl -H "X-API-Key: YOUR_KEY" https://your-app.railway.app/ask \
    -X POST -d '{"user_id":"test","question":"test"}'; 
done
# Should eventually return 429
```

---

##  Submission

**Submit your GitHub repository URL:**

```
https://github.com/your-username/day12-agent-deployment
```

**Deadline:** 17/4/2026

---

##  Quick Tips

1.  Test your public URL from a different device
2.  Make sure repository is public or instructor has access
3.  Include screenshots of working deployment
4.  Write clear commit messages
5.  Test all commands in DEPLOYMENT.md work
6.  No secrets in code or commit history

---

##  Need Help?

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [CODE_LAB.md](CODE_LAB.md)
- Ask in office hours
- Post in discussion forum

---

**Good luck! **
