/**
 * The landing page.
 *
 * The one screen allowed a voice: display serif, a signature visual, and a
 * full-bleed band. Everything under `/ops` stays quiet, and the discipline
 * that governs it -- no shadows, mono for structured facts -- still governs
 * here, so the two read as one product rather than a site and a tool.
 */
import { Link } from 'react-router-dom'

import { Convergence } from '../components/landing/Convergence'
import { LedgerProof } from '../components/landing/LedgerProof'
import { StageIcon } from '../components/landing/StageIcon'

/** The pipeline, named as the system names it. Executor matches the ledger. */
const STAGES = [
  { n: '01', key: 'triage', name: 'Triage', text: 'Reads the report and names the fault.' },
  { n: '02', key: 'shortlist', name: 'Shortlist', text: 'Narrows to what is already open nearby.' },
  { n: '03', key: 'deduplicate', name: 'Deduplicate', text: 'Decides if this is one of them.' },
  { n: '04', key: 'prioritise', name: 'Prioritise', text: 'Sets urgency and a deadline.' },
  { n: '05', key: 'route', name: 'Route', text: 'Picks the team that owns the work.' },
  { n: '06', key: 'dispatch', name: 'Dispatch', text: 'Raises the ticket, in the reporter’s words.' },
]

export function Landing() {
  return (
    <>
      <section className="hero">
        <div className="hero__copy">
          <h1 className="display hero__title">From reports to repairs.</h1>
          <p className="hero__sub">
            Relay reads maintenance reports written in plain language, works out
            which ones describe the same underlying fault, and carries each problem
            through prioritisation, routing, and dispatch — keeping a record of why
            each call was made.
          </p>
          <div className="hero__actions">
            <Link to="/report" className="btn btn--primary btn--lg">
              Report an issue
            </Link>
            <Link to="/ops" className="btn btn--lg">
              View the ops dashboard
            </Link>
          </div>
          <p className="hero__aside">
            The dashboard is the internal view for facilities staff.
          </p>
        </div>

        <div className="hero__visual">
          <div className="hero__framing">
            <span className="label">As reported</span>
            <span className="hero__arrow" aria-hidden="true" />
            <span className="label">As Relay files it</span>
          </div>
          <Convergence />
        </div>
      </section>

      <section className="band">
        <div className="band__inner">
          <h2 className="display band__title">The gap</h2>
          <div className="problem">
            <div>
              <h3 className="problem__head">One fault, several tickets</h3>
              <p className="problem__body">
                Reporters describe the same problem differently, and a flat category
                dropdown has no way to tell that they mean one thing. Crews get
                dispatched more than once for the same job.
              </p>
            </div>
            <div>
              <h3 className="problem__head">Or several reports, none</h3>
              <p className="problem__body">
                Reports arriving hours apart are never connected, so a worsening
                fault reads as a series of unrelated minor complaints and waits
                behind work that matters less.
              </p>
            </div>
          </div>
          <p className="band__foot">
            Facilities teams lose most of their time to this gap rather than to the
            repairs themselves.
          </p>
        </div>
      </section>

      <section className="stages" id="how-it-works">
        <div className="stages__head">
          <h2 className="display band__title">What Relay does</h2>
          <p className="stages__lede">
            Two of these six are judgement calls. The rest apply the campus's own
            written policy, so the same evidence always produces the same answer —
            and an escalation stays defensible when someone asks why a work order
            jumped the queue.
          </p>
        </div>

        <ol className="stagegrid">
          {STAGES.map((stage) => (
            <li className="stage" key={stage.n}>
              <div className="stage__top">
                <StageIcon stage={stage.key} />
                <span className="stage__n">{stage.n}</span>
              </div>
              <h3 className="stage__name">{stage.name}</h3>
              <p className="stage__text">{stage.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="proofband">
        <div className="proofband__inner">
          <div>
            <h2 className="display band__title">Every call, on the record</h2>
            <p className="stages__lede">
              Each incident carries the reasoning behind every decision made about
              it — including the ones a person made. This is the actual view.
            </p>
          </div>
          <LedgerProof />
        </div>
      </section>

      <section className="closer">
        <div className="closer__inner">
          <h2 className="display closer__title">Two ways in.</h2>
          <div className="closer__actions">
            <Link to="/report" className="closer__card closer__card--primary">
              <span className="closer__cardtitle">Report an issue</span>
              <span className="closer__cardtext">
                Describe what is wrong in your own words. Relay handles the rest.
              </span>
            </Link>
            <Link to="/ops" className="closer__card">
              <span className="closer__cardtitle">View the ops dashboard</span>
              <span className="closer__cardtext">
                The internal board for facilities staff: the live queue, decision
                trails, and dispatch.
              </span>
            </Link>
          </div>
        </div>
      </section>

      <footer className="sitefoot">
        <span className="wordmark">Relay</span>
        <span className="sitefoot__note">Facilities coordination for university campuses</span>
      </footer>
    </>
  )
}
