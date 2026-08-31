/**
 * Report intake.
 *
 * Someone filling this in often has one hand on something broken, so the
 * description is focused on arrival, location narrows only as far as the
 * reporter can say, and nothing below the description is required. Relay
 * records what is missing rather than demanding it.
 */
import { useEffect, useMemo, useRef, useState } from 'react'

import { CategoryGlyph } from '../components/CategoryGlyph'
import { PriorityToken } from '../components/PriorityToken'
import { categoryLabel, floorLabel } from '../lib/format'
import type { Campus, ReportIntakeResult } from '../lib/types'

interface IntakeProps {
  campus: Campus | null
  /**
   * Why the campus layout is missing, when it is. Without it there are no
   * buildings to choose from, and an empty dropdown with nothing beside it
   * reads as a campus with no buildings rather than as a failure to load.
   */
  campusError: string | null
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
  new_incident: 'Opened a new issue',
  merged: 'Added to work already underway',
  needs_review: 'Someone will take a look',
}

export function IntakeView({
  campus,
  campusError,
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
            <span className="label">Issue</span>
            <p className="fact__value fact__value--glyph">
              <CategoryGlyph category={result.issue_type} />
              {categoryLabel(result.issue_type)}
            </p>
          </div>
          <div>
            <span className="label">Urgency</span>
            <p className="fact__value fact__value--glyph">
              {result.priority ? (
                <>
                  <PriorityToken priority={result.priority} />
                  {result.priority[0].toUpperCase() + result.priority.slice(1)}
                </>
              ) : (
                'Set once someone places it'
              )}
            </p>
          </div>
          <div>
            <span className="label">Team</span>
            <p className="fact__value">{result.team_name ?? 'Not yet assigned'}</p>
          </div>
        </div>

        <div style={{ padding: '0 1rem 1rem' }}>
          <span className="label" style={{ display: 'block', marginBottom: '0.25rem' }}>
            What happens next
          </span>
          <p style={{ fontSize: '0.875rem', maxWidth: '64ch' }}>
            {result.reasoning.deduplication ?? result.reasoning.triage}
          </p>
          {result.photo_received && !result.photo_stored && (
            <p className="hint" style={{ marginTop: '0.75rem' }}>
              Your photo came through but isn't kept yet. We read your description.
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
    <>
      {/* Answers the question a category-picker would otherwise force: what
          kind of problem is this? Nothing here asks the reporter to decide. */}
      <header className="intro">
        <span className="label intro__eyebrow">Report an issue</span>
        <h1 className="display intro__title">Just tell us what’s wrong.</h1>
        <p className="intro__sub">
          We read what you wrote, work out what kind of problem it is, and send it
          to the team that handles it.
        </p>
        <p className="intro__note">
          There’s no category to choose and no form to hunt through. Describe it in
          the box below, in your own words.
        </p>
      </header>

      <form
      className="panel form"
      style={{ maxWidth: '44rem' }}
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
      {/* Shown above the fields rather than beside the building select: it
          explains why every location choice below is empty, not just one. */}
      {campusError && (
        <p className="notice">
          <strong>Relay could not load the campus layout.</strong> Buildings,
          floors, and rooms are unavailable, so a report cannot be placed yet.{' '}
          {campusError}
        </p>
      )}

      <div className="field">
        <label className="label" htmlFor="description">
          What’s wrong?
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
                {floorLabel(item)}
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
                {item.name ? `, ${item.name}` : ''}
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
        <p className="hint">Not kept yet. We’ll go on your description.</p>
      </div>

      {error && <p className="notice">{error}</p>}

      <div>
        {/* A report with no building cannot be deduplicated or routed, so the
            form refuses rather than sending one the pipeline will reject. */}
        <button
          type="submit"
          className="btn btn--primary"
          disabled={submitting || description.trim().length === 0 || !buildingId}
        >
          {submitting ? 'Reading your report…' : 'Send report'}
        </button>
        {!buildingId && (
          <p className="hint" style={{ marginTop: '0.5rem' }}>
            Waiting on the campus layout before a report can be sent.
          </p>
        )}
      </div>
      </form>
    </>
  )
}
