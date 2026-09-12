/** Input / run / eval contracts. Field names must match ``core/research/contracts.py``. */

import type { DatasetId, StopReason, TaskType } from "@/lib/research/enums"
import type {
  ExperimentConditions,
  ModelConfigSnapshot,
  ReferenceLayer,
  ReviewRecord,
  TaskLabels,
  VisibilityGrant,
  VisibleMaterials,
} from "@/lib/research/shared"

export interface InputContract {
  schema_version?: string
  dataset_id: DatasetId
  cluster_id: string
  pack_version: string
  task_type: TaskType
  visible_materials: Record<string, VisibleMaterials>
  visibility_grants?: VisibilityGrant[]
  experiment_conditions: ExperimentConditions
  model_config: ModelConfigSnapshot
  task_labels?: TaskLabels | null
  reference?: ReferenceLayer | null
}

export interface RunUtterance {
  turn: number
  role: string
  text: string
  source_ids?: string[]
}

export interface RetrievedSpan {
  source_id: string
  document_id: string
  quote?: string
  score?: number | null
}

export interface RunContract {
  schema_version?: string
  run_id: string
  derived_from?: string | null
  session_id?: string | null
  dataset_id: DatasetId
  cluster_id: string
  pack_version: string
  task_type: TaskType
  materials_hash?: string
  utterances?: RunUtterance[]
  retrieved_spans?: RetrievedSpan[]
  stop_reason?: StopReason | null
  created_at?: string
}

export interface EvalContract {
  schema_version?: string
  report_id: string
  run_id: string
  reference_version?: string
  rubric_version?: string
  machine_checks?: Record<string, unknown>
  legal_quality?: Record<string, unknown>
  review_records?: ReviewRecord[]
  created_at?: string
}
