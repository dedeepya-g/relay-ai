/**
 * Report intake.
 *
 * Someone filling this in often has one hand on something broken, so the
 * description is focused on arrival, location narrows only as far as the
 * reporter can say, and nothing below the description is required. Relay
 * records what is missing rather than demanding it.
 */
import { useEffect, useMemo, useRef, useState } from 'react'

import { PriorityToken } from '../components/PriorityToken'
import { categoryLabel } from '../lib/format'
import type { Campus, ReportIntakeResult } from '../lib/types'

interface IntakeProps {
  campus: Campus | null
  submitting: boolean
  result: ReportIntakeResult | null
  error: string | null
  onSubmit: (input: {
    description: string
    buildingId: string
    floor?: string
    room?: string
    photo?: File | null
  }) => Promise<void>
  onOpenIncident: (incidentId: string) => void
  onReset: () => void
}

const OUTCOME_HEADLINE: Record<string, string> = {
  new_incident: 'Opened a new incident',
  merged: 'Added to an incident already being worked',
  needs_review: 'Held for a person to place',
}

export function IntakeView({
  campus,
  submitting,
  result,
  error,
  onSubmit,
  onOpenIncident,
  onReset,
}: IntakeProps) {
  const [description, setDescription] = useState('')
  const [buildingId, setBuildingId] = useState('')
  const [floor, setFloor] = useState('')
  const [room, setRoom] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const descriptionRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    descriptionRef.current?.focus()
  }, [])

  useEffect(() => {
    if (campus && !buildingId) setBuildingId(campus.buildings[0]?.building_id ?? '')
  }, [campus, buildingId])

  const building = useMemo(
    () => campus?.buildings.find((item) => item.building_id === buildingId) ?? null,
    [campus, buildingId],
  )
  const rooms = useMemo(
    () => (floor ? (building?.rooms.filter((item) => item.floor === floor) ?? []) : []),
    [building, floor],
  )

  if (result) {
    return (
      <div className="panel enter" style={{ marginTop: '1.5rem' }}>
        <div className="panel__head">
          <h2 className="panel__title">{OUTCOME_HEADLINE[result.outcome] ?? 'Report received'}</h2>
          <span className="idtag">{result.report_id}</span>
        </div>
        <div className="factgrid">
          <div>
            <span className="label">Classified as</span>
            <p className="fact__value">{categoryLabel(result.issue_type)}</p>
          </div>
          <div>
            <span className="label">Priority</span>
            <p className="fact__value">
              {result.priority ? (
                <PriorityToken priority={result.priority} />
              ) : (
                'Not set until placed'
              )}
            </p>
          </div>
          <div>
            <span className="label">Team</span>
            <p className="fact__value">{result.team_name ?? 'Awaiting a decision'}</p>
          </div>
        </div>

        <div style={{ padding: '0 1rem 1rem' }}>
          <span className="label" style={{ display: 'block', marginBottom: '0.25rem' }}>
            Why
          </span>
          <p style={{ fontSize: '0.875rem', maxWidth: '64ch' }}>
            {result.reasoning.deduplication ?? result.reasoning.triage}
          </p>
          {result.photo_received && !result.photo_stored && (
            <p className="hint" style={{ marginTop: '0.75rem' }}>
              Your photo was received but not kept — photo storage is not built yet, so
              Relay classified this from the text alone.
            </p>
          )}
          <div className="review__actions" style={{ marginTop: '1rem' }}>
            {result.incident_id && (
              <button
                type="button"
                className="btn btn--primary btn--sm"
                onClick={() => onOpenIncident(result.incident_id!)}
              >
                See the incident
              </button>
            )}
            <button type="button" className="btn btn--sm" onClick={onReset}>
              Report something else
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <form
      className="panel form"
      style={{ marginTop: '1.5rem', maxWidth: '44rem' }}
      onSubmit={(event) => {
        event.preventDefault()
        void onSubmit({
          description: description.trim(),
          buildingId,
          floor: floor || undefined,
          room: room || undefined,
          photo,
        })
      }}
    >
      <div className="field">
        <label className="label" htmlFor="description">
          What is wrong?
        </label>
        <textarea
          id="description"
          ref={descriptionRef}
          className="textarea"
          value={description}
          maxLength={4000}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Water is leaking inside the third-floor restroom."
          required
        />
        <p className="hint">
          Plain words are fine. Relay reads this the way you wrote it.
        </p>
      </div>

      <div className="field__row">
        <div className="field">
          <label className="label" htmlFor="building">
            Building
          </label>
          <select
            id="building"
            className="select"
            value={buildingId}
            onChange={(event) => {
              setBuildingId(event.target.value)
              setFloor('')
              setRoom('')
            }}
            required
          >
            {campus?.buildings.map((item) => (
              <option key={item.building_id} value={item.building_id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="label" htmlFor="floor">
            Floor <span style={{ textTransform: 'none' }}>· if you know it</span>
          </label>
          <select
            id="floor"
            className="select"
            value={floor}
            disabled={!building}
            onChange={(event) => {
              setFloor(event.target.value)
              setRoom('')
            }}
          >
            <option value="">Not sure</option>
            {building?.floors.map((item) => (
              <option key={item} value={item}>
                {item === 'B1' ? 'Basement' : `Floor ${item}`}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="label" htmlFor="room">
            Room <span style={{ textTransform: 'none' }}>· if you know it</span>
          </label>
          <select
            id="room"
            className="select"
            value={room}
            disabled={!floor}
            onChange={(event) => setRoom(event.target.value)}
          >
            <option value="">Not sure</option>
            {rooms.map((item) => (
              <option key={item.number} value={item.number}>
                {item.number}
                {item.name ? ` — ${item.name}` : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="field">
        <label className="label" htmlFor="photo">
          Photo <span style={{ textTransform: 'none' }}>· optional</span>
        </label>
        <input
          id="photo"
          className="file"
          type="file"
          accept="image/*"
          onChange={(event) => setPhoto(event.target.files?.[0] ?? null)}
        />
        <p className="hint">Accepted, but not stored yet — Relay will read your text.</p>
      </div>

      {error && <p className="notice">{error}</p>}

      <div>
        <button
          type="submit"
          className="btn btn--primary"
          disabled={submitting || description.trim().length === 0}
        >
          {submitting ? 'Reading your report…' : 'Send report'}
        </button>
      </div>
    </form>
  )
}
