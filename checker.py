import asyncio
import re
import time
import config

IP_PORT_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})")
IPV6_PORT_RE = re.compile(r"\[([0-9a-fA-F:]+)\]:(\d{1,5})")


def extract_endpoint(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = IPV6_PORT_RE.search(line)
    if m:
        return m.group(1), int(m.group(2))
    m = IP_PORT_RE.search(line)
    if m:
        return m.group(1), int(m.group(2))
    return None


async def check_endpoint(host, port, timeout=config.CHECK_TIMEOUT):
    start = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        elapsed = time.monotonic() - start
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, elapsed
    except Exception:
        elapsed = time.monotonic() - start
        return False, elapsed


async def check_bridge_line(line, semaphore):
    endpoint = extract_endpoint(line)
    if not endpoint:
        return {"line": line, "ok": False, "reason": "no_endpoint", "latency": None}
    host, port = endpoint
    async with semaphore:
        ok, elapsed = await check_endpoint(host, port)
    return {
        "line": line,
        "ok": ok,
        "reason": None if ok else "unreachable",
        "latency": elapsed,
        "host": host,
        "port": port,
    }


async def check_bridges(lines):
    semaphore = asyncio.Semaphore(config.CHECK_CONCURRENCY)
    tasks = [check_bridge_line(line, semaphore) for line in lines]
    results = await asyncio.gather(*tasks)
    return list(results)
