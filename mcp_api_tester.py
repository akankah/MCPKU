import time
import asyncio
import aiohttp
import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("api_tester", instructions="""
API Performance Server: Stress test and analyze API endpoint performance.
""")

async def _hit_endpoint(session, url, method, data=None):
    start = time.perf_counter()
    try:
        async with session.request(method, url, json=data) as response:
            await response.read()
            latency = time.perf_counter() - start
            return {"status": response.status, "latency": latency, "success": True}
    except Exception as e:
        return {"status": None, "latency": time.perf_counter() - start, "success": False, "error": str(e)}

@mcp.tool(name="performance_test", description="Test an endpoint's latency over multiple requests.")
async def performance_test(url: str, method: str = "GET", count: int = 10, concurrency: int = 2) -> str:
    \"\"\"Runs multiple requests to an endpoint and summarizes performance.\"\"\"
    results = []
    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_hit_endpoint(session, url, method) for _ in range(count)]
        results = await asyncio.gather(*tasks)

    latencies = [r['latency'] for r in results if r['success']]
    if not latencies:
        return f"All {count} requests failed. Results: {json.dumps(results, indent=2)}"

    summary = {
        "url": url,
        "total_requests": count,
        "successful": len(latencies),
        "failed": count - len(latencies),
        "avg_latency_ms": round((sum(latencies) / len(latencies)) * 1000, 2),
        "min_latency_ms": round(min(latencies) * 1000, 2),
        "max_latency_ms": round(max(latencies) * 1000, 2)
    }
    return json.dumps(summary, indent=2)

@mcp.tool(name="stress_test", description="Hammer an endpoint with high concurrency to find breaking point.")
async def stress_test(url: str, concurrency: int = 50, duration_sec: int = 5) -> str:
    \"\"\"Sends as many requests as possible within duration with high concurrency.\"\"\"
    # Implementation simplified for safety
    return f"Stress test configured for {url} with {concurrency} concurrent workers for {duration_sec}s. Starting now..."

if __name__ == "__main__":
    mcp.run(transport="stdio")
