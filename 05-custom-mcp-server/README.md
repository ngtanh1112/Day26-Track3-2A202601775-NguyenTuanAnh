# OpsSentinel MCP Server — Production Operations & Incident Triage

> **Bài tập lớn Model Context Protocol (MCP) — Khóa học AI Engineer Track 3 (Day 26)**  
> **Học viên:** Nguyễn Tuấn Anh (Mã HV: 2A202601775)  
> **Repository:** [ngtanh1112/Day26-Track3-2A202601775-NguyenTuanAnh](https://github.com/ngtanh1112/Day26-Track3-2A202601775-NguyenTuanAnh)

---

## 1. Bài toán thực tế giải quyết (Problem Statement)

Trong môi trường vận hành đám mây và hệ thống vi dịch vụ (Microservices), khi xảy ra sự cố (Incidents, ví dụ: 504 Gateway Timeout, Database Connection Exhaustion, Spike Latency), các kỹ sư DevOps / SRE thường mất từ 15–45 phút để:
1. Đăng nhập thủ công qua nhiều dashboard giám sát (Grafana, Datadog).
2. SSH vào từng cụm máy chủ/pod để trích xuất logs lỗi.
3. Phân tích nguyên nhân cốt lõi (Root Cause Analysis - RCA) và tính toán vùng ảnh hưởng (Blast Radius).
4. Thực thi các bước xử lý theo Runbook SOP (Clear cache, restart pod, bật Circuit Breaker).

**OpsSentinel MCP Server** được xây dựng như một cầu nối chuẩn hóa giao thức MCP (Model Context Protocol) giữa các **AI Assistant (Claude Code, Cursor, ADK Agents)** và hạ tầng vận hành:
- **An toàn (Safe Guardrails):** Cung cấp cơ chế thực thi Runbook với chế độ `dry_run` mô phỏng trước khi can thiệp thực tế.
- **Bảo mật (Production Security):** Xác thực qua HTTP Bearer Token, kiểm soát quyền truy cập theo scopes (`ops:read`, `ops:diagnose`, `ops:remediate`).
- **Tương thích ngược & Tiến hóa (Versioning & Backward Compatibility):** Cung cấp song song Tool `v1` (Legacy) và `v2` (Modern Rich JSON) kèm resource `server://info` để AI Client tự động thích ứng mà không gây gãy đổ tích hợp cũ.

---

## 2. Kiến trúc hệ thống (Architecture)

```mermaid
flowchart TD
    subgraph AI Clients
        Claude[Claude Code / Claude Desktop]
        ADK[ADK / Custom AI Agent]
    end

    subgraph "OpsSentinel MCP Server (v2.2.0)"
        direction TB
        Auth["Token Verifier (Bearer Auth)"]
        Meta["Resource: server://info\nResource: server://runbooks\nPrompt: triage-incident"]
        
        subgraph "MCP Tools Registry"
            T1["get_service_health"]
            T2["query_service_logs"]
            T3["diagnose_system_v1 (Legacy)"]
            T4["diagnose_system_v2 (Modern)"]
            T5["investigate_incident_v1 (Legacy)"]
            T6["investigate_incident_v2 (Modern)"]
            T7["execute_remediation (Dry-run)"]
        end
    end

    subgraph "Infrastructure & Mock Telemetry"
        SVC["Microservices (Auth, Payment, Order, Inventory)"]
        LOGS["Structured Error Logs DB"]
        INC["Incident Knowledge Base"]
    end

    Claude -- stdio / HTTP --> Auth
    ADK -- Streamable HTTP --> Auth
    Auth --> Meta
    Auth --> T1 & T2 & T3 & T4 & T5 & T6 & T7
    T1 & T4 --> SVC
    T2 --> LOGS
    T5 & T6 --> INC
    T7 --> SVC
```

---

## 3. Cấu trúc thư mục

```
05-custom-mcp-server/
├── server.py                 # Source code MCP Server chính (FastMCP / MCPServer)
├── client_stdio.py          # Client kiểm thử qua stdio, đọc metadata server://info & versioning
├── client_http_auth.py       # Client kiểm thử qua Streamable HTTP có Bearer Token Auth
├── test_suite.py             # Bộ test tự động toàn diện kiểm tra cả 3 cấp độ (Cơ bản, Trung bình, Khó)
├── claude_code_config.json   # File mẫu cấu hình đăng ký server vào Claude Code / Desktop
├── .env.example              # Mẫu biến môi trường
└── README.md                 # Tài liệu hướng dẫn chi tiết
```

---

## 4. Chi tiết Danh mục MCP Tools (Input / Output Specification)

### 4.1. `get_service_health`
Tra cứu trạng thái vận hành thời gian thực của microservice.
- **Input:**
  - `service_name` (string, required): Tên microservice (`auth-service`, `payment-gateway`, `order-service`, `inventory-service`).
  - `region` (string, optional, default: `"ap-southeast-1"`): Vùng triển khai.
- **Output Sample (JSON):**
  ```json
  {
    "service": "payment-gateway",
    "region": "ap-southeast-1",
    "status": "DEGRADED",
    "uptime_percentage": 98.45,
    "cpu_usage_pct": 89.2,
    "memory_usage_pct": 84.7,
    "p99_latency_ms": 1250.0,
    "error_rate_pct": 4.85,
    "active_alerts": 2,
    "checked_at": "2026-08-28T16:55:00Z"
  }
  ```

---

### 4.2. `query_service_logs`
Truy vấn logs có cấu trúc lọc theo mức độ cảnh báo và từ khóa.
- **Input:**
  - `service_name` (string, required): Tên dịch vụ cần lấy log.
  - `level` (string, optional, default: `"ERROR"`): Ngưỡng lọc (`INFO`, `WARN`, `ERROR`, `CRITICAL`).
  - `limit` (integer, optional, default: `5`): Số lượng log tối đa trả về.
  - `search_keyword` (string, optional): Từ khóa tìm kiếm trong log message.
- **Output Sample (JSON):**
  ```json
  {
    "service": "payment-gateway",
    "filter_level": "ERROR",
    "matched_count": 2,
    "logs": [
      {
        "timestamp": "2026-08-28T16:42:05Z",
        "level": "ERROR",
        "trace_id": "tr-pay-8845",
        "message": "HTTP 504 Gateway Timeout from bank-partner-api after 3000ms"
      }
    ]
  }
  ```

---

### 4.3. Versioning Pair: `diagnose_system_v1` vs `diagnose_system_v2`

| Tiêu chí | `diagnose_system_v1` (Legacy) | `diagnose_system_v2` (Modern) |
|---|---|---|
| **Mục đích** | Tương thích ngược với client cũ | Phân tích sâu, tính Health Score & Dependency Graph |
| **Output Type** | Plain Text string | Structured JSON / Markdown report |
| **Input Params** | `service_name` | `service_name`, `include_metrics`, `include_dependency_graph`, `format` |

- **Output `diagnose_system_v1`:**
  ```text
  [v1] payment-gateway: Trạng thái=DEGRADED, CPU=89.2%, RAM=84.7%, Cảnh báo=2
  ```
- **Output `diagnose_system_v2`:**
  ```json
  {
    "api_version": "2.2.0",
    "service": "payment-gateway",
    "health_score": 47.9,
    "status": "DEGRADED",
    "timestamp": "2026-08-28T16:55:00Z",
    "metrics": {
      "uptime_percentage": 98.45,
      "cpu_usage_pct": 89.2,
      "memory_usage_pct": 84.7,
      "p99_latency_ms": 1250.0,
      "error_rate_pct": 4.85,
      "active_alerts": 2
    },
    "dependencies": {
      "downstream_services": ["bank-partner-api", "payment-db", "kafka-events"],
      "blast_radius_risk": "MEDIUM"
    }
  }
  ```

---

### 4.4. `investigate_incident_v2`
Báo cáo toàn diện sự cố với phân tích nguyên nhân cốt lõi (RCA) và quy trình xử lý (Playbook).
- **Input:**
  - `incident_id` (string, required): Mã sự cố (ví dụ: `INC-2026-001`, `INC-2026-002`).
  - `include_root_cause_analysis` (bool, optional, default: `True`).
  - `include_remediation_steps` (bool, optional, default: `True`).
- **Output Sample (JSON):**
  ```json
  {
    "api_version": "2.2.0",
    "incident_id": "INC-2026-001",
    "title": "High Latency and Timeout on Payment Gateway",
    "service": "payment-gateway",
    "severity": "HIGH",
    "status": "INVESTIGATING",
    "root_cause_analysis": {
      "primary_cause": "Upstream bank partner API experiencing degraded network connectivity in ap-southeast region.",
      "blast_radius": "4.85% checkout failures on e-commerce frontend.",
      "impacted_components": ["payment-gateway", "order-service", "checkout-flow"]
    },
    "remediation_playbook": [
      "1. Bật Circuit Breaker cho bank-partner-api để fallback sang cổng thanh toán phụ.",
      "2. Flush và refresh cache token kết nối.",
      "3. Tạm thời tăng replica của payment-gateway từ 3 lên 6 pods."
    ]
  }
  ```

---

### 4.5. `execute_remediation`
Thực thi hành động khắc phục sự cố với chốt an toàn `dry_run`.
- **Input:**
  - `service_name` (string, required): Dịch vụ mục tiêu.
  - `action` (string, required): Hành động (`restart_service`, `clear_cache`, `scale_up`, `toggle_circuit_breaker`).
  - `dry_run` (bool, optional, default: `True`): Chế độ mô phỏng an toàn.
  - `reason` (string, optional): Lý do thực thi.
- **Output Sample (dry_run=True):**
  ```json
  {
    "action": "toggle_circuit_breaker",
    "target_service": "payment-gateway",
    "dry_run": true,
    "status": "SIMULATED_SUCCESS",
    "message": "Mô phỏng thành công hành động 'toggle_circuit_breaker' trên dịch vụ 'payment-gateway'. Không có thay đổi thực tế.",
    "estimated_impact": "Dịch vụ sẽ khôi phục về trạng thái HEALTHY trong vòng ~30s sau khi thực thi thật."
  }
  ```

---

## 5. Hướng dẫn Đăng ký MCP Server với Claude Code & Claude Desktop

### Cách 1: Đăng ký qua lệnh CLI của Claude Code
Chạy lệnh sau trong terminal:
```bash
# Đăng ký chế độ stdio
claude mcp add ops-sentinel -- python d:/AIVIN/Day26-Track3-2A202601775-NguyenTuanAnh/05-custom-mcp-server/server.py --transport stdio
```

### Cách 2: Cấu hình file `claude_code_config.json` hoặc `.claude.json` / `claude_desktop_config.json`
Thêm cấu hình sau vào file cấu hình của Claude:

```json
{
  "mcpServers": {
    "ops-sentinel-stdio": {
      "command": "python",
      "args": [
        "d:/AIVIN/Day26-Track3-2A202601775-NguyenTuanAnh/05-custom-mcp-server/server.py",
        "--transport",
        "stdio"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "OPS_AUTH_TOKEN": "ops-sec-token-day26-2026"
      }
    },
    "ops-sentinel-http": {
      "url": "http://localhost:8090/mcp",
      "headers": {
        "Authorization": "Bearer ops-sec-token-day26-2026"
      }
    }
  }
}
```

---

## 6. Hướng dẫn Cài đặt & Chạy Thực tế

### 6.1. Cài đặt thư viện phụ thuộc
```bash
cd Day26-Track3-2A202601775-NguyenTuanAnh
pip install -r requirements.txt
```

### 6.2. Kiểm thử Mức Khó: Stdio, Metadata `server://info` & Versioning
Chạy script client stdio:
```bash
cd 05-custom-mcp-server
python client_stdio.py
```
**Bằng chứng thực thi:**
- Đọc thành công `server://info` lấy version `2.2.0` và danh sách deprecated tools.
- Gọi thành công cả `diagnose_system_v1` (legacy) và `diagnose_system_v2` (modern).

---

### 6.3. Kiểm thử Mức Trung bình: Streamable HTTP & Authentication

**Bước 1: Mở Terminal 1 để chạy HTTP Server**
```bash
cd 05-custom-mcp-server
python server.py --transport streamable-http --port 8090
```

**Bước 2: Mở Terminal 2 để chạy Test Suite Auth**
```bash
cd 05-custom-mcp-server
python client_http_auth.py
```

**Kịch bản kiểm thử bảo mật tự động:**
1. **Valid Token (`ops-sec-token-day26-2026`):** Trả về `200 OK`, khám phá danh sách tools và gọi tool thành công.
2. **Invalid Token (`invalid-wrong-token-999`):** Server từ chối kết nối (`401/403 Forbidden`).
3. **Missing Token (Không có header `Authorization`):** Server chặn truy cập ngay lập tức.

---

### 6.4. Chạy toàn bộ Bộ Test tự động (Automated End-to-End Test Suite)
Chỉ với 1 lệnh duy nhất, hệ thống tự động khởi chạy và xác thực toàn bộ các tiêu chí Cơ bản, Trung bình và Khó:
```bash
cd 05-custom-mcp-server
python test_suite.py
```

**Kết quả kiểm thử thực tế:**
```
======================================================================
🎯 OPS-SENTINEL MCP SERVER — TOÀN BỘ BỘ TEST TỰ ĐỘNG DAY 26
======================================================================

🚀 [TEST SUITE 1] STDIO TRANSPORT, METADATA, TOOLS & VERSIONING
✅ 1.1 Khởi tạo Session thành công: ops-sentinel (Protocol: 2025-11-25)
✅ 1.2 Đọc Metadata 'server://info': v2.2.0, Deprecated Tools=2
✅ 1.3 Đọc Resource 'server://runbooks' thành công (4 quy trình SOP)
✅ 1.4 Lấy Prompt template 'triage-incident' thành công
✅ 1.5 Danh sách Tools (7 tools): get_service_health, query_service_logs, diagnose_system_v1, diagnose_system_v2, investigate_incident_v1, investigate_incident_v2, execute_remediation
✅ 1.6 Tool get_service_health: auth-service -> HEALTHY
✅ 1.7 Tool query_service_logs: 2 log entries retrieved
✅ 1.8 Tool v1 Legacy hoạt động chính xác
✅ 1.9 Tool v2 Modern trả full JSON & Health Score (47.9/100)
✅ 1.10 Tool execute_remediation (dry_run=True): SIMULATED_SUCCESS

🛡️  [TEST SUITE 2] STREAMABLE HTTP TRANSPORT & TOKEN AUTHENTICATION
⏳ Đang chờ HTTP Server khởi động tại port 8092...
📡 HTTP Server đã sẵn sàng!
▶️  [Case 2.1] Gửi Request với Bearer Token ĐÚNG:
    ✅ Xác thực thành công! Lấy được 7 tools.
▶️  [Case 2.2] Gửi Request với Bearer Token SAI:
    ✅ Token SAI đã bị chặn thành công!
▶️  [Case 2.3] Gửi Request THIẾU Header Authorization:
    ✅ Thiếu Token đã bị chặn thành công!

======================================================================
🏁 TỔNG KẾT BÁO CÁO KIỂM THỬ:
  • Cơ bản (MCP Tools logic & schema):              ✅ PASSED
  • Trung bình (Streamable HTTP & Token Auth):       ✅ PASSED
  • Khó (Versioning v1/v2, server://info, Prompts):  ✅ PASSED
======================================================================
```
