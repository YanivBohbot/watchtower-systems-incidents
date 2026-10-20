import { Check, FileText, ShieldCheck } from "lucide-react";
import type { Investigation } from "../api/types";
import StatusBadge from "../components/StatusBadge";

export type ReviewDecision = { approved: boolean; create_ticket: boolean };

/** Agent reports with their sources and limitations, and the human review buttons. */
export default function InvestigationsPage({
  investigations,
  canWrite,
  busy,
  onReview,
}: {
  investigations: Investigation[] | undefined;
  canWrite: boolean;
  busy: boolean;
  onReview: (investigationId: string, decision: ReviewDecision) => void;
}) {
  return (
    <section className="investigations-list">
      {!investigations?.length ? (
        <div className="panel empty">
          <ShieldCheck />
          <h3>No investigations yet</h3>
          <p>Start an investigation from a detected event.</p>
        </div>
      ) : (
        investigations.map((inv) => (
          <article className="panel report" key={inv.id}>
            <div className="panel-heading">
              <h2>Investigation {inv.id.slice(0, 8)}</h2>
              <StatusBadge value={inv.status} />
            </div>
            {inv.report ? (
              <>
                <h3>{inv.report.summary}</h3>
                <ul>
                  {inv.report.findings.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
                <div className="recommendation">
                  <span className="eyebrow">RECOMMENDATION</span>
                  <p>{inv.report.recommendation}</p>
                </div>
                {inv.report.sources.map((source) => (
                  <details key={source.id}>
                    <summary>
                      <FileText size={14} /> {source.document} · page{" "}
                      {source.page}
                    </summary>
                    <blockquote>{source.text}</blockquote>
                    <small>Reference: {source.id}</small>
                  </details>
                ))}
                {inv.report.limitations.length > 0 && (
                  <div className="limitations">
                    <strong>Limitations to consider</strong>
                    <ul>
                      {inv.report.limitations.map((v, i) => (
                        <li key={i}>{v}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <small className="hint">
                  Local tools used:{" "}
                  {inv.report.tool_trace.join(" → ") || "none"}
                </small>
                {inv.status === "awaiting_review" && canWrite && (
                  <div className="review-actions">
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() =>
                        onReview(inv.id, { approved: true, create_ticket: true })
                      }
                    >
                      <Check size={16} /> Approve and create ticket
                    </button>
                    <button
                      disabled={busy}
                      onClick={() =>
                        onReview(inv.id, {
                          approved: true,
                          create_ticket: false,
                        })
                      }
                    >
                      Approve without ticket
                    </button>
                    <button
                      className="danger"
                      disabled={busy}
                      onClick={() =>
                        onReview(inv.id, {
                          approved: false,
                          create_ticket: false,
                        })
                      }
                    >
                      Reject
                    </button>
                  </div>
                )}
                {inv.ticket && (
                  <div className="ticket">
                    <Check size={17} /> Ticket created via MCP · {inv.ticket.id}
                  </div>
                )}
              </>
            ) : (
              <p className="section-description">
                Processing is queued or running. Check the jobs below for any
                errors.
              </p>
            )}
          </article>
        ))
      )}
    </section>
  );
}
