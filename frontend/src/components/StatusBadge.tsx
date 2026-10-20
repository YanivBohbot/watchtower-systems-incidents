const labels: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  indexed: "Indexed",
  indexing: "Indexing",
  awaiting_review: "Awaiting review",
  approved: "Approved",
  rejected: "Rejected",
  review_queued: "Review in progress",
};

/** Human-readable label for a job, document or investigation status. */
export default function StatusBadge({ value }: { value: string }) {
  return <span className={`status ${value}`}>{labels[value] || value}</span>;
}
