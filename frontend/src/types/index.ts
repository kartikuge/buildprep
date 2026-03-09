export type Stage = 'prelims' | 'mains' | 'both'

export type Subject =
  | 'HISTORY'
  | 'ECONOMY'
  | 'POLITY'
  | 'ENVIRONMENT'
  | 'GEOGRAPHY'
  | 'SCI_TECH'
  | 'ETHICS'
  | 'ESSAY'
  | 'OPTIONAL'
  | 'CSAT'

export type BlockCategory =
  | 'CORE_LEARNING'
  | 'CORE_RETENTION'
  | 'CORE_PATTERN'
  | 'PERFORMANCE'
  | 'CORRECTIVE'
  | 'RETENTION'
  | 'INPUT'
  | 'PROCESSING'
  | 'META'

export interface PlanCard {
  card_id: string
  block_type: string
  category: BlockCategory
  subject: Subject | null
  topic: string | null
  planned_duration: number
  actual_duration: number | null
  fatigue: number
  order: number
  status: string
}

export interface DailyPlan {
  date: string
  cards: PlanCard[]
  finalized: boolean
}

export interface WeeklyPlan {
  user_id: string
  week_start: string
  days: DailyPlan[]
  narrative: string
  generated_at: string
}

export interface UserProfile {
  user_id: string
  display_name: string
  optional_subject: string | null
  stage: Stage
  prelims_date: string | null
  mains_date: string | null
  available_hours_per_day: number
  created_at: string
}

export interface OnboardRequest {
  display_name: string
  optional_subject: string | null
  stage: Stage
  prelims_date: string | null
  mains_date: string | null
  available_hours_per_day: number
  subject_confidences: Record<string, number>
}

export interface OnboardResponse {
  user_id: string
  profile: UserProfile
  plan: WeeklyPlan | null
  plan_error: string | null
}

export interface ExamCycle {
  id: string
  label: string
  prelimsDate: string
  mainsDate: string
}

export type CheckInStatus = 'PENDING' | 'DONE' | 'PARTIAL' | 'SKIPPED'

export interface CardCheckIn {
  card_id: string
  status: 'DONE' | 'PARTIAL' | 'SKIPPED'
  actual_duration?: number
}

export interface CheckInRequest {
  cards: CardCheckIn[]
  finalize_day: boolean
}

export interface CheckInResponse {
  date: string
  finalized: boolean
  cards_updated: number
  confidences_updated: string[]
}

export interface TopicConfidence {
  user_id: string
  subject: Subject
  perceived_confidence: number
  streak: number
  skip_count: number
  total_sessions: number
  last_practiced_date: string | null
  milestones_awarded: string[]
}
