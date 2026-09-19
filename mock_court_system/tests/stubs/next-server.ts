/**
 * Minimal `next/server` stub for the release vitest suite.
 *
 * The repo's node_modules contains a stripped `next` package (no
 * package.json / `next/server` entry), so unit tests that exercise BFF
 * helpers alias this stub instead. It implements only what the BFF
 * helpers use: `NextResponse` / `NextResponse.json` / `NextRequest`.
 */

export class NextResponse extends Response {
  static json(body: unknown, init: ResponseInit = {}): NextResponse {
    const headers = new Headers(init.headers)
    if (!headers.has("content-type")) {
      headers.set("content-type", "application/json")
    }
    return new NextResponse(JSON.stringify(body), { ...init, headers })
  }
}

export class NextRequest extends Request {}
