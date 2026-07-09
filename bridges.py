import json
import aiohttp
import config

TRANSPORTS = ["obfs4", "vanilla", "meek-azure", "snowflake"]

TRANSPORT_TITLES = {
    "obfs4": "obfs4",
    "vanilla": "Vanilla (без обфускации)",
    "meek-azure": "meek-azure",
    "snowflake": "snowflake",
}


async def fetch_builtin_bridges():
    headers = {
        "Content-Type": "application/vnd.api+json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(config.MOAT_BUILTIN_URL, timeout=15) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    return data


async def fetch_bridges_for_country(country_code="RU"):
    headers = {
        "Content-Type": "application/vnd.api+json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    payload = {
        "data": [
            {
                "type": "client-transports",
                "id": "1",
                "attributes": {
                    "country": country_code,
                    "transports": TRANSPORTS,
                },
            }
        ]
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(
            config.MOAT_SETTINGS_URL, data=json.dumps(payload), timeout=15
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    return data


def extract_bridge_lines(moat_response):
    result = {}
    try:
        settings = moat_response["data"][0]["attributes"]["settings"]
    except (KeyError, IndexError, TypeError):
        settings = []
    for entry in settings:
        bridges = entry.get("bridges", {})
        transport = bridges.get("type")
        lines = bridges.get("bridge_strings", [])
        if not transport or not lines:
            continue
        result.setdefault(transport, [])
        result[transport].extend(lines)
    return result


def extract_builtin_lines(builtin_response):
    result = {}
    for transport, lines in builtin_response.items():
        if isinstance(lines, list) and lines:
            result[transport] = lines
    return result


async def get_bridges(transport):
    collected = {}
    try:
        builtin = await fetch_builtin_bridges()
        collected.update(extract_builtin_lines(builtin))
    except Exception:
        pass

    if transport not in collected or not collected.get(transport):
        try:
            settings = await fetch_bridges_for_country("RU")
            fetched = extract_bridge_lines(settings)
            for k, v in fetched.items():
                collected.setdefault(k, [])
                collected[k].extend(v)
        except Exception:
            pass

    lines = collected.get(transport, [])
    seen = set()
    unique_lines = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)
    return unique_lines
