import os
import requests

GITHUB_TOKEN: str = os.environ.get("GITHUB_API_KEY", "")
API_BASE: str = "https://api.github.com"


def _headers() -> dict[str, str]:
    h: dict[str, str] = {
        "User-Agent": "mcp-github-server",
        "Accept": "application/vnd.github.v3+json",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _api(method: str, path: str, **kwargs) -> dict:
    url = f"{API_BASE}{path}"
    req_kwargs = {"headers": _headers(), "timeout": 15}
    if method in ("post", "patch", "put") and "data" in kwargs:
        req_kwargs["json"] = kwargs.pop("data")
    if "params" in kwargs:
        req_kwargs["params"] = kwargs.pop("params")
    try:
        r = requests.request(method, url, **req_kwargs)
        r.raise_for_status()
        if method == "delete" and r.status_code == 204:
            return {"deleted": True}
        return r.json()
    except requests.exceptions.HTTPError as e:
        body = e.response.text[:300]
        return {"error": f"HTTP {e.response.status_code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def _get(path: str, params: dict | None = None) -> dict:
    return _api("get", path, params=params)


def _post(path: str, data: dict | None = None) -> dict:
    return _api("post", path, data=data)


def _patch(path: str, data: dict) -> dict:
    return _api("patch", path, data=data)


def _put(path: str, data: dict | None = None) -> dict:
    return _api("put", path, data=data)


def _delete(path: str) -> dict:
    return _api("delete", path)


def _format_repo(r: dict) -> str:
    return (
        f"Name: {r.get('full_name')}\n"
        f"Description: {r.get('description', '')}\n"
        f"Stars: {r.get('stargazers_count')} | Forks: {r.get('forks_count')} | Language: {r.get('language')}\n"
        f"URL: {r.get('html_url')}\n"
        f"Topics: {', '.join(r.get('topics', []))}\n"
        f"Created: {r.get('created_at')} | Updated: {r.get('updated_at')}"
    )


def _graphql(query: str) -> dict:
    headers = _headers()
    headers["Accept"] = "application/vnd.github.v4+json"
    try:
        r = requests.post(f"{API_BASE}/graphql", headers=headers, json={"query": query}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)[:200]}