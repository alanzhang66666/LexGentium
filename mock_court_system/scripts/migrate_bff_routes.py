"""Codemod: migrate app/api/**/route.ts from backendFetch to shared proxies.

Transforms the common shapes:
- backendFetch(path, {opts})            -> proxyJson(request, {path, opts})
- custom SSE fetch blocks               -> proxySse(request, {path, method:"POST"})
- body: await request.json() / parsed    -> dropped (proxy forwards raw bytes)
- _request params                        -> renamed to request

Files that don't match a clean shape are reported for manual migration.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app" / "api"

FETCH_CALL = re.compile(
    r"backendFetch\(\s*(?P<path>`[^`]*`|\"[^\"]*\"|'[^']*'|/[^,]*?/)\s*,\s*\{(?P<opts>.*?)\}\s*,?\s*\)",
    re.S,
)


def _clean_opts(opts: str) -> str:
    lines = []
    for line in opts.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("body:", "request,", "request:", "timeoutMessage:")):
            continue
        lines.append(stripped.rstrip(","))
    return ", ".join(lines)


def _rewrite_fetch_calls(text: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match) -> str:
        nonlocal count
        count += 1
        path = match.group("path")
        opts = _clean_opts(match.group("opts"))
        inner = f"path: {path}"
        if opts:
            inner += f", {opts}"
        return f"proxyJson(request, {{{inner}}})"

    return FETCH_CALL.sub(repl, text), count


def _fix_signatures(text: str) -> str:
    # Handlers that ignore the request object must take `request` for the proxy.
    text = text.replace("_request: Request", "request: Request")
    text = text.replace("_request: NextRequest", "request: NextRequest")
    # Zero-arg handlers gain the request parameter.
    text = re.sub(
        r"export async function (GET|HEAD)\(\s*\)",
        r"export async function \1(request: Request)",
        text,
    )
    return text


def _fix_imports(text: str, uses_sse: bool) -> str:
    # Drop backendFetch/parseJsonBody imports, add proxy imports.
    text = re.sub(r'import\s*\{[^}]*\}\s*from\s*"@/lib/backend-fetch"\n?', "", text)
    text = re.sub(r'import\s*\{[^}]*\}\s*from\s*"@/lib/backend-proxy"\n?', "", text)
    text = re.sub(r'import\s*\{[^}]*\}\s*from\s*"@/lib/backend-stream"\n?', "", text)
    imports = 'import { proxyJson } from "@/lib/backend-proxy"\n'
    if uses_sse:
        imports += 'import { proxySse } from "@/lib/backend-stream"\n'
    # Insert after the last import line, or at top.
    lines = text.splitlines(keepends=True)
    last_import = -1
    for i, line in enumerate(lines):
        if line.lstrip().startswith("import "):
            last_import = i
    lines.insert(last_import + 1 if last_import >= 0 else 0, imports)
    return "".join(lines)


def _remove_parsejson_preamble(text: str) -> str:
    text = re.sub(
        r"\s*const parsed = await parseJsonBody\(request\)\s*\n\s*if \(!parsed\.ok\) return parsed\.response\s*\n",
        "\n",
        text,
    )
    text = re.sub(r"const body = await request\.json\(\)\s*\n", "", text)
    text = re.sub(r"const body = await request\.json\(\)\.catch\(\(\) => \(\{\}\)\)\s*\n", "", text)
    return text


def migrate_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    original = text

    uses_sse = "text/event-stream" in text or "stream" in path.name and "backendResponse.body" in text

    text = _remove_parsejson_preamble(text)
    text, n = _rewrite_fetch_calls(text)
    text = _fix_signatures(text)
    text = _fix_imports(text, uses_sse)

    leftovers = []
    if "backendFetch(" in text or "parseJsonBody(" in text or "BACKEND_URL" in text:
        leftovers.append("residual backendFetch/BACKEND_URL")
    if n == 0 and "fetch(" not in original:
        leftovers.append("no backendFetch call rewritten")

    if leftovers:
        return f"MANUAL: {path.relative_to(ROOT)} — {', '.join(leftovers)}"

    path.write_text(text, encoding="utf-8")
    return f"OK: {path.relative_to(ROOT)}"


def main() -> int:
    routes = sorted(ROOT.rglob("route.ts"))
    for route in routes:
        print(migrate_file(route))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
