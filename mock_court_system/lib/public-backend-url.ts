/**
 * 浏览器内打开「后端 Swagger」等链接时使用（与 Next 服务端代理用的 BACKEND_URL 一致时可同值）。
 * 在 .env.local 中设置 NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
 */
export const PUBLIC_BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"
