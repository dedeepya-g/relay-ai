/**
 * The real interface, standing still.
 *
 * NOTE: this is a static mockup, not a rendering of live data. It borrows
 * DecisionLedger.tsx's own class names -- `.ledger`, `.event`,
 * `.event__quote`, `.event__meta`, `.entry`, `.entry--human`, `.entry__head`,
 * `.entry__who`, `.entry__why` -- so that it looks like the product rather
 * than like a drawing of it. That coupling is deliberate and it is also the
 * risk: nothing here breaks if those classes are renamed or their markup
 * changes, it just quietly stops matching. Spot-check this against the real
 * ledger whenever DecisionLedger.tsx's structure or class names move.
 *
 * A static rendering of an incident's trail using the board's own classes --
 * the same markers, spacing, type, and human-entry treatment the dashboard
 * draws. Not a diagram of the product: the product, held still so it can be
 * read.
 *
 * The content is representative rather than live. Nothing here is fetched,
 * because a marketing page should not depend on a campus having data.
 */

const ENTRIES = [
  {
    headline: 'Sorted as Plumbing',
    why: 'The report describes water coming through a ceiling, which is a plumbing fault rather than a custodial spill. The reporter gave a floor but no room.',
    human: false,
  },
  {
    headline: 'Added to an existing issue',
    why: 'Same building, same floor, and the same fault described from a later point in time. This is the leak already open as inc_7f3a2b91, not a second one.',
    human: false,
  },
  {
    headline: 'Set to Critical',
    why: 'Two people describe this as dangerous: water spreading toward an outlet. 4 people have reported it, which counts on its own. Needs someone now.',
    human: false,
  },
  {
    headline: 'Marked resolved · by someone here',
    why: 'Isolated the supply, replaced the failed joint, dried the corridor.',
    human: true,
  },
]

export function LedgerProof() {
  return (
    <div className="proof" aria-label="An incident's decision trail as it appears in the dashboard">
      <div className="proof__chrome">
        <span className="proof__title">Water spreading, Harlow Science Center</span>
        <span className="idtag">inc_7f3a2b91</span>
      </div>

      <div className="ledger">
        <section className="event">
          <span className="event__marker" aria-hidden="true" />
          <p className="event__quote">“Water coming through the ceiling on the third floor.”</p>
          <p className="event__meta">14:12:04 · Harlow Science Center · Floor 3</p>

          {ENTRIES.map((entry) => (
            <article
              key={entry.headline}
              className={`entry${entry.human ? ' entry--human' : ''}`}
            >
              <p className="entry__head">
                {entry.human ? (
                  <>
                    Marked resolved
                    <span className="entry__who"> · by someone here</span>
                  </>
                ) : (
                  entry.headline
                )}
              </p>
              <p className="entry__why">{entry.why}</p>
            </article>
          ))}
        </section>
      </div>
    </div>
  )
}
