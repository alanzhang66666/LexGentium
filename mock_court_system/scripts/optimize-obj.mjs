#!/usr/bin/env node

/**
 * Rebuild a supplier character OBJ for /hearing-3d.
 *
 * PR #7's compact files used a whole-body grid around 1.5 cm and kept the
 * unused UV table. That erased facial topology and left 19 MiB of dead `vt`
 * lines. This pass keeps a finer grid on the head, a coarser grid on the body,
 * writes only referenced UVs, and enables smoothing (`s 1`).
 *
 * Numbers stay aligned with `components/hearing-3d/obj-optimize.ts`.
 */
import fs from "node:fs"
import path from "node:path"

const HEAD_RATIO = 0.17
const HEAD_CELL = 0.0036
const BODY_CELL = 0.0165

const [input, output, ...flags] = process.argv.slice(2)
if (!input || !output) {
  console.error("usage: optimize-obj.mjs input.obj output.obj [--head-cell=0.0036] [--body-cell=0.0165] [--head-ratio=0.17]")
  process.exit(2)
}

const options = { headCell: HEAD_CELL, bodyCell: BODY_CELL, headRatio: HEAD_RATIO }
for (const flag of flags) {
  const [key, value] = flag.replace(/^--/, "").split("=")
  if (key === "head-cell") options.headCell = Number(value)
  if (key === "body-cell") options.bodyCell = Number(value)
  if (key === "head-ratio") options.headRatio = Number(value)
}
if (![options.headCell, options.bodyCell, options.headRatio].every((value) => Number.isFinite(value) && value > 0)) {
  throw new Error("invalid optimizer flag")
}

const raw = fs.readFileSync(input, "utf8")
const lines = raw.split(/\r?\n/)

const vertices = []
const uvs = []
const faces = []
const headers = []
let minY = Number.POSITIVE_INFINITY
let maxY = Number.NEGATIVE_INFINITY

for (const rawLine of lines) {
  const line = rawLine.trim()
  if (!line) continue
  if (line.startsWith("v ")) {
    const parts = line.split(/\s+/)
    const y = Number(parts[2])
    vertices.push({ text: `${parts[1]} ${parts[2]} ${parts[3]}`, x: Number(parts[1]), y, z: Number(parts[3]) })
    if (y < minY) minY = y
    if (y > maxY) maxY = y
    continue
  }
  if (line.startsWith("vt ")) {
    uvs.push(line.slice(3).trim())
    continue
  }
  if (line.startsWith("f ")) {
    faces.push(line.slice(2).trim())
    continue
  }
  if (line.startsWith("vn ")) continue
  if (line.startsWith("s ")) continue
  headers.push(line)
}

const threshold = minY + (1 - options.headRatio) * (maxY - minY)
const remap = new Array(vertices.length + 1)
const clusterByKey = new Map()
const reduced = []

for (let index = 0; index < vertices.length; index += 1) {
  const vertex = vertices[index]
  const cell = vertex.y >= threshold ? options.headCell : options.bodyCell
  const key = `${Math.round(vertex.x / cell)}:${Math.round(vertex.y / cell)}:${Math.round(vertex.z / cell)}`
  let reducedIndex = clusterByKey.get(key)
  if (reducedIndex === undefined) {
    reducedIndex = reduced.length + 1
    clusterByKey.set(key, reducedIndex)
    reduced.push(vertex.text)
  }
  remap[index + 1] = reducedIndex
}

const usedUvs = new Map()
const compactFaces = []
let skippedFaces = 0

for (const face of faces) {
  const corners = face.split(/\s+/).map((token) => {
    const [positionText, uvText] = token.split("/")
    const originalIndex = Number(positionText)
    const mappedIndex = originalIndex > 0 ? remap[originalIndex] : remap[vertices.length + originalIndex + 1]
    const originalUv = Number(uvText)
    return { mappedIndex, originalUv }
  })
  if (new Set(corners.map((corner) => corner.mappedIndex)).size < 3) {
    skippedFaces += 1
    continue
  }
  compactFaces.push(corners.map((corner) => {
    let compactUv = usedUvs.get(corner.originalUv)
    if (compactUv === undefined && Number.isFinite(corner.originalUv) && corner.originalUv !== 0) {
      compactUv = usedUvs.size + 1
      usedUvs.set(corner.originalUv, compactUv)
    }
    return compactUv ? `${corner.mappedIndex}/${compactUv}` : `${corner.mappedIndex}`
  }).join(" "))
}

const chunks = [
  ...headers,
  "s 1",
  ...reduced.map((vertex) => `v ${vertex}`),
]
const uvOrder = [...usedUvs.entries()].sort((left, right) => left[1] - right[1])
for (const [originalUv] of uvOrder) {
  chunks.push(`vt ${uvs[originalUv - 1]}`)
}
for (const face of compactFaces) chunks.push(`f ${face}`)

fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${chunks.join("\n")}\n`)

console.log(JSON.stringify({
  input,
  output,
  headCell: options.headCell,
  bodyCell: options.bodyCell,
  headRatio: options.headRatio,
  vertexCount: vertices.length,
  reducedVertexCount: reduced.length,
  uvCount: uvs.length,
  reducedUvCount: usedUvs.size,
  faceCount: faces.length,
  reducedFaceCount: compactFaces.length,
  skippedFaces,
  minY,
  maxY,
  headThreshold: threshold,
}))
