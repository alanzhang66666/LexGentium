#!/usr/bin/env node

import { spawnSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, "../..")
const optimizer = path.join(here, "optimize-obj.mjs")

const jobs = [
  ["审判长/de3c7f0ce40b3295365b3ff7c12c654d.obj", "roles/judge/model-optimized.obj"],
  ["审判员/09e463a2f0f1c70a76f655f8f86d3509.obj", "roles/associate-judge/model-optimized.obj"],
  ["人民陪审员/220a1db130e2a30ab1ebad73c54d1e90.obj", "roles/people-juror/model-optimized.obj"],
  ["书记员/61207a98c2ee124a5b13acd145284acd.obj", "roles/clerk/model-optimized.obj"],
  ["中方代理律师/a17eb167347a3a14341a9cdb5f3f6e1d.obj", "roles/china-counsel/model-optimized.obj"],
  ["中方企业代表/18f1bd4e59a6e554730c77a5da8297ad.obj", "roles/china-company-rep/model-optimized.obj"],
  ["外方代理律师/4b003cdc9d4c29c8750d3075b618d861.obj", "roles/foreign-counsel/model-optimized.obj"],
  ["外方企业代表/0839de8d476881405339f6d90944b01b.obj", "roles/foreign-company/model-optimized.obj"],
  ["法庭口译员/af4df04667f911cf7d659b87519ebc75.obj", "roles/interpreter/model-optimized.obj"],
  ["技术专家证人/255c3eb8dfa1551fee8c93c5c455a307.obj", "roles/technical-expert-witness/model-optimized.obj"],
  ["外籍事实证人/c972d8b4b758a83ea635faf0fbede9e2.obj", "roles/foreign-witness/model-optimized.obj"],
  ["公诉人/db8530e6b5f1951697c10a732fbcd5b2.obj", "roles/prosecutor/model-optimized.obj"],
  ["司法警察/c80c0d8dfde4a40bc440e8625c7a0478.obj", "models/judicial-police/judicial-police-optimized.obj"],
]

const only = process.argv.slice(2)
for (const [sourceRel, outputRel] of jobs) {
  const slug = outputRel.split("/")[1] ?? outputRel
  if (only.length > 0 && !only.includes(slug) && !only.some((value) => sourceRel.includes(value))) continue
  const input = path.join(repoRoot, "3D建模方案/角色资料", sourceRel)
  const output = outputRel.startsWith("models/")
    ? path.join(repoRoot, "mock_court_system/public/hearing-3d", outputRel)
    : path.join(repoRoot, "mock_court_system/public/hearing-3d/models", outputRel)
  console.log(`\n=== ${sourceRel} -> ${outputRel} ===`)
  const result = spawnSync(process.execPath, [optimizer, input, output], { stdio: "inherit" })
  if (result.status !== 0) process.exit(result.status ?? 1)
}
