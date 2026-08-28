"""OpsSentinel MCP Client (stdio transport).

Minh họa mức độ Khó (Hard Level):
1. Kết nối tới server qua stdio.
2. Đọc server metadata qua Resource `server://info` trước khi gọi tool để kiểm tra version & deprecation.
3. Liệt kê toàn bộ tools, prompts, resources.
4. Gọi tool v1 (legacy) — vẫn hoạt động tốt (Backward compatibility).
5. Gọi tool v2 (modern) — nhận dữ liệu JSON chi tiết, health score, dependency graph.
6. Gọi tool chẩn đoán log và runbook remediation với dry-run guardrails.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = str(Path(__file__).parent / "server.py")


async def main() -> None:
    print("=" * 70)
    print("🛡️  OpsSentinel MCP Client — Stdio Mode & Metadata Inspection")
    print("=" * 70)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT, "--transport", "stdio"],
        env=dict(os.environ),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. Initialize session
            print("\n[1] 🔌 Khởi tạo phiên kết nối MCP Session...")
            init_result = await session.initialize()
            print(f"    ✅ Đã kết nối tới Server: {init_result.server_info.name} (Protocol: {init_result.protocol_version})")

            # 2. Đọc Metadata từ server://info trước khi gọi tool (Hard requirement)
            print("\n[2] 📋 Đọc Server Metadata qua Resource 'server://info':")
            info_resource = await session.read_resource("server://info")
            server_meta = json.loads(info_resource.contents[0].text)
            print(f"    • Tên server: {server_meta['name']}")
            print(f"    • Phiên bản: v{server_meta['version']}")
            print(f"    • Trạng thái: {server_meta['status']}")
            print(f"    • Deprecated tools: {server_meta['deprecated_tools']}")
            print(f"    • Hướng dẫn chuyển đổi (Migration Guide):")
            for k, v in server_meta['migration_guide'].items():
                print(f"      - {k}: {v}")

            # 3. Khám phá danh sách Tools
            print("\n[3] 🔧 Khám phá danh sách Tools công bố bởi Server:")
            tools_list = await session.list_tools()
            for tool in tools_list.tools:
                print(f"    • [{tool.name}]: {tool.description.splitlines()[0] if tool.description else ''}")

            # 4. Kiểm tra Backward Compatibility — Gọi Tool v1 (Legacy)
            print("\n[4] 🔄 Gọi Tool v1 Legacy (Backward Compatibility):")
            res_v1 = await session.call_tool("diagnose_system_v1", {"service_name": "payment-gateway"})
            print(f"    Output: {res_v1.content[0].text}")

            # 5. Gọi Tool v2 Modern — Nhận dữ liệu phong phú
            print("\n[5] 🚀 Gọi Tool v2 Modern (Rich JSON, Health Score, Dependency Graph):")
            res_v2 = await session.call_tool(
                "diagnose_system_v2",
                {
                    "service_name": "payment-gateway",
                    "include_metrics": True,
                    "include_dependency_graph": True,
                    "format": "json",
                },
            )
            v2_data = json.loads(res_v2.content[0].text)
            print(f"    Output (Formatted JSON):")
            print(json.dumps(v2_data, indent=6, ensure_ascii=False))

            # 6. Điều tra Incident qua Tool v2 & Lấy Logs
            print("\n[6] 🔍 Điều tra sự cố INC-2026-001 qua 'investigate_incident_v2':")
            inc_res = await session.call_tool("investigate_incident_v2", {"incident_id": "INC-2026-001"})
            inc_data = json.loads(inc_res.content[0].text)
            print(f"    • Tiêu đề: {inc_data.get('title')}")
            print(f"    • Mức độ: {inc_data.get('severity')}")
            print(f"    • Nguyên nhân cốt lõi (RCA): {inc_data.get('root_cause_analysis', {}).get('primary_cause')}")

            # 7. Thực thi Runbook Remediation với Chốt an toàn Dry-run
            print("\n[7] ⚙️  Mô phỏng thực thi Runbook khắc phục sự cố (dry_run=True):")
            remedy_res = await session.call_tool(
                "execute_remediation",
                {
                    "service_name": "payment-gateway",
                    "action": "toggle_circuit_breaker",
                    "dry_run": True,
                    "reason": "Mitigate 504 gateway timeout from upstream bank partner",
                },
            )
            remedy_data = json.loads(remedy_res.content[0].text)
            print(f"    • Trạng thái mô phỏng: {remedy_data.get('status')}")
            print(f"    • Chi tiết: {remedy_data.get('message')}")
            print(f"    • Tác động dự kiến: {remedy_data.get('estimated_impact')}")

    print("\n" + "=" * 70)
    print("✅ Hoàn thành toàn bộ kịch bản kiểm thử Stdio & Versioning!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
