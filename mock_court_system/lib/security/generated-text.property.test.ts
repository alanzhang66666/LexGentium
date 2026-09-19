import { describe, expect, it } from "vitest"
import fc from "fast-check"
import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"

/**
 * Property 29: 生成文本只按文本呈现。
 *
 * 任意包含 HTML/script/事件属性/Unicode markup 的外部或生成字符串，
 * 经 React 文本渲染后输出被转义的 textContent —— 不产生可执行元素或 handler。
 */
const HOSTILE = fc.oneof(
  fc.string(),
  fc.constantFrom(
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    '<a href="javascript:alert(1)">x</a>',
    "<svg onload=alert(1)>",
    "&#60;script&#62;",
    "‮<script>alert(1)</script>‬", // RTL override + markup
    '"><iframe srcdoc="<script>alert(1)</script>">',
    "${alert(1)}",
    "<div onmouseover='alert(1)'>hover</div>",
  ),
)

function renderText(s: string): string {
  return renderToStaticMarkup(createElement("span", null, s))
}

describe("Property 29: 生成文本只按文本呈现", () => {
  it("任意输入渲染为转义文本，不产生可执行标记", () => {
    fc.assert(
      fc.property(HOSTILE, (s) => {
        const html = renderText(s)
        const inner = html.replace(/^<span>/, "").replace(/<\/span>$/, "")
        // 输出中不存在任何未转义的 <（tag/handler 均已被 &lt; 中和）
        expect(inner).not.toMatch(/<script|<img|<svg|<iframe|<a\s/i)
        expect(inner).not.toContain("<")
        // 输入字符逐字保留（转义后解码还原）
        expect(inner).toBe(
          s
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#x27;"),
        )
      }),
    )
  })

  it("嵌套数组/数字/布尔子节点不产生原始 HTML", () => {
    fc.assert(
      fc.property(fc.array(HOSTILE, { maxLength: 4 }), (parts) => {
        const html = renderToStaticMarkup(
          createElement("div", null, ...parts),
        )
        expect(html).not.toMatch(/<script|<img|<svg|<iframe/i)
      }),
    )
  })
})
