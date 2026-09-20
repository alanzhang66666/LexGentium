/** Shared numbers for the OBJ rebuild script. Keep in sync with `scripts/optimize-obj.mjs`. */

export const OBJ_OPTIMIZE = {
  /** Top slice of the bounding box treated as head / neck. */
  headRatio: 0.17,
  /** Finer facial grid. These scans have overlapping shells, so sub-millimeter cells explode. */
  headCell: 0.0036,
  /** Body grid close to the current compact runtime density. */
  bodyCell: 0.0165,
} as const

export function headThreshold(minY: number, maxY: number, headRatio = OBJ_OPTIMIZE.headRatio): number {
  return minY + (1 - headRatio) * (maxY - minY)
}

export function clusterCell(y: number, threshold: number, headCell = OBJ_OPTIMIZE.headCell, bodyCell = OBJ_OPTIMIZE.bodyCell): number {
  return y >= threshold ? headCell : bodyCell
}

export function clusterKey(x: number, y: number, z: number, cell: number): string {
  return `${Math.round(x / cell)}:${Math.round(y / cell)}:${Math.round(z / cell)}`
}
