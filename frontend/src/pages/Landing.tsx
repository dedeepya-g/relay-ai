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

/** The pipeline, named as the system names it. Executor matches the ledger. */
const STAGES = [
  {
    n: '01',
    name: 'Triage',
    by: 'model',
    text: 'Reads the report and returns its category, any wording that signals urgency, and which location details the reporter left out.',
  },
  {
    n: '02',
    name: 'Shortlist',
    by: 'query',
    text: 'Narrows the comparison to incidents already open in the same building, so the judgement below is made against a plausible few.',
  },
  {
    n: '03',
    name: 'Deduplicate',
    by: 'model',
    text: 'Decides whether the report describes a fault already being tracked, a separate one, or something too ambiguous to call.',
  },
  {
    n: '04',
    name: 'Prioritise',
    by: 'rule',
    text: 'Sets priority and a deadline from how many people reported the fault and how many described danger.',
  },
  {
    n: '05',
    name: 'Route',
    by: 'rule',
    text: 'Assigns the maintenance team that owns this category of work on this campus.',
  },
  {
    n: '06',
    name: 'Dispatch',
    by: 'rule',
    text: 'Raises a work order with field instructions built from what each reporter actually said.',
  },
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
            through prioritisation, routing, and dispatch — recording the reasoning
            behind every decision.
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
          <Convergence />
        </div>
      </section>

      <section className="band">
        <div className="band__inner">
          <h2 className="display band__title">The handoff gap</h2>
          <div className="problem">
            <div>
              <h3 className="problem__head">One fault becomes several tickets</h3>
              <p className="problem__body">
                Reporters describe the same problem differently, and a flat category
                dropdown has no way to tell that they mean one thing. Crews get
                dispatched more than once for the same job.
              </p>
            </div>
            <div>
              <h3 className="problem__head">Or several reports become none</h3>
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
            Six stages. A model is used in exactly two of them, both genuine
            judgements about ambiguous language. Everything after is deterministic
            rule application over campus configuration, so the same evidence always
            produces the same priority, the same team, and the same escalation.
          </p>
        </div>

        <ol className="stagegrid">
          {STAGES.map((stage) => (
            <li className="stage" key={stage.n}>
              <div className="stage__top">
                <span className="stage__n">{stage.n}</span>
                <span className={`stage__by stage__by--${stage.by}`}>{stage.by}</span>
              </div>
              <h3 className="stage__name">{stage.name}</h3>
              <p className="stage__text">{stage.text}</p>
            </li>
          ))}
        </ol>
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
        <span className="sitefoot__note">AI facilities coordination for university campuses</span>
      </footer>
    </>
  )
}
