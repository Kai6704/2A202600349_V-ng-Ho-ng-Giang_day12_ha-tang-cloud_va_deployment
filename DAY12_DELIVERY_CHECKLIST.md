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

### Exercise 3.1: Railway deployment
- URL: https://your-app.railway.app
- Screenshot: [Link to screenshot in repo]

## Part 4: API Security

### Exercise 4.1-4.3: Test results
[Paste your test outputs]

### Exercise 4.4: Cost guard implementation
[Explain your approach]

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
[Your explanations and test results]
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
https://your-agent.railway.app

## Platform
Railway / Render / Cloud Run

## Test Commands

### Health Check
```bash
curl https://your-agent.railway.app/health
# Expected: {"status": "ok"}
```

### API Test (with authentication)
```bash
curl -X POST https://your-agent.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

## Environment Variables Set
- PORT
- REDIS_URL
- AGENT_API_KEY
- LOG_LEVEL

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
