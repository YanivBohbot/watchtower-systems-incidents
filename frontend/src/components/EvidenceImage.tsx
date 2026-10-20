import { useMedia } from "../api/media";
import type { Incident } from "../api/types";

/** The evidence capture saved for an incident, with its time code. */
export default function EvidenceImage({
  incident,
  token,
}: {
  incident: Incident;
  token: string;
}) {
  const { url, error } = useMedia(`/incidents/${incident.id}/evidence`, token);
  return (
    <div className="evidence">
      {url ? (
        <img
          src={url}
          alt={`Capture at ${incident.seconds.toFixed(1)} seconds`}
        />
      ) : (
        <span>{error || "Loading evidence…"}</span>
      )}
      <span className="timecode">{incident.seconds.toFixed(1)} s</span>
    </div>
  );
}
