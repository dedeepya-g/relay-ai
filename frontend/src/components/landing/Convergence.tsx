/**
 * The hero visual: scattered reports sorting into the incidents they belong to.
 *
 * This is deduplication drawn rather than described, and deliberately shows
 * both halves of it. Reports that describe one fault group together; reports
 * that describe different faults stay apart. A version that collapsed
 * everything into a single card would depict the failure the product exists
 * to prevent -- merging things that are not the same problem.
 *
 * The cards are built from the board's own parts: the same priority token,
 * mono facts, and hairline structure a real queue row uses. Nothing here is
 * an illustration of the product; it is the product's own vocabulary.
 *
 * Motion is CSS only, on one shared cycle. Under `prefers-reduced-motion`
 * every element holds its resolved state, which says the same thing without
 * the movement.
 */

interface Cluster {
  id: string
  priority: 'critical' | 'high' | 'medium'
  label: string
  title: string
  team: string
  /** Centre of this card in stage coordinates, where its reports travel to. */
  cx: number
  cy: number
  /** Where the card itself sits. */
  top: number
  delay: string
}

const CLUSTERS: Cluster[] = [
  {
    id: 'a',
    priority: 'critical',
    label: 'Critical',
    title: 'Water spreading on an upper floor',
    team: 'Plumbing',
    cx: 62,
    cy: 12,
    top: 2,
    delay: '0.2s',
  },
  {
    id: 'b',
    priority: 'high',
    label: 'High',
    title: 'Lighting out in a stairwell',
    team: 'Electrical',
    cx: 62,
    cy: 47,
    top: 37,
    delay: '0.45s',
  },
  {
    id: 'c',
    priority: 'medium',
    label: 'Medium',
    title: 'No heating in a west-wing office',
    team: 'HVAC',
    cx: 62,
    cy: 82,
    top: 72,
    delay: '0.7s',
  },
]

/** Each report, where it starts, and which incident it turns out to belong to. */
const REPORTS = [
  { text: 'there’s a puddle by the door', x: 0, y: 0, to: 'a', delay: '0s' },
  { text: 'ceiling’s dripping again', x: 34, y: 14, to: 'a', delay: '0.35s' },
  { text: 'floor is soaked in here', x: 2, y: 26, to: 'a', delay: '0.7s' },
  { text: 'stairwell light keeps flickering', x: 30, y: 40, to: 'b', delay: '1.05s' },
  { text: 'half the lights are out', x: 0, y: 53, to: 'b', delay: '1.4s' },
  { text: 'radiator is stone cold', x: 4, y: 76, to: 'c', delay: '1.75s' },
  { text: 'freezing in this office', x: 32, y: 90, to: 'c', delay: '2.1s' },
]

export function Convergence() {
  const target = (id: string) => CLUSTERS.find((c) => c.id === id) as Cluster

  return (
    <div
      className="converge"
      role="img"
      aria-label="Scattered maintenance reports sorting into three separate incidents: reports describing one fault group together, reports describing different faults stay apart"
    >
      {/* A thread from each report to the incident it joins. Same hairline as
          every rule on the board -- structure, not decoration. */}
      <svg className="converge__web" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {REPORTS.map((r) => {
          const t = target(r.to)
          return (
            <line
              key={r.text}
              x1={r.x + 12}
              y1={r.y + 5}
              x2={t.cx}
              y2={t.cy}
              className="converge__thread"
              style={{ animationDelay: r.delay }}
            />
          )
        })}
      </svg>

      {REPORTS.map((r) => {
        const t = target(r.to)
        return (
          <span
            key={r.text}
            className="bubble"
            style={
              {
                '--x': `${r.x}%`,
                '--y': `${r.y}%`,
                '--cx': `${t.cx}%`,
                '--cy': `${t.cy}%`,
                animationDelay: r.delay,
              } as React.CSSProperties
            }
          >
            {r.text}
          </span>
        )
      })}

      {CLUSTERS.map((c) => (
        <div
          key={c.id}
          className={`converge__card converge__card--${c.priority}`}
          style={{ top: `${c.top}%`, animationDelay: c.delay }}
          aria-hidden="true"
        >
          <div className="converge__cardhead">
            <span className={`priority priority--${c.priority}`}>
              <span className="priority__token" />
              {c.label}
            </span>
            <span className="idtag">
              {REPORTS.filter((r) => r.to === c.id).length} reports
            </span>
          </div>
          <p className="converge__cardtitle">{c.title}</p>
          <div className="converge__cardfoot">
            <span>{c.team}</span>
            <span>Dispatched</span>
          </div>
        </div>
      ))}
    </div>
  )
}
