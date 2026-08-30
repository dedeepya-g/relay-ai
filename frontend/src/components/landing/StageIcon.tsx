/**
 * One mark per pipeline stage.
 *
 * Same grid and stroke weight as the category glyphs, so the two sets read as
 * one system. Each stage card leads with its mark, which lets the description
 * underneath be a single line instead of a paragraph.
 */

const PATHS: Record<string, string> = {
  // page with a line being read
  triage: 'M4 2.5h6l2.5 2.5v8.5h-8.5V2.5ZM10 2.5V5h2.5M5.75 8h4.5M5.75 10.5h3',
  // funnel narrowing
  shortlist: 'M2.5 3h11l-4.25 5v5l-2.5-1.5V8L2.5 3Z',
  // two overlapping rings
  deduplicate: 'M6.25 10.5a3.25 3.25 0 1 1 0-6.5 3.25 3.25 0 0 1 0 6.5ZM9.75 10.5a3.25 3.25 0 1 1 0-6.5 3.25 3.25 0 0 1 0 6.5Z',
  // ranked bars
  prioritise: 'M3.5 12.5V9M8 12.5V5.5M12.5 12.5V3',
  // arrow into a lane
  route: 'M2.5 8h8.5M8 5l3 3-3 3M13.5 3.5v9',
  // ticket
  dispatch: 'M2.5 5.5h11v2a1.2 1.2 0 0 0 0 2.4v2.6h-11V9.9a1.2 1.2 0 0 0 0-2.4V5.5ZM6.5 5.5v7',
}

export function StageIcon({ stage }: { stage: string }) {
  return (
    <svg
      className="stage__icon"
      viewBox="0 0 16 16"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[stage] ?? PATHS.triage} />
    </svg>
  )
}
