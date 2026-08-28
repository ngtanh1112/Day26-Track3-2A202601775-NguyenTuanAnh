# Day 26 — Model Context Protocol (MCP) & Function Calling

> **Báo cáo thực hành & Bài tập lớn Day 26 — AI Engineer Track 3**  
> **Học viên:** Nguyễn Tuấn Anh (Mã học viên: `2A202601775`)  
> **Repository:** [ngtanh1112/Day26-Track3-2A202601775-NguyenTuanAnh](https://github.com/ngtanh1112/Day26-Track3-2A202601775-NguyenTuanAnh)

---

## 📌 Bảng Đánh Giá Mức Độ Hoàn Thành Bài Lab

| Cấp độ | Tiêu chí yêu cầu | Trạng thái | Nơi triển khai & Bằng chứng |
|---|---|:---:|---|
| **Cơ bản** | • Source code MCP Server do học viên tự xây<br>• Ít nhất 1–2 MCP tools<br>• README hướng dẫn cài đặt & chạy<br>• Mô tả bài toán thực tế & Input/Output từng tool<br>• Hướng dẫn đăng ký với Claude Code<br>• Bằng chứng kiểm tra tool chạy được | **HOÀN THÀNH** | [`05-custom-mcp-server/`](05-custom-mcp-server/)<br>Server `ops-sentinel` với 7 tools chuyên sâu, tài liệu chi tiết, test suite tự động. |
| **Trung bình** | • Phiên bản server chạy bằng **Streamable HTTP**<br>• **Authentication bằng Token** (Bearer Token verification)<br>• Hướng dẫn & Script test **Token ĐÚNG**<br>• Hướng dẫn & Script test **Token SAI / THIẾU** (Bị chặn 401/403) | **HOÀN THÀNH** | [`05-custom-mcp-server/client_http_auth.py`](05-custom-mcp-server/client_http_auth.py)<br>Xác thực Bearer token qua `MCPServer` + `TokenVerifier`, chặn token sai/thiếu. |
| **Khó** | • **Versioning** cho một tool thật (v1 vs v2 song song)<br>• **Client cũ (v1) vẫn hoạt động** bình thường (Backward compatibility)<br>• Resource **`server://info`** công bố metadata, version, deprecated tools, migration guide<br>• Client/script đọc metadata trước khi gọi tool | **HOÀN THÀNH** | [`05-custom-mcp-server/client_stdio.py`](05-custom-mcp-server/client_stdio.py)<br>Resource `server://info`, tool `diagnose_system_v1` & `diagnose_system_v2`, `investigate_incident_v1` & `v2`. |
| **Bảo mật** | • Không commit API key, Access token, Password, Secret, `.env` thật lên GitHub<br>• Sử dụng `.env.example` làm template | **HOÀN THÀNH** | [`.gitignore`](.gitignore), [`.env.example`](.env.example) |

---

## 📂 Cấu trúc Repository

```
Day26-Track3-2A202601775-NguyenTuanAnh/
├── README.md                           ← Báo cáo tổng quan bài lab & ma trận tiêu chí
├── requirements.txt                    ← Danh sách thư viện: mcp[cli], google-genai, httpx, uvicorn
├── .env.example                        ← Mẫu biến môi trường an toàn (không chứa secret thật)
├── .gitignore                          ← Chặn commit .env, venv, cache
│
├── 01-function-calling/                ← [Lab 1] Function Calling thuần túy với Google Gemini SDK
│   ├── README.md
│   └── weather_function_calling.py
│
├── 02-mcp-basics/                      ← [Lab 2] MCP cơ bản (FastMCP Server + ClientSession qua stdio)
│   ├── README.md
│   ├── weather_server.py
│   └── weather_client.py
│
├── 03-production/                      ← [Lab 3] Các kiến trúc MCP trong Production
│   ├── README.md
│   ├── auth_server.py                  ← Server Streamable HTTP có Bearer Token Auth
│   ├── auth_client.py                  ← Client kết nối HTTP có Header Authorization
│   ├── registry.json                   ← Danh mục Tool Registry trung tâm
│   ├── registry_client.py              ← Agent khám phá & chọn tool động qua Registry
│   ├── versioned_server.py             ← Server hỗ trợ versioning v1/v2 và resource server://info
│   └── versioned_client.py             ← Client đọc metadata trước khi gọi tool
│
├── 04-lab/                             ← [Lab 4] Weather Agent với Remote MCP Server & Google ADK
│   ├── README.md
│   ├── mcp-server/                     ← Remote MCP Server (FastMCP qua Streamable HTTP)
│   │   ├── weather.py
│   │   └── Dockerfile
│   └── mcp-client/                     ← ADK Agent điều phối Function Calling qua McpToolset
│       ├── weather_agent/agent.py
│       └── verify_setup.py
│
└── 05-custom-mcp-server/               ← ⭐ [BÀI TẬP LỚN MCP CUSTOM - MỨC ĐỘ KHÓ]
    ├── README.md                       ← Tài liệu đầy đủ: bài toán, I/O tools, Claude Code setup
    ├── server.py                       ← OpsSentinel MCP Server (Stdio + Streamable HTTP + Auth + Versioning)
    ├── client_stdio.py                 ← Client Stdio: Đọc metadata server://info & kiểm tra versioning
    ├── client_http_auth.py             ← Client HTTP: Kiểm thử 3 trường hợp Auth (Đúng, Sai, Thiếu)
    ├── test_suite.py                   ← Bộ Test Suite E2E tự động xác thực toàn bộ tiêu chí
    ├── claude_code_config.json         ← Cấu hình tích hợp Claude Code & Claude Desktop
    └── .env.example                    ← Biến môi trường mẫu cho server
```

---

## ⚡ Hướng Dẫn Cài Đặt & Chạy Nhanh

### 1. Cài đặt môi trường
```bash
python -m venv .venv
# Trên Windows PowerShell:
.venv\Scripts\Activate.ps1
# Trên Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

---

### 2. Chạy bài Custom MCP Server — OpsSentinel (Cơ bản, Trung bình & Khó)

#### 🚀 Chạy toàn bộ Bộ Test Tự Động (Recommended):
```bash
cd 05-custom-mcp-server
python test_suite.py
```

#### 🛡️ Chạy kiểm thử Versioning & Metadata qua Stdio:
```bash
cd 05-custom-mcp-server
python client_stdio.py
```

#### 🔒 Chạy kiểm thử Streamable HTTP & Authentication:
```bash
# Terminal 1 (Khởi chạy Server HTTP tại port 8090):
cd 05-custom-mcp-server
python server.py --transport streamable-http --port 8090

# Terminal 2 (Chạy Client kiểm thử Auth với 3 kịch bản):
cd 05-custom-mcp-server
python client_http_auth.py
```

---

### 3. Đăng ký OpsSentinel MCP Server vào Claude Code / Claude Desktop

#### Cách 1: Đăng ký qua lệnh Claude Code CLI
```bash
claude mcp add ops-sentinel -- python d:/AIVIN/Day26-Track3-2A202601775-NguyenTuanAnh/05-custom-mcp-server/server.py --transport stdio
```

#### Cách 2: Thêm vào file cấu hình Claude Desktop (`claude_desktop_config.json`) hoặc `.claude.json`
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

## 📖 Tóm Tắt Khái Niệm: Function Calling vs Model Context Protocol (MCP)

| Tiêu chí | Function Calling | Model Context Protocol (MCP) |
|---|---|---|
| **Bản chất** | Khả năng của mô hình LLM (Model capability) | Giao thức giao tiếp chuẩn hóa Client–Server (Protocol) |
| **Khai báo Tool** | Viết thủ công schema JSON trong từng ứng dụng | Server tự công bố (Self-describing) qua `@mcp.tool()` |
| **Khám phá Tool** | Hard-code danh sách `tools` trong code app | Khám phá động tại runtime qua `session.list_tools()` |
| **Môi trường thực thi** | App client tự thực thi function | MCP Server độc lập thực thi, client chỉ điều phối |
| **Tái sử dụng** | Khó dùng lại giữa các framework khác nhau | Dùng chung cho Claude Code, Claude Desktop, Cursor, ADK Agents |
| **Bảo mật & Phân tán** | Gắn chặt vào process của app | Hỗ trợ phân tán qua Streamable HTTP, Bearer Auth, Scopes |

---

## 🎯 Bằng Chứng Kiểm Thử Tổng Hợp

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
✅ 1.8 Tool v1 Legacy hoạt động chính xác: [v1] payment-gateway: Trạng thái=DEGRADED, CPU=89.2%, RAM=84.7%, Cảnh báo=2
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
