import { describe, expect, it } from "vitest"
import { FACE_MATERIAL_PRESET } from "./face-material-preset"
import { clusterCell, clusterKey, headThreshold, OBJ_OPTIMIZE } from "./obj-optimize"

describe("hearing face material preset", () => {
  it("keeps skin dielectric and damps noisy scan normals", () => {
    expect(FACE_MATERIAL_PRESET.sheen).toBeGreaterThan(0)
    expect(FACE_MATERIAL_PRESET.clearcoat).toBeLessThan(0.1)
    expect(FACE_MATERIAL_PRESET.normalScale).toBeLessThan(0.5)
    expect(FACE_MATERIAL_PRESET.envMapIntensity).toBeGreaterThan(0)
    expect(FACE_MATERIAL_PRESET.maxAnisotropy).toBeGreaterThanOrEqual(8)
  })
})

describe("face-preserving OBJ clustering", () => {
  it("uses a finer grid on the top of the bounding box", () => {
    const threshold = headThreshold(0, 1)
    expect(threshold).toBeCloseTo(1 - OBJ_OPTIMIZE.headRatio)
    expect(clusterCell(0.9, threshold)).toBe(OBJ_OPTIMIZE.headCell)
    expect(clusterCell(0.2, threshold)).toBe(OBJ_OPTIMIZE.bodyCell)
    expect(OBJ_OPTIMIZE.headCell * 4).toBeLessThan(OBJ_OPTIMIZE.bodyCell)
  })

  it("keeps nearby facial vertices in distinct cells", () => {
    const lip = clusterKey(0.01, 0.7, 0.04, OBJ_OPTIMIZE.headCell)
    const aboveLip = clusterKey(0.01, 0.705, 0.04, OBJ_OPTIMIZE.headCell)
    const bodyA = clusterKey(0.2, 0.3, 0.1, OBJ_OPTIMIZE.bodyCell)
    const bodyB = clusterKey(0.201, 0.3, 0.1, OBJ_OPTIMIZE.bodyCell)
    expect(lip).not.toEqual(aboveLip)
    expect(bodyA).toEqual(bodyB)
  })
})
