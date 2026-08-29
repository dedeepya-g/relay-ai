/** Wire types mirroring `backend/api/schemas.py`. */

export type Priority = 'critical' | 'high' | 'medium' | 'low'
export type IncidentStatus =
  | 'open'
  | 'assigned'
  | 'in_progress'
  | 'on_hold'
  | 'escalated'
  | 'resolved'
  | 'closed'
export type ReportStatus =
  | 'received'
  | 'triaged'
  | 'linked'
  | 'pending_review'
  | 'rejected'
export type Outcome = 'new_incident' | 'merged' | 'needs_review'

export interface RoomOption {
  number: string
  floor: string
  room_type: string
  name: string | null
}

export interface BuildingOption {
  building_id: string
  name: string
  aliases: string[]
  floors: string[]
  rooms: RoomOption[]
}

export interface TeamOption {
  team_id: string
  name: string
  categories: string[]
  coverage_hours: string
}

export interface Campus {
  campus_id: string
  name: string
  timezone: string
  buildings: BuildingOption[]
  teams: TeamOption[]
  sla_minutes: Record<Priority, number>
}

export interface IncidentSummary {
  incident_id: string
  title: string
  category: string
  priority: Priority
  status: IncidentStatus
  building_id: string
  floor: string | null
  room: string | null
  assigned_team_id: string | null
  assigned_team_name: string | null
  report_count: number
  sla_due_at: string | null
  created_at: string
  updated_at: string
  /**
   * Escalation level, raised only by the overdue sweep. That sweep is not
   * implemented server-side yet, so this is always 0 today and the queue's
   * ESCALATED tag never fires. The reader is deliberately in place so that
   * finishing `escalate_overdue_incidents` lights it up with no UI change.
   */
  escalation_level?: number
}

export interface LinkedReport {
  report_id: string
  description: string
  status: ReportStatus
  floor: string | null
  room: string | null
  is_potential_emergency: boolean
  severity_signals: string[]
  submitted_at: string
}

export interface DecisionEntry {
  decision_id: string
  decision_type: string
  decided_by: 'agent' | 'human'
  subject_id: string
  outcome: string
  rationale: string
  model: string | null
  created_at: string
}

export interface IncidentDetail {
  incident: IncidentSummary
  summary: string
  reports: LinkedReport[]
  decisions: DecisionEntry[]
}

export interface PendingReview {
  report_id: string
  description: string
  building_id: string
  floor: string | null
  room: string | null
  issue_type: string | null
  is_potential_emergency: boolean
  severity_signals: string[]
  reasoning: string
  submitted_at: string
}

export interface ReportIntakeResult {
  report_id: string
  outcome: Outcome
  incident_id: string | null
  report_status: ReportStatus
  issue_type: string | null
  is_potential_emergency: boolean
  severity_signals: string[]
  missing_fields: string[]
  priority: Priority | null
  team_assigned: string | null
  team_name: string | null
  sla_due_at: string | null
  evidence_count: number | null
  reasoning: Record<string, string>
  photo_received: boolean
  photo_stored: boolean
}
