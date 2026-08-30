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
      <div className="panel">
        <div className="empty">
          <strong>Reading the campus configuration…</strong>
        </div>
      </div>
    )
  }

  if (!campus) {
    return (
      <div className="panel">
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

      <p className="hint" style={{ marginBottom: '1.25rem', maxWidth: '68ch' }}>
        The configuration Relay reads when it routes, prioritises, and escalates.
        Every decision on the board is made against these values. Read-only here:
        changing a deadline would re-time incidents already open against it.
      </p>

      {/* --- Policy ---------------------------------------------------------- */}
      <div className="detail__grid">
        <div className="panel">
          <div className="panel__head">
            <h3 className="panel__title">Response deadlines</h3>
            <span className="label">by priority</span>
          </div>
          <div className="factgrid">
            {PRIORITY_ORDER.filter((p) => campus.sla_minutes[p] !== undefined).map(
              (priority) => (
                <div key={priority}>
                  <span className={`priority priority--${priority}`}>
                    <span className="priority__token" />
                    {priority}
                  </span>
                  <p className="fact__value">{duration(campus.sla_minutes[priority])}</p>
                </div>
              ),
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel__head">
            <h3 className="panel__title">Escalation</h3>
            <span className="label">when a deadline passes</span>
          </div>
          <div className="factgrid">
            <div>
              <span className="label">Grace period</span>
              <p className="fact__value">{duration(policy.grace_period_minutes)}</p>
            </div>
            <div>
              <span className="label">Repeat every</span>
              <p className="fact__value">{duration(policy.repeat_interval_minutes)}</p>
            </div>
            <div>
              <span className="label">Stops at level</span>
              <p className="fact__value">{policy.max_level}</p>
            </div>
          </div>
          {policy.notify_on_escalation.length > 0 && (
            <div style={{ padding: '0 1rem 1rem' }}>
              <span className="label" style={{ display: 'block', marginBottom: '0.375rem' }}>
                Notified at every level
              </span>
              {policy.notify_on_escalation.map((address) => (
                <p className="row__sub" key={address} style={{ marginTop: 0 }}>
                  {address}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* --- Teams ----------------------------------------------------------- */}
      <div className="section-head">
        <h3 className="panel__title">Maintenance teams</h3>
        <span className="label">
          {campus.teams.length} {campus.teams.length === 1 ? 'team' : 'teams'}
        </span>
      </div>
      <div className="panel">
        {campus.teams.map((team) => (
          <div className="evidence__item" key={team.team_id} style={{ padding: '0.875rem 1rem' }}>
            <div className="evidence__meta" style={{ justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 500 }}>{team.name}</span>
              <span className="idtag">{team.coverage_hours}</span>
            </div>
            <p className="row__sub" style={{ marginTop: '0.25rem' }}>
              {team.team_id}
            </p>
            <div className="evidence__meta" style={{ marginTop: '0.5rem' }}>
              {team.categories.map((category) => (
                <span className="tag tag--resolved" key={category}>
                  {categoryLabel(category)}
                </span>
              ))}
            </div>
          </div>
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

      {campus.buildings.map((building) => (
        <div className="panel" key={building.building_id} style={{ marginBottom: '1rem' }}>
          <div className="panel__head">
            <h3 className="panel__title">{building.name}</h3>
            <span className="idtag">{building.building_id}</span>
            <span className="label" style={{ marginLeft: 'auto' }}>
              {building.floors.length} floors · {building.rooms.length} rooms
            </span>
          </div>

          {building.aliases.length > 0 && (
            <p className="hint" style={{ padding: '0.75rem 1rem 0' }}>
              Also reported as: {building.aliases.join(', ')}
            </p>
          )}

          <div className="evidence">
            {building.floors.map((floor) => {
              const rooms = roomsByFloor(building.rooms, floor)
              return (
                <div className="evidence__item" key={floor}>
                  <span className="label">{floorLabel(floor)}</span>
                  {rooms.length === 0 ? (
                    <p className="hint" style={{ marginTop: '0.25rem' }}>
                      No rooms configured on this floor.
                    </p>
                  ) : (
                    <div className="evidence__meta" style={{ marginTop: '0.375rem' }}>
                      {rooms.map((room) => (
                        <span className="roomchip" key={room.number}>
                          <span className="roomchip__n">{room.number}</span>
                          {room.name ?? room.room_type.replace('_', ' ')}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </>
  )
}
