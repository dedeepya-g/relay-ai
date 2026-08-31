/**
 * The campus configuration, at `/ops/campus`.
 *
 * Read-only, and read from the same document the pipeline reads at decision
 * time. This is the answer to "why did that go to Plumbing?" and "why was the
 * deadline two minutes?" -- the policy behind every routing and prioritisation
 * decision, which until now existed only in Firestore and in the seed script.
 *
 * Editing belongs to whoever owns campus policy, not to a dashboard: changing
 * an SLA here would silently re-time every incident already open against it.
 */
import { useCampus } from '../../lib/CampusContext'
import { CategoryGlyph } from '../../components/CategoryGlyph'
import { PriorityToken } from '../../components/PriorityToken'
import { categoryLabel, floorLabel } from '../../lib/format'
import type { Priority, RoomOption } from '../../lib/types'

const PRIORITY_ORDER: Priority[] = ['critical', 'high', 'medium', 'low']

/** Minutes as an operator says them. */
function duration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`
  const hours = minutes / 60
  if (Number.isInteger(hours)) return `${hours} hr`
  return `${Math.floor(hours)} hr ${minutes % 60} min`
}

function roomsByFloor(rooms: RoomOption[], floor: string): RoomOption[] {
  return rooms.filter((room) => room.floor === floor)
}

export function CampusPage() {
  const { campus, error, loading } = useCampus()

  if (loading) {
    return (
      <div className="rowlist">
        <div className="empty">
          <strong>Reading the campus configuration…</strong>
        </div>
      </div>
    )
  }

  if (!campus) {
    return (
      <div className="rowlist">
        <div className="empty">
          <strong>No campus configuration is available.</strong>
          {error ?? 'Seed one with scripts/seed_campus_config.py.'}
        </div>
      </div>
    )
  }

  const policy = campus.escalation_policy

  return (
    <>
      <div className="section-head">
        <h2 className="panel__title">{campus.name}</h2>
        <span className="idtag">{campus.campus_id}</span>
        <span className="label" style={{ marginLeft: 'auto' }}>
          {campus.timezone}
        </span>
      </div>

      <p className="hint" style={{ marginBottom: '1.25rem', maxWidth: '62ch' }}>
        Every call on the board is made against these values.
      </p>

      <div className="block">
        <div className="block__head">
          <h3 className="panel__title">Response policy</h3>
          <span className="label">and what happens when they pass</span>
        </div>
        <div className="factgrid">
          {PRIORITY_ORDER.filter((p) => campus.sla_minutes[p] !== undefined).map(
            (priority) => (
              <div key={priority}>
                <span className="fact__value--glyph" style={{ display: 'flex' }}>
                  <PriorityToken priority={priority} />
                  <span className="label">{priority}</span>
                </span>
                <p className="fact__value">{duration(campus.sla_minutes[priority])}</p>
              </div>
            ),
          )}
        </div>
        <div className="factgrid" style={{ borderTop: '1px solid var(--line)' }}>
          <div>
            <span className="label">Wait before raising</span>
            <p className="fact__value">{duration(policy.grace_period_minutes)}</p>
          </div>
          <div>
            <span className="label">Raise again every</span>
            <p className="fact__value">{duration(policy.repeat_interval_minutes)}</p>
          </div>
          <div>
            <span className="label">Stops after</span>
            <p className="fact__value">{policy.max_level} raises</p>
          </div>
          {policy.notify_on_escalation.length > 0 && (
            <div>
              <span className="label">Goes to</span>
              <p className="fact__value" style={{ fontSize: '0.8125rem' }}>
                {policy.notify_on_escalation
                  .map((a) => a.split('@')[0].replace(/\./g, ' '))
                  .join(', ')}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* --- Teams ----------------------------------------------------------- */}
      <div className="section-head">
        <h3 className="panel__title">Teams</h3>
        <span className="label">
          {campus.teams.length} {campus.teams.length === 1 ? 'team' : 'teams'}
        </span>
      </div>
      <div className="rowlist">
        {campus.teams.map((team) => (
          <details className="disclose" key={team.team_id}>
            <summary className="disclose__row">
              <span className="disclose__caret" aria-hidden="true" />
              <span className="disclose__name">{team.name}</span>
              <span className="disclose__stat">
                {team.categories.length}{' '}
                {team.categories.length === 1 ? 'category' : 'categories'}
              </span>
            </summary>
            <div className="disclose__body">
              <div className="glyphrow">
                {team.categories.map((category) => (
                  <span key={category}>
                    <CategoryGlyph category={category} />
                    {categoryLabel(category)}
                  </span>
                ))}
              </div>
              <p className="hint" style={{ marginTop: '0.625rem' }}>
                {team.coverage_hours}
              </p>
            </div>
          </details>
        ))}
      </div>

      {/* --- Buildings ------------------------------------------------------- */}
      <div className="section-head">
        <h3 className="panel__title">Buildings</h3>
        <span className="label">
          {campus.buildings.length} buildings ·{' '}
          {campus.buildings.reduce((sum, b) => sum + b.rooms.length, 0)} rooms
        </span>
      </div>

      <div className="rowlist">
        {campus.buildings.map((building) => (
          <details className="disclose" key={building.building_id}>
            <summary className="disclose__row">
              <span className="disclose__caret" aria-hidden="true" />
              <span className="disclose__name">{building.name}</span>
              <span className="disclose__stat">
                {building.floors.length} floors · {building.rooms.length} rooms
              </span>
            </summary>
            <div className="disclose__body">
              {building.aliases.length > 0 && (
                <p className="hint" style={{ marginBottom: '0.75rem' }}>
                  Also called {building.aliases.join(', ')}
                </p>
              )}
              {building.floors.map((floor) => {
                const rooms = roomsByFloor(building.rooms, floor)
                return (
                  <div className="floorblock" key={floor}>
                    <span className="label">{floorLabel(floor)}</span>
                    {rooms.length === 0 ? (
                      <p className="hint">No rooms listed.</p>
                    ) : (
                      <p className="roomlist">
                        {rooms.map((room, i) => (
                          <span key={room.number}>
                            {i > 0 && <span className="roomlist__sep"> · </span>}
                            <span className="roomlist__n">{room.number}</span>{' '}
                            {room.name ?? room.room_type.replace('_', ' ')}
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </details>
        ))}
      </div>

    </>
  )
}
