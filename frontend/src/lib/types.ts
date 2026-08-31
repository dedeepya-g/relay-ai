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

export interface EscalationPolicy {
  grace_period_minutes: number
  repeat_interval_minutes: number
  max_level: number
  notify_on_escalation: string[]
}

export interface Campus {
  campus_id: string
  name: string
  timezone: string
  buildings: BuildingOption[]
  teams: TeamOption[]
  sla_minutes: Record<Priority, number>
  escalation_policy: EscalationPolicy
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
  /** Plain-language description, shown on row focus. */
  summary: string
  /** Work orders dispatched for this incident; empty for older incidents. */
  work_order_ids: string[]
  sla_due_at: string | null
  /** When the incident was resolved; null while it is live. */
  resolved_at: string | null
  /** When the incident was closed; null until it is. */
  closed_at: string | null
  created_at: string
  updated_at: string
  /**
   * How many times the overdue sweep has raised this incident; 0 means never.
   * Written by `escalate_overdue_incidents`, which the queue triggers through
   * `POST /admin/check-overdue`. Nothing runs it on a schedule yet, so it
   * advances only when someone asks for a sweep.
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
  /** What executed the decision, not merely whether a person was involved. */
  decided_by: 'model' | 'rule' | 'agent' | 'human'
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

export type WorkOrderStatus =
  | 'pending'
  | 'acknowledged'
  | 'in_progress'
  | 'completed'
  | 'cancelled'

export interface WorkOrder {
  work_order_id: string
  ticket: string
  incident_id: string
  team_id: string
  team_name: string | null
  status: WorkOrderStatus
  priority: Priority
  due_at: string | null
  created_at: string
}

export interface EscalationEntry {
  incident_id: string
  title: string
  escalation_level: number
  minutes_past_deadline: number
  supporting_team_id: string | null
  supporting_ticket: string | null
  work_order_tickets: string[]
}

export interface OverdueSweepResult {
  campus_id: string
  /** Incidents found past their deadline. */
  checked_count: number
  /**
   * Of those, how many the policy actually raised. The two differ when an
   * incident is inside its grace period or repeat interval, or already at the
   * policy's maximum level.
   */
  escalated_count: number
  escalations: EscalationEntry[]
}

export interface StatusUpdateResult {
  incident: IncidentSummary
  previous_status: IncidentStatus
  /** False when the incident was already in the target status. */
  changed: boolean
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
