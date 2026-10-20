import { Activity } from "lucide-react";
import type { Job } from "../api/types";
import StatusBadge from "./StatusBadge";

/** Table of the latest background jobs, shown under every tab. */
export default function JobActivity({
  jobs,
  canWrite,
  busy,
  onRetry,
}: {
  jobs: Job[] | undefined;
  canWrite: boolean;
  busy: boolean;
  onRetry: (jobId: string) => void;
}) {
  return (
    <section className="panel jobs">
      <div className="panel-heading">
        <h2>
          <Activity size={17} /> Job activity
        </h2>
        <span className="subtle">AUTO-REFRESH</span>
      </div>
      {!jobs?.length ? (
        <p className="section-description">
          Analyses, indexing and investigations will appear here.
        </p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>ID</th>
                <th>Progress</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td>{job.kind}</td>
                  <td>
                    <code>{job.id.slice(0, 8)}</code>
                    {job.error && (
                      <small className="job-error">{job.error}</small>
                    )}
                  </td>
                  <td>
                    <progress max="100" value={job.progress} />
                  </td>
                  <td>
                    <StatusBadge value={job.status} />
                  </td>
                  <td>
                    {job.status === "failed" && canWrite && (
                      <button disabled={busy} onClick={() => onRetry(job.id)}>
                        Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
