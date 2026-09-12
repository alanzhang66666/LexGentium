/** Controlled six-column field keys. Values must match ``core/research/field_keys.py``. */

import type { TaskType } from "@/lib/research/enums"

export const CISG_FACT_FIELD_KEYS = [
  "parties_places_of_business",
  "governing_instrument",
  "alleged_impediment",
  "notice_date",
] as const

export const ENFORCEMENT_FACT_FIELD_KEYS = [
  "award_seat",
  "arbitration_institution",
  "enforcement_forum",
  "notice_of_proceedings",
  "award_date",
] as const

export const ALL_FACT_FIELD_KEYS = [
  "parties_places_of_business",
  "governing_instrument",
  "alleged_impediment",
  "notice_date",
  "award_seat",
  "arbitration_institution",
  "enforcement_forum",
  "notice_of_proceedings",
  "award_date",
] as const

export const FACT_FIELD_KEYS_BY_TASK: Record<TaskType, readonly string[]> = {
  cisg_article79: CISG_FACT_FIELD_KEYS,
  enforcement_nyc: ENFORCEMENT_FACT_FIELD_KEYS,
}

export const GAP_RELATED_FIELDS = [
  "parties_places_of_business",
  "governing_instrument",
  "alleged_impediment",
  "notice_date",
  "award_seat",
  "arbitration_institution",
  "enforcement_forum",
  "notice_of_proceedings",
  "award_date",
  "impediment",
  "beyond_control",
  "unforeseeable",
  "unavoidable",
  "notice",
  "third_person",
  "duration",
  "other_remedies",
  "procedural_facts",
  "party_claims",
  "court_findings",
  "legal_bases",
  "material_gaps",
  "source_anchors",
  "award_text",
] as const
