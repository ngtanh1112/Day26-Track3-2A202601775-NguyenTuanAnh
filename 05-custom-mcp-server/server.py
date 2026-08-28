"""OpsSentinel MCP Server — Production Operations & Incident Management.

Mô tả bài toán thực tế:
Hệ thống AI Agent (như Claude Code, Cursor, ADK Agent) trong môi trường production
cần khả năng tự động chẩn đoán sức khỏe vi dịch vụ (Microservices), truy vấn log lỗi,
phân tích nguyên nhân sự cố (Root Cause Analysis), và thực thi runbook xử lý sự cố
một cách an toàn có kiểm soát (Dry-run guardrails), mà không cần cấp quyền root trực tiếp.

Tính năng:
- Hỗ trợ cả 2 phương thức truyền thông: stdio (cho Claude Code local) và streamable-http (cho Agent phân tán).
- Authentication: Xác thực Bearer Token qua Header Authorization.
- Versioning & Backward Compatibility: Cung cấp song song tool v1 (legacy) và tool v2 (nâng cao).
- Server Metadata Resource: Expose resource `server://info` và `server://runbooks`.
- Guided Prompt: Expose prompt `triage-incident` hỗ trợ AI Agent xử lý sự cố chuẩn SOP.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

# ── Cấu hình Server & Metadata ───────────────────────────────────────
SERVER_NAME = "ops-sentinel"
SERVER_VERSION = "2.2.0"
DEFAULT_PORT = int(os.environ.get("OPS_SERVER_PORT", "8090"))
DEFAULT_HOST = os.environ.get("OPS_SERVER_HOST", "0.0.0.0")

# Kho token hợp lệ (Production: Tích hợp OAuth2/JWT/Keycloak/Vault)
VALID_AUTH_TOKENS: dict[str, str] = {
    os.environ.get("OPS_AUTH_TOKEN", "ops-sec-token-day26-2026"): "devops-engineer",
    "ci-cd-token-xyz999": "ci-cd-pipeline",
    "claude-agent-token-888": "claude-code-agent",
}


class OpsTokenVerifier(TokenVerifier):
    """Xác thực Bearer Token cho Streamable HTTP transport."""

    async def verify_token(self, token: str) -> AccessToken | None:
        client_identity = VALID_AUTH_TOKENS.get(token)
        if client_identity is None:
            return None
        return AccessToken(
            token=token,
            client_id=client_identity,
            scopes=["ops:read", "ops:diagnose", "ops:remediate"],
        )


# Khởi tạo MCP Server với Auth Settings
server_instructions = (
    f"{SERVER_NAME} v{SERVER_VERSION} — Hệ thống giám sát, phân tích log sự cố "
    "và thực thi runbook tự động cho Microservices Production. "
    "Hỗ trợ versioning (v1 legacy & v2 modern) và metadata qua resource server://info."
)

mcp = MCPServer(
    SERVER_NAME,
    instructions=server_instructions,
    auth=AuthSettings(
        issuer_url=f"http://{DEFAULT_HOST}:{DEFAULT_PORT}",
        resource_server_url=f"http://{DEFAULT_HOST}:{DEFAULT_PORT}",
    ),
    token_verifier=OpsTokenVerifier(),
)

# ── Dữ liệu Mock chuẩn hoá cho Production Simulation ─────────────────
SERVICES_DB: dict[str, dict[str, Any]] = {
    "auth-service": {
        "status": "HEALTHY",
        "uptime_pct": 99.98,
        "cpu_usage_pct": 24.5,
        "memory_usage_pct": 42.1,
        "p99_latency_ms": 38.2,
        "error_rate_pct": 0.02,
        "active_alerts": 0,
        "dependencies": ["user-db", "redis-session-cache"],
        "region": "ap-southeast-1",
    },
    "payment-gateway": {
        "status": "DEGRADED",
        "uptime_pct": 98.45,
        "cpu_usage_pct": 89.2,
        "memory_usage_pct": 84.7,
        "p99_latency_ms": 1250.0,
        "error_rate_pct": 4.85,
        "active_alerts": 2,
        "dependencies": ["bank-partner-api", "payment-db", "kafka-events"],
        "region": "ap-southeast-1",
    },
    "order-service": {
        "status": "HEALTHY",
        "uptime_pct": 99.95,
        "cpu_usage_pct": 45.0,
        "memory_usage_pct": 58.3,
        "p99_latency_ms": 65.4,
        "error_rate_pct": 0.15,
        "active_alerts": 0,
        "dependencies": ["inventory-service", "payment-gateway", "order-db"],
        "region": "ap-southeast-1",
    },
    "inventory-service": {
        "status": "CRITICAL",
        "uptime_pct": 94.10,
        "cpu_usage_pct": 98.5,
        "memory_usage_pct": 96.2,
        "p99_latency_ms": 4800.0,
        "error_rate_pct": 18.30,
        "active_alerts": 4,
        "dependencies": ["inventory-db", "redis-stock-cache"],
        "region": "ap-southeast-1",
    },
}

LOGS_DB: dict[str, list[dict[str, Any]]] = {
    "payment-gateway": [
        {
            "timestamp": "2026-08-28T16:40:12Z",
            "level": "WARN",
            "trace_id": "tr-pay-8812",
            "message": "Connection pool timeout reaching bank-partner-api (retry 1/3)",
        },
        {
            "timestamp": "2026-08-28T16:42:05Z",
            "level": "ERROR",
            "trace_id": "tr-pay-8845",
            "message": "HTTP 504 Gateway Timeout from bank-partner-api after 3000ms",
        },
        {
            "timestamp": "2026-08-28T16:43:22Z",
            "level": "ERROR",
            "trace_id": "tr-pay-8890",
            "message": "Transaction rollback triggered for txn_id: 9948271. Reason: Partner timeout",
        },
    ],
    "inventory-service": [
        {
            "timestamp": "2026-08-28T16:30:00Z",
            "level": "WARN",
            "trace_id": "tr-inv-1001",
            "message": "Redis cache eviction rate spiked by 340%",
        },
        {
            "timestamp": "2026-08-28T16:35:14Z",
            "level": "ERROR",
            "trace_id": "tr-inv-1044",
            "message": "DB connection exhaustion on inventory-db: active=100/100, waiting=42",
        },
        {
            "timestamp": "2026-08-28T16:36:50Z",
            "level": "CRITICAL",
            "trace_id": "tr-inv-1089",
            "message": "Deadlock detected in inventory_allocation table on SKU-FLASH-SALE-99",
        },
    ],
    "auth-service": [
        {
            "timestamp": "2026-08-28T16:50:00Z",
            "level": "INFO",
            "trace_id": "tr-auth-3011",
            "message": "JWT token issued for user_id: 88124, scope: read_write",
        },
        {
            "timestamp": "2026-08-28T16:52:10Z",
            "level": "INFO",
            "trace_id": "tr-auth-3099",
            "message": "Health check probe OK from k8s-liveness",
        },
    ],
}

INCIDENTS_DB: dict[str, dict[str, Any]] = {
    "INC-2026-001": {
        "title": "High Latency and Timeout on Payment Gateway",
        "service": "payment-gateway",
        "severity": "HIGH",
        "status": "INVESTIGATING",
        "created_at": "2026-08-28T16:35:00Z",
        "summary": "Payment requests are facing 504 timeouts due to upstream partner latency.",
        "root_cause_analysis": {
            "primary_cause": "Upstream bank partner API experiencing degraded network connectivity in ap-southeast region.",
            "blast_radius": "4.85% checkout failures on e-commerce frontend.",
            "impacted_components": ["payment-gateway", "order-service", "checkout-flow"],
        },
        "remediation_playbook": [
            "1. Bật Circuit Breaker cho bank-partner-api để fallback sang cổng thanh toán phụ.",
            "2. Flush và refresh cache token kết nối.",
            "3. Tạm thời tăng replica của payment-gateway từ 3 lên 6 pods.",
        ],
    },
    "INC-2026-002": {
        "title": "Database Connection Saturation and Lock Contention on Inventory",
        "service": "inventory-service",
        "severity": "CRITICAL",
        "status": "ACTION_REQUIRED",
        "created_at": "2026-08-28T16:30:00Z",
        "summary": "Flash sale flash-traffic exhausted connection pool causing deadlocks.",
        "root_cause_analysis": {
            "primary_cause": "Cache miss storm on Redis leading to direct read/write locks on MySQL primary instance.",
            "blast_radius": "18.3% stock check failures for flash-sale SKUs.",
            "impacted_components": ["inventory-service", "inventory-db", "cart-checkout"],
        },
        "remediation_playbook": [
            "1. Thực hiện warm-up lại Redis stock cache.",
            "2. Tăng pool size cho inventory-db từ 100 lên 200 connections.",
            "3. Kích hoạt rate limiter ở API Gateway cho route /api/v1/inventory/reserve.",
        ],
    },
}


# ═════════════════════════════════════════════════════════════════════
# 1. MCP RESOURCES & PROMPTS
# ═════════════════════════════════════════════════════════════════════

@mcp.resource("server://info")
def server_info() -> str:
    """Metadata toàn diện của OpsSentinel MCP Server — dùng cho discovery và version validation."""
    payload = {
        "name": SERVER_NAME,
        "version": SERVER_VERSION,
        "protocol_version": "2024-11-05",
        "status": "OPERATIONAL",
        "description": "DevOps & Incident Investigation MCP Server with Versioning and Token Authentication",
        "capabilities": {
            "tools": True,
            "resources": True,
            "prompts": True,
            "logging": True,
        },
        "active_tools": [
            "get_service_health",
            "query_service_logs",
            "diagnose_system_v2",
            "investigate_incident_v2",
            "execute_remediation",
        ],
        "deprecated_tools": [
            {
                "tool": "diagnose_system_v1",
                "deprecated_since": "2.0.0",
                "recommended_replacement": "diagnose_system_v2",
                "eol_date": "2026-12-31",
            },
            {
                "tool": "investigate_incident_v1",
                "deprecated_since": "2.0.0",
                "recommended_replacement": "investigate_incident_v2",
                "eol_date": "2026-12-31",
            },
        ],
        "migration_guide": {
            "diagnose_system": "Sử dụng diagnose_system_v2 để nhận cấu trúc JSON chi tiết, dependency graph và latency p99.",
            "investigate_incident": "Sử dụng investigate_incident_v2 để nhận báo cáo Root Cause Analysis (RCA) và remediation playbook.",
        },
        "system_time": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


@mcp.resource("server://runbooks")
def operational_runbooks() -> str:
    """Sổ tay quy trình phản ứng sự cố (Incident Response SOP & Runbooks)."""
    runbooks = {
        "restart_service": "Graceful pod rolling restart with zero-downtime drain.",
        "clear_cache": "Invalidate Redis key patterns or flush namespace.",
        "scale_up": "Increase HPA minimum replicas to absorb traffic surges.",
        "toggle_circuit_breaker": "Trip circuit breaker to fallback partner gateway.",
    }
    return json.dumps(runbooks, indent=2, ensure_ascii=False)


@mcp.prompt("triage-incident")
def triage_incident_prompt(incident_id: str) -> str:
    """Prompt template chuẩn hóa hướng dẫn Agent điều tra sự cố production."""
    return (
        f"Bạn là Chuyên gia DevOps / SRE đang trực chiến incident {incident_id}.\n"
        f"Hãy thực hiện tuần tự các bước sau:\n"
        f"1. Đọc metadata server qua resource `server://info`.\n"
        f"2. Sử dụng tool `investigate_incident_v2` với incident_id='{incident_id}' để thu thập RCA.\n"
        f"3. Dùng `query_service_logs` để trích xuất error logs liên quan.\n"
        f"4. Đánh giá rủi ro và đề xuất hành động trong `execute_remediation` (ở chế độ dry_run=True trước).\n"
        f"5. Báo cáo tóm tắt tình hình, nguyên nhân cốt lõi và các bước khắc phục."
    )


# ═════════════════════════════════════════════════════════════════════
# 2. MCP TOOLS
# ═════════════════════════════════════════════════════════════════════

@mcp.tool()
def get_service_health(service_name: str, region: str = "ap-southeast-1") -> str:
    """Tra cứu trạng thái vận hành thời gian thực (Health, CPU, RAM, Latency p99, Error Rate) của vi dịch vụ.

    Args:
        service_name: Tên microservice (ví dụ: auth-service, payment-gateway, order-service, inventory-service)
        region: Vùng triển khai đám mây (mặc định: ap-southeast-1)
    """
    svc = SERVICES_DB.get(service_name.lower())
    if not svc:
        available = list(SERVICES_DB.keys())
        return json.dumps(
            {
                "error": f"Service '{service_name}' không tồn tại.",
                "available_services": available,
                "status": "NOT_FOUND",
            },
            ensure_ascii=False,
        )

    result = {
        "service": service_name,
        "region": region,
        "status": svc["status"],
        "uptime_percentage": svc["uptime_pct"],
        "cpu_usage_pct": svc["cpu_usage_pct"],
        "memory_usage_pct": svc["memory_usage_pct"],
        "p99_latency_ms": svc["p99_latency_ms"],
        "error_rate_pct": svc["error_rate_pct"],
        "active_alerts": svc["active_alerts"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def query_service_logs(
    service_name: str,
    level: str = "ERROR",
    limit: int = 5,
    search_keyword: str | None = None,
) -> str:
    """Truy vấn structured application logs theo level (INFO, WARN, ERROR, CRITICAL) và từ khóa.

    Args:
        service_name: Tên dịch vụ cần lấy log (ví dụ: payment-gateway, inventory-service, auth-service)
        level: Cấp độ log tối thiểu cần lọc (INFO, WARN, ERROR, CRITICAL). Mặc định: ERROR.
        limit: Số lượng bản ghi tối đa cần trả về (1 đến 50, mặc định: 5).
        search_keyword: Từ khóa tùy chọn để lọc nội dung log message.
    """
    logs = LOGS_DB.get(service_name.lower(), [])
    if not logs:
        return json.dumps(
            {"service": service_name, "logs_count": 0, "logs": [], "message": "Không tìm thấy bản ghi log nào."},
            ensure_ascii=False,
        )

    filtered = []
    for entry in logs:
        if search_keyword and search_keyword.lower() not in entry["message"].lower():
            continue
        filtered.append(entry)

    limited = filtered[: max(1, min(limit, 50))]
    return json.dumps(
        {
            "service": service_name,
            "filter_level": level,
            "matched_count": len(limited),
            "logs": limited,
        },
        indent=2,
        ensure_ascii=False,
    )


# ── VERSIONING MINH HOẠ: TOOL V1 (LEGACY) VS TOOL V2 (MODERN) ─────────

@mcp.tool()
def diagnose_system_v1(service_name: str) -> str:
    """[v1 LEGACY] Kiểm tra nhanh tình trạng hệ thống — Trả chuỗi text đơn giản. Deprecated: dùng diagnose_system_v2."""
    svc = SERVICES_DB.get(service_name.lower())
    if not svc:
        return f"[v1] {service_name}: KHÔNG TÌM THẤY DỊCH VỤ"
    return f"[v1] {service_name}: Trạng thái={svc['status']}, CPU={svc['cpu_usage_pct']}%, RAM={svc['memory_usage_pct']}%, Cảnh báo={svc['active_alerts']}"


@mcp.tool()
def diagnose_system_v2(
    service_name: str,
    include_metrics: bool = True,
    include_dependency_graph: bool = True,
    format: str = "json",
) -> str:
    """[v2 MODERN] Chẩn đoán chuyên sâu vi dịch vụ — Trả JSON giàu dữ liệu với dependency graph và health score.

    Args:
        service_name: Tên vi dịch vụ (auth-service, payment-gateway, inventory-service, order-service)
        include_metrics: Có bao gồm metrics chi tiết CPU/RAM/p99 latency không (mặc định: True)
        include_dependency_graph: Có đính kèm danh sách vi dịch vụ phụ thuộc không (mặc định: True)
        format: Định dạng trả về ('json' hoặc 'markdown', mặc định: 'json')
    """
    svc = SERVICES_DB.get(service_name.lower())
    if not svc:
        return json.dumps(
            {"api_version": "2.2.0", "service": service_name, "error": "Service not found"},
            ensure_ascii=False,
        )

    # Tính toán Health Score từ 0 - 100
    penalty = (svc["error_rate_pct"] * 2.5) + (svc["cpu_usage_pct"] > 80) * 20 + (svc["memory_usage_pct"] > 80) * 20
    health_score = max(0.0, round(100.0 - penalty, 1))

    report: dict[str, Any] = {
        "api_version": "2.2.0",
        "service": service_name,
        "health_score": health_score,
        "status": svc["status"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if include_metrics:
        report["metrics"] = {
            "uptime_percentage": svc["uptime_pct"],
            "cpu_usage_pct": svc["cpu_usage_pct"],
            "memory_usage_pct": svc["memory_usage_pct"],
            "p99_latency_ms": svc["p99_latency_ms"],
            "error_rate_pct": svc["error_rate_pct"],
            "active_alerts": svc["active_alerts"],
        }

    if include_dependency_graph:
        report["dependencies"] = {
            "downstream_services": svc.get("dependencies", []),
            "blast_radius_risk": "HIGH" if svc["status"] == "CRITICAL" else ("MEDIUM" if svc["status"] == "DEGRADED" else "LOW"),
        }

    if format == "markdown":
        md = f"### Chẩn đoán Dịch vụ: `{service_name}` (v2.2.0)\n"
        md += f"- **Trạng thái:** `{report['status']}` (Health Score: {report['health_score']}/100)\n"
        if include_metrics:
            md += f"- **CPU / RAM:** {svc['cpu_usage_pct']}% / {svc['memory_usage_pct']}%\n"
            md += f"- **p99 Latency:** {svc['p99_latency_ms']}ms | **Error Rate:** {svc['error_rate_pct']}%\n"
        if include_dependency_graph:
            md += f"- **Dependencies:** {', '.join(svc.get('dependencies', []))}\n"
        return md

    return json.dumps(report, indent=2, ensure_ascii=False)


@mcp.tool()
def investigate_incident_v1(incident_id: str) -> str:
    """[v1 LEGACY] Tra cứu sự cố cơ bản — Trả chuỗi text tóm tắt. Deprecated: dùng investigate_incident_v2."""
    inc = INCIDENTS_DB.get(incident_id.upper())
    if not inc:
        return f"[v1] Sự cố {incident_id} không tồn tại."
    return f"[v1] {incident_id} ({inc['severity']}): {inc['title']} - Dịch vụ: {inc['service']} - Trạng thái: {inc['status']}"


@mcp.tool()
def investigate_incident_v2(
    incident_id: str,
    include_root_cause_analysis: bool = True,
    include_remediation_steps: bool = True,
) -> str:
    """[v2 MODERN] Báo cáo chi tiết sự cố Production — Phân tích nguyên nhân cốt lõi (RCA) và Runbook khắc phục.

    Args:
        incident_id: Mã định danh sự cố (ví dụ: INC-2026-001, INC-2026-002)
        include_root_cause_analysis: Bao gồm phân tích nguyên nhân cốt lõi và blast radius (mặc định: True)
        include_remediation_steps: Đính kèm các bước xử lý theo Playbook (mặc định: True)
    """
    inc = INCIDENTS_DB.get(incident_id.upper())
    if not inc:
        return json.dumps(
            {
                "api_version": "2.2.0",
                "incident_id": incident_id,
                "error": "Incident not found",
                "known_incidents": list(INCIDENTS_DB.keys()),
            },
            ensure_ascii=False,
        )

    result: dict[str, Any] = {
        "api_version": "2.2.0",
        "incident_id": incident_id.upper(),
        "title": inc["title"],
        "service": inc["service"],
        "severity": inc["severity"],
        "status": inc["status"],
        "summary": inc["summary"],
        "created_at": inc["created_at"],
    }

    if include_root_cause_analysis:
        result["root_cause_analysis"] = inc.get("root_cause_analysis", {})

    if include_remediation_steps:
        result["remediation_playbook"] = inc.get("remediation_playbook", [])

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def execute_remediation(
    service_name: str,
    action: str,
    dry_run: bool = True,
    reason: str = "Automated AI Incident Mitigation",
) -> str:
    """Thực thi hành động khắc phục sự cố (Runbook Remediation) với chốt an toàn dry_run.

    Args:
        service_name: Tên dịch vụ mục tiêu (ví dụ: payment-gateway, inventory-service)
        action: Hành động cần chạy ('restart_service', 'clear_cache', 'scale_up', 'toggle_circuit_breaker')
        dry_run: Nếu True, chỉ mô phỏng tác động và kiểm tra tính hợp lệ mà không thay đổi hệ thống thật. Mặc định: True.
        reason: Lý do thực hiện can thiệp hệ thống.
    """
    valid_actions = ["restart_service", "clear_cache", "scale_up", "toggle_circuit_breaker"]
    if action not in valid_actions:
        return json.dumps(
            {
                "success": False,
                "error": f"Hành động '{action}' không hợp lệ.",
                "allowed_actions": valid_actions,
            },
            ensure_ascii=False,
        )

    if service_name.lower() not in SERVICES_DB:
        return json.dumps(
            {"success": False, "error": f"Service '{service_name}' không tồn tại trong hệ thống."},
            ensure_ascii=False,
        )

    response = {
        "action": action,
        "target_service": service_name,
        "dry_run": dry_run,
        "reason": reason,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }

    if dry_run:
        response.update({
            "status": "SIMULATED_SUCCESS",
            "message": f"Mô phỏng thành công hành động '{action}' trên dịch vụ '{service_name}'. Không có thay đổi thực tế.",
            "estimated_impact": "Dịch vụ sẽ khôi phục về trạng thái HEALTHY trong vòng ~30s sau khi thực thi thật.",
        })
    else:
        # Giả lập thực thi thật
        svc = SERVICES_DB[service_name.lower()]
        svc["status"] = "HEALTHY"
        svc["active_alerts"] = 0
        svc["cpu_usage_pct"] = 35.0
        svc["memory_usage_pct"] = 48.0
        svc["error_rate_pct"] = 0.01
        response.update({
            "status": "APPLIED_SUCCESS",
            "message": f"Đã áp dụng thành công hành động '{action}' trên dịch vụ '{service_name}'. Trạng thái mới: HEALTHY.",
            "service_new_status": svc,
        })

    return json.dumps(response, indent=2, ensure_ascii=False)


# ═════════════════════════════════════════════════════════════════════
# 3. ENTRYPOINT & RUNNER
# ═════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Khởi chạy OpsSentinel MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Phương thức truyền thông MCP (mặc định: stdio)",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host cho HTTP server (mặc định: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port cho HTTP server (mặc định: {DEFAULT_PORT})")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.transport in ["streamable-http", "sse"]:
        print(f"🛡️  [OpsSentinel] Đang khởi chạy MCP Server qua Streamable HTTP trên http://{args.host}:{args.port}/mcp")
        print(f"🔒 [Auth] Yêu cầu Bearer Token xác thực trong Header.")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        # Chế độ stdio
        mcp.run()
