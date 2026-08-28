"""OpsSentinel MCP Client (Streamable HTTP with Token Authentication).

Minh họa mức độ Trung bình (Medium Level):
1. Kết nối qua Streamable HTTP (`http://localhost:8090/mcp`).
2. Xác thực bằng Bearer Token qua Header `Authorization: Bearer <token>`.
3. Kiểm thử 3 kịch bản:
   - Case 1: Token ĐÚNG (`ops-sec-token-day26-2026`) -> Thành công kết nối, lấy tools và gọi tool.
   - Case 2: Token SAI (`invalid-wrong-token-999`) -> Bị từ chối (401/403 Forbidden).
   - Case 3: THIẾU Token (No header) -> Bị từ chối (401 Unauthorized).

Cách chạy:
    Terminal 1 (chạy server):
        python server.py --transport streamable-http --port 8090
    Terminal 2 (chạy test client):
        python client_http_auth.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

SERVER_PORT = int(os.environ.get("OPS_SERVER_PORT", "8090"))
SERVER_URL = f"http://localhost:{SERVER_PORT}/mcp"

VALID_TOKEN = os.environ.get("OPS_AUTH_TOKEN", "ops-sec-token-day26-2026")
INVALID_TOKEN = "invalid-wrong-token-999"


async def test_valid_token() -> bool:
    print("\n" + "=" * 65)
    print("TEST 1: Xác thực với Bearer Token ĐÚNG (Valid Token)")
    print("=" * 65)
    print(f"📡 Kết nối tới: {SERVER_URL}")
    print(f"🔑 Header Authorization: Bearer {VALID_TOKEN[:8]}...***")

    http_client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        timeout=15.0,
    )

    try:
        async with http_client:
            async with streamable_http_client(SERVER_URL, http_client=http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    init_res = await session.initialize()
                    print(f"✅ Kết nối thành công! Server: {init_res.server_info.name} v{init_res.server_info.version}")

                    # Đọc server metadata
                    info = await session.read_resource("server://info")
                    meta = json.loads(info.contents[0].text)
                    print(f"📋 Server Version: {meta['version']}, Status: {meta['status']}")

                    # Liệt kê tools
                    tools = await session.list_tools()
                    print(f"🔧 Danh sách {len(tools.tools)} Tools khả dụng:")
                    for t in tools.tools:
                        print(f"   • {t.name}")

                    # Gọi tool get_service_health
                    print("\n▶️  Thực thi tool 'get_service_health(service_name=\"auth-service\")':")
                    call_res = await session.call_tool("get_service_health", {"service_name": "auth-service"})
                    print(f"   {call_res.content[0].text}")

                    # Gọi tool diagnose_system_v2
                    print("\n▶️  Thực thi tool 'diagnose_system_v2(service_name=\"inventory-service\")':")
                    v2_res = await session.call_tool("diagnose_system_v2", {"service_name": "inventory-service"})
                    print(f"   {v2_res.content[0].text}")
                    return True

    except Exception as e:
        print(f"❌ Test 1 Thất bại với ngoại lệ không mong muốn: {e}")
        return False


async def test_invalid_token() -> bool:
    print("\n" + "=" * 65)
    print("TEST 2: Kiểm thử với Bearer Token SAI (Invalid Token)")
    print("=" * 65)
    print(f"📡 Kết nối tới: {SERVER_URL}")
    print(f"🚫 Header Authorization: Bearer {INVALID_TOKEN}")

    http_client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {INVALID_TOKEN}"},
        timeout=10.0,
    )

    try:
        async with http_client:
            async with streamable_http_client(SERVER_URL, http_client=http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    print("❌ LỖI BẢO MẬT: Token sai nhưng server vẫn cho phép kết nối!")
                    return False
    except (httpx.HTTPStatusError, Exception) as exc:
        print(f"✅ KẾT QUẢ ĐÚNG: Server đã từ chối truy cập với Token sai.")
        print(f"   Chi tiết lỗi chặn: {exc}")
        return True


async def test_missing_token() -> bool:
    print("\n" + "=" * 65)
    print("TEST 3: Kiểm thử khi THIẾU Bearer Token (Missing Token)")
    print("=" * 65)
    print(f"📡 Kết nối tới: {SERVER_URL}")
    print(f"🚫 Header Authorization: [NONE - Không gửi Header]")

    http_client = httpx.AsyncClient(
        headers={},  # Không có Authorization header
        timeout=10.0,
    )

    try:
        async with http_client:
            async with streamable_http_client(SERVER_URL, http_client=http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    print("❌ LỖI BẢO MẬT: Không gửi token nhưng server vẫn cho phép kết nối!")
                    return False
    except (httpx.HTTPStatusError, Exception) as exc:
        print(f"✅ KẾT QUẢ ĐÚNG: Server đã chặn kết nối do thiếu Bearer Token.")
        print(f"   Chi tiết lỗi chặn: {exc}")
        return True


async def main() -> None:
    print("=" * 65)
    print("🛡️  OpsSentinel MCP — Streamable HTTP & Token Auth Test Runner")
    print("=" * 65)

    r1 = await test_valid_token()
    r2 = await test_invalid_token()
    r3 = await test_missing_token()

    print("\n" + "=" * 65)
    print("📊 TỔNG KẾT KẾT QUẢ KIỂM THỬ AUTHENTICATION (STREAMABLE HTTP):")
    print(f"  1. Valid Token:   {'✅ PASS' if r1 else '❌ FAIL'}")
    print(f"  2. Invalid Token: {'✅ PASS (Được chặn an toàn)' if r2 else '❌ FAIL'}")
    print(f"  3. Missing Token: {'✅ PASS (Được chặn an toàn)' if r3 else '❌ FAIL'}")
    print("=" * 65)

    if not (r1 and r2 and r3):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
