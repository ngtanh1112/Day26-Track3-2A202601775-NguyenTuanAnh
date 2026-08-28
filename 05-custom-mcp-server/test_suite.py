"""Automated End-to-End Test Suite for OpsSentinel MCP Server.

Kiểm thử toàn diện 3 cấp độ:
1. CƠ BẢN (Basic):
   - Khởi tạo MCP Server, khám phá danh sách tools.
   - Kiểm tra logic của 5 tools: get_service_health, query_service_logs, diagnose_system_v1, diagnose_system_v2, execute_remediation.
2. TRUNG BÌNH (Medium):
   - Khởi chạy HTTP Server với Streamable HTTP transport.
   - Kiểm thử Token Authentication với 3 trường hợp: Valid Token, Invalid Token, Missing Token.
3. KHÓ (Hard):
   - Đọc và thẩm định metadata qua Resource `server://info`.
   - Kiểm tra Versioning: Gọi song song tool v1 (legacy) và v2 (modern) đảm bảo backward compatibility.
   - Kiểm tra Prompt template `triage-incident` và Resource `server://runbooks`.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

SERVER_SCRIPT = str(Path(__file__).parent / "server.py")
HTTP_PORT = 8092
SERVER_URL = f"http://127.0.0.1:{HTTP_PORT}/mcp"
VALID_TOKEN = "ops-sec-token-day26-2026"
INVALID_TOKEN = "unauthorized-token-12345"


# ═════════════════════════════════════════════════════════════════════
# 1. TEST SUITE: STDIO, RESOURCES, PROMPTS, TOOLS & VERSIONING (KHÓ)
# ═════════════════════════════════════════════════════════════════════

async def test_stdio_and_versioning() -> bool:
    print("\n" + "=" * 70)
    print("🚀 [TEST SUITE 1] STDIO TRANSPORT, METADATA, TOOLS & VERSIONING")
    print("=" * 70)

    params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT, "--transport", "stdio"],
        env=dict(os.environ),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_res = await session.initialize()
            assert init_res.server_info.name == "ops-sentinel", "Server name mismatch"
            print(f"✅ 1.1 Khởi tạo Session thành công: {init_res.server_info.name} (Protocol: {init_res.protocol_version})")

            # 1.2 Resource server://info (Khó)
            info_res = await session.read_resource("server://info")
            info_data = json.loads(info_res.contents[0].text)
            assert info_data["name"] == "ops-sentinel"
            assert "version" in info_data
            assert len(info_data["deprecated_tools"]) >= 1
            print(f"✅ 1.2 Đọc Metadata 'server://info': v{info_data['version']}, Deprecated Tools={len(info_data['deprecated_tools'])}")

            # 1.3 Resource server://runbooks
            runbooks_res = await session.read_resource("server://runbooks")
            runbooks_data = json.loads(runbooks_res.contents[0].text)
            assert "restart_service" in runbooks_data
            print(f"✅ 1.3 Đọc Resource 'server://runbooks' thành công ({len(runbooks_data)} quy trình SOP)")

            # 1.4 Prompt triage-incident
            prompt_res = await session.get_prompt("triage-incident", {"incident_id": "INC-2026-001"})
            assert "INC-2026-001" in prompt_res.messages[0].content.text
            print(f"✅ 1.4 Lấy Prompt template 'triage-incident' thành công")

            # 1.5 List Tools
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            assert "get_service_health" in tool_names
            assert "query_service_logs" in tool_names
            assert "diagnose_system_v1" in tool_names
            assert "diagnose_system_v2" in tool_names
            assert "investigate_incident_v2" in tool_names
            assert "execute_remediation" in tool_names
            print(f"✅ 1.5 Danh sách Tools ({len(tool_names)} tools): {', '.join(tool_names)}")

            # 1.6 Call Tool get_service_health
            r_health = await session.call_tool("get_service_health", {"service_name": "auth-service"})
            health_json = json.loads(r_health.content[0].text)
            assert health_json["status"] == "HEALTHY"
            print(f"✅ 1.6 Tool get_service_health: {health_json['service']} -> {health_json['status']}")

            # 1.7 Call Tool query_service_logs
            r_logs = await session.call_tool("query_service_logs", {"service_name": "payment-gateway", "limit": 2})
            logs_json = json.loads(r_logs.content[0].text)
            assert logs_json["matched_count"] > 0
            print(f"✅ 1.7 Tool query_service_logs: {logs_json['matched_count']} log entries retrieved")

            # 1.8 Versioning Backward Compatibility: Tool v1 vs Tool v2
            r_v1 = await session.call_tool("diagnose_system_v1", {"service_name": "payment-gateway"})
            assert "[v1]" in r_v1.content[0].text
            print(f"✅ 1.8 Tool v1 Legacy hoạt động chính xác: {r_v1.content[0].text.strip()}")

            r_v2 = await session.call_tool("diagnose_system_v2", {"service_name": "payment-gateway"})
            v2_json = json.loads(r_v2.content[0].text)
            assert v2_json["api_version"] == "2.2.0"
            assert "health_score" in v2_json
            assert "metrics" in v2_json
            assert "dependencies" in v2_json
            print(f"✅ 1.9 Tool v2 Modern trả full JSON & Health Score ({v2_json['health_score']}/100)")

            # 1.10 Tool execute_remediation with dry_run
            r_remedy = await session.call_tool(
                "execute_remediation",
                {"service_name": "inventory-service", "action": "clear_cache", "dry_run": True},
            )
            remedy_json = json.loads(r_remedy.content[0].text)
            assert remedy_json["status"] == "SIMULATED_SUCCESS"
            print(f"✅ 1.10 Tool execute_remediation (dry_run=True): {remedy_json['status']}")

    return True


# ═════════════════════════════════════════════════════════════════════
# 2. TEST SUITE: STREAMABLE HTTP & TOKEN AUTHENTICATION (TRUNG BÌNH)
# ═════════════════════════════════════════════════════════════════════

async def test_http_auth_suite() -> bool:
    print("\n" + "=" * 70)
    print("🛡️  [TEST SUITE 2] STREAMABLE HTTP TRANSPORT & TOKEN AUTHENTICATION")
    print("=" * 70)

    # Khởi động server dạng HTTP daemon process
    env = dict(os.environ)
    env["OPS_SERVER_PORT"] = str(HTTP_PORT)
    env["OPS_AUTH_TOKEN"] = VALID_TOKEN
    env["PYTHONIOENCODING"] = "utf-8"

    server_proc = subprocess.Popen(
        [sys.executable, SERVER_SCRIPT, "--transport", "streamable-http", "--port", str(HTTP_PORT)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Chờ server sẵn sàng
        print(f"⏳ Đang chờ HTTP Server khởi động tại port {HTTP_PORT}...")
        for _ in range(30):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"http://127.0.0.1:{HTTP_PORT}/mcp", timeout=1.0)
                    if resp.status_code in [200, 401, 403, 404, 405]:
                        break
            except Exception:
                await asyncio.sleep(0.2)
        else:
            print("❌ Không thể kết nối tới HTTP Server sau 6s!")
            return False

        print("📡 HTTP Server đã sẵn sàng!")

        # Case 2.1: Token ĐÚNG
        print("\n▶️  [Case 2.1] Gửi Request với Bearer Token ĐÚNG:")
        http_client_valid = httpx.AsyncClient(headers={"Authorization": f"Bearer {VALID_TOKEN}"}, timeout=10.0)
        async with http_client_valid:
            async with streamable_http_client(SERVER_URL, http_client=http_client_valid) as (read, write):
                async with ClientSession(read, write) as session:
                    init_res = await session.initialize()
                    assert init_res.server_info.name == "ops-sentinel"
                    tools = await session.list_tools()
                    assert len(tools.tools) > 0
                    print(f"    ✅ Xác thực thành công! Lấy được {len(tools.tools)} tools.")

        # Case 2.2: Token SAI (Kỳ vọng bị từ chối)
        print("\n▶️  [Case 2.2] Gửi Request với Bearer Token SAI:")
        http_client_invalid = httpx.AsyncClient(headers={"Authorization": f"Bearer {INVALID_TOKEN}"}, timeout=5.0)
        rejected_invalid = False
        try:
            async with http_client_invalid:
                async with streamable_http_client(SERVER_URL, http_client=http_client_invalid) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
        except (httpx.HTTPStatusError, Exception) as exc:
            rejected_invalid = True
            print(f"    ✅ Token SAI đã bị chặn thành công! Lỗi nhận được: {exc}")

        assert rejected_invalid, "Lỗi bảo mật: Token sai vẫn truy cập được!"

        # Case 2.3: THIẾU Token (Kỳ vọng bị từ chối)
        print("\n▶️  [Case 2.3] Gửi Request THIẾU Header Authorization:")
        http_client_missing = httpx.AsyncClient(headers={}, timeout=5.0)
        rejected_missing = False
        try:
            async with http_client_missing:
                async with streamable_http_client(SERVER_URL, http_client=http_client_missing) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
        except (httpx.HTTPStatusError, Exception) as exc:
            rejected_missing = True
            print(f"    ✅ Thiếu Token đã bị chặn thành công! Lỗi nhận được: {exc}")

        assert rejected_missing, "Lỗi bảo mật: Thiếu token vẫn truy cập được!"

        return True

    finally:
        server_proc.terminate()
        server_proc.wait(timeout=5)


async def main() -> None:
    print("=" * 70)
    print("🎯 OPS-SENTINEL MCP SERVER — TOÀN BỘ BỘ TEST TỰ ĐỘNG DAY 26")
    print("=" * 70)

    t1 = await test_stdio_and_versioning()
    t2 = await test_http_auth_suite()

    print("\n" + "=" * 70)
    print("🏁 TỔNG KẾT BÁO CÁO KIỂM THỬ:")
    print(f"  • Cơ bản (MCP Tools logic & schema):              {'✅ PASSED' if t1 else '❌ FAILED'}")
    print(f"  • Trung bình (Streamable HTTP & Token Auth):       {'✅ PASSED' if t2 else '❌ FAILED'}")
    print(f"  • Khó (Versioning v1/v2, server://info, Prompts):  {'✅ PASSED' if t1 else '❌ FAILED'}")
    print("=" * 70)

    if not (t1 and t2):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
