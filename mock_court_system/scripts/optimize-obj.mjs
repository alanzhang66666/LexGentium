#!/usr/bin/env node

/**
 * Reduce a single-material OBJ by clustering nearby position vertices while
 * retaining the original UV table. The delivered character OBJs have no
 * normals and use one material, so Three.js can rebuild normals at load time.
 */
import fs from "node:fs"
import readline from "node:readline"

const [input, output, cellArg = "0.0015"] = process.argv.slice(2)
if (!input || !output) {
  console.error("usage: optimize-obj.mjs input.obj output.obj [position-cell]")
  process.exit(2)
}

const cell = Number(cellArg)
if (!Number.isFinite(cell) || cell <= 0) {
  throw new Error(`invalid position cell: ${cellArg}`)
}

const inputStream = fs.createReadStream(input, "utf8")
const outputStream = fs.createWriteStream(output, "utf8")
const lines = readline.createInterface({ input: inputStream, crlfDelay: Infinity })

const clusterByKey = new Map()
const remap = []
let vertexCount = 0
let reducedVertexCount = 0
let faceCount = 0
let reducedFaceCount = 0
let emittedHeader = false
let seenGeometry = false

function write(value) {
  if (!outputStream.write(value)) {
    return new Promise((resolve) => outputStream.once("drain", resolve))
  }
  return undefined
}

async function emit(value) {
  const pending = write(value)
  if (pending) await pending
}

for await (const rawLine of lines) {
  const line = rawLine.trim()
  if (!line) continue

  if (line.startsWith("v ")) {
    const [, xText, yText, zText] = line.split(/\s+/)
    const x = Number(xText)
    const y = Number(yText)
    const z = Number(zText)
    const key = `${Math.round(x / cell)}:${Math.round(y / cell)}:${Math.round(z / cell)}`
    let reducedIndex = clusterByKey.get(key)
    if (reducedIndex === undefined) {
      reducedIndex = ++reducedVertexCount
      clusterByKey.set(key, reducedIndex)
      await emit(`v ${xText} ${yText} ${zText}\n`)
    }
    remap[++vertexCount] = reducedIndex
    seenGeometry = true
    continue
  }

  if (line.startsWith("f ")) {
    const tokens = line.slice(2).trim().split(/\s+/)
    const mapped = tokens.map((token) => {
      const [position, ...rest] = token.split("/")
      const originalIndex = Number(position)
      const mappedIndex = originalIndex > 0 ? remap[originalIndex] : remap[vertexCount + originalIndex + 1]
      return [mappedIndex, rest.join("/")]
    })
    faceCount += 1
    const positionIndices = mapped.map(([position]) => position)
    if (new Set(positionIndices).size < 3) continue
    reducedFaceCount += 1
    await emit(`f ${mapped.map(([position, uv]) => `${position}/${uv}`).join(" ")}\n`)
    continue
  }

  // Header and UV lines are copied unchanged. OBJ input places all positions
  // before UVs/faces, so position clusters are known before faces are parsed.
  if (!seenGeometry || line.startsWith("vt ") || line.startsWith("mtllib ") || line.startsWith("o ") || line.startsWith("s ") || line.startsWith("usemtl ") || line.startsWith("g ")) {
    await emit(`${line}\n`)
  }
}

await new Promise((resolve, reject) => outputStream.end((error) => error ? reject(error) : resolve()))
console.log(JSON.stringify({ input, output, cell, vertexCount, reducedVertexCount, faceCount, reducedFaceCount }))
