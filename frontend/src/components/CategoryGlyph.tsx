/**
 * A mark for each kind of fault.
 *
 * Twelve glyphs, one stroke weight, drawn on a 16-unit grid so they sit on the
 * same optical line as the text beside them. They replace the bordered text
 * tags that used to name a category: the shape carries it, and a row stops
 * spending a rectangle on something a reader recognises at a glance.
 *
 * Never the only carrier -- every glyph is paired with its name in prose or an
 * accessible label, so nothing here depends on recognising an icon.
 */

const PATHS: Record<string, string> = {
  // droplet
  plumbing: 'M8 2.5c2.6 3 4.2 5 4.2 6.9A4.2 4.2 0 0 1 8 13.6a4.2 4.2 0 0 1-4.2-4.2C3.8 7.5 5.4 5.5 8 2.5Z',
  // bolt
  electrical: 'M9.2 2 4.4 8.9h3.1L6.8 14l4.8-6.9H8.5L9.2 2Z',
  // waves
  hvac: 'M2.5 5.5c1.5-1.4 3-1.4 4.5 0s3 1.4 4.5 0M2.5 9c1.5-1.4 3-1.4 4.5 0s3 1.4 4.5 0M2.5 12.5c1.5-1.4 3-1.4 4.5 0s3 1.4 4.5 0',
  // key
  access: 'M10.5 3a3 3 0 1 1-2.6 4.5L3 12.4V14h2v-1.4h1.6V11h1.5l1.1-1.1A3 3 0 0 1 10.5 3Z',
  // brush
  custodial: 'M6 10 3 13v1h1l3-3M9.5 2.5l4 4-4.5 4.5-4-4L9.5 2.5Z',
  // frame
  structural: 'M2.5 2.5h11v11h-11zM2.5 6h11M6 6v7.5',
  // shield
  safety: 'M8 2 3 4v4.5c0 3 2.2 5 5 5.5 2.8-.5 5-2.5 5-5.5V4L8 2Z',
  // leaf
  grounds: 'M3 13C3 7.5 6.5 3.5 13 3c.5 6.5-3.5 10-10 10ZM6 10c1.5-1.5 3.5-3 6-4',
  // monitor
  it_av: 'M2.5 3.5h11v7h-11zM6 13.5h4M8 10.5v3',
  // chevrons
  elevator: 'M8 2v12M5 5.5 8 2l3 3.5M5 10.5 8 14l3-3.5',
  // bug
  pest: 'M5.5 6a2.5 2.5 0 0 1 5 0v3a2.5 2.5 0 0 1-5 0V6ZM6 4.5 5 3.5M10 4.5l1-1M5.5 7.5h-2M12.5 7.5h-2M5.5 10.5l-2 1.5M12.5 10.5l-2 1.5',
  // dot
  other: 'M8 6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z',
}

const NAMES: Record<string, string> = {
  plumbing: 'Plumbing',
  electrical: 'Electrical',
  hvac: 'Heating and cooling',
  access: 'Access control',
  custodial: 'Custodial',
  structural: 'Structural',
  safety: 'Safety',
  grounds: 'Grounds',
  it_av: 'IT and AV',
  elevator: 'Elevator',
  pest: 'Pest control',
  other: 'Other',
}

interface CategoryGlyphProps {
  category: string | null
  /** Set when the name is not already beside it, so the mark stays readable. */
  labelled?: boolean
}

export function CategoryGlyph({ category, labelled = false }: CategoryGlyphProps) {
  const key = category ?? 'other'
  const path = PATHS[key] ?? PATHS.other
  const name = NAMES[key] ?? 'Other'

  return (
    <svg
      className="glyph__icon"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={labelled ? 'img' : 'presentation'}
      aria-label={labelled ? name : undefined}
      aria-hidden={labelled ? undefined : true}
    >
      <path d={path} />
    </svg>
  )
}
