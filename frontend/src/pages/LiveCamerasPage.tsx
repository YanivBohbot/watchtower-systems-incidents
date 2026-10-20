import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera as CameraIcon, Siren, X } from "lucide-react";
import { mediaUrl, request, streamEvents } from "../api/client";
import type { Alert, Camera } from "../api/types";

const kinds: Record<string, string> = {
  person_dwell: "Person in restricted zone",
};

function time(value: string) {
  return new Date(value).toLocaleTimeString();
}

/** Latest annotated frame, refreshed twice a second while the page is visible. */
function useFrame(cameraId: string, token: string) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let current = "";
    let busy = false;
    const abort = new AbortController();
    async function load() {
      if (busy || document.hidden) return;
      busy = true;
      try {
        const next = await mediaUrl(
          `/cameras/${cameraId}/frame`,
          token,
          abort.signal,
        );
        if (current) URL.revokeObjectURL(current);
        current = next;
        setUrl(next);
      } catch {
        if (!abort.signal.aborted) setUrl("");
      } finally {
        busy = false;
      }
    }
    void load();
    const timer = setInterval(() => void load(), 500);
    return () => {
      clearInterval(timer);
      abort.abort();
      if (current) URL.revokeObjectURL(current);
    };
  }, [cameraId, token]);
  return url;
}

function Tile({
  camera,
  token,
  alerting,
}: {
  camera: Camera;
  token: string;
  alerting: boolean;
}) {
  const url = useFrame(camera.id, token);
  const status = camera.status;
  const offline = !status || status.state !== "live";
  return (
    <figure
      className={`camera-tile${alerting ? " alerting" : ""}`}
      aria-label={`Camera ${camera.name}`}
    >
      {url && !offline ? (
        <img src={url} alt={`Live view of ${camera.name}`} />
      ) : (
        <span className="camera-offline">
          {status?.state === "error" ? "Source error" : "Offline"}
        </span>
      )}
      <figcaption>
        <strong>{camera.name}</strong>
        <span>
          {status
            ? `${status.frames_analyzed.toLocaleString()} frames analyzed`
            : "No signal"}
        </span>
      </figcaption>
    </figure>
  );
}

function Snapshot({ alert, token }: { alert: Alert; token: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    let current = "";
    mediaUrl(`/alerts/${alert.id}/snapshot`, token, abort.signal)
      .then((value) => {
        current = value;
        setUrl(value);
      })
      .catch(() => undefined);
    return () => {
      abort.abort();
      if (current) URL.revokeObjectURL(current);
    };
  }, [alert.id, token]);
  return url ? (
    <img className="alert-snapshot" src={url} alt="Alert snapshot" />
  ) : null;
}

export default function LiveCamerasPage({ token }: { token: string }) {
  const queryClient = useQueryClient();
  const cameras = useQuery({
    queryKey: ["cameras", token],
    queryFn: () => request<Camera[]>("/cameras", token),
    refetchInterval: 3000,
  });
  const alerts = useQuery({
    queryKey: ["alerts", token],
    queryFn: () => request<Alert[]>("/alerts?limit=20", token),
    refetchInterval: 10000, // fallback when the event stream is down
  });
  const [active, setActive] = useState<Alert[]>([]);
  const [seen, setSeen] = useState<Set<string> | null>(null);
  useEffect(() => {
    if (!alerts.data) return;
    if (seen === null) {
      // Alerts that existed when the wall opened stay in the list, not the banner.
      setSeen(new Set(alerts.data.map((a) => a.id)));
      return;
    }
    const fresh = alerts.data.filter((a) => !seen.has(a.id));
    if (!fresh.length) return;
    setSeen(new Set([...seen, ...fresh.map((a) => a.id)]));
    setActive((list) => [
      ...fresh.filter((a) => !list.some((b) => b.id === a.id)),
      ...list,
    ]);
  }, [alerts.data, seen]);
  const [open, setOpen] = useState("");
  const [connected, setConnected] = useState(false);
  useEffect(
    () =>
      streamEvents(
        token,
        (event) => {
          if (event.type !== "alert") return;
          setSeen((ids) => (ids ? new Set([...ids, event.alert.id]) : ids));
          setActive((list) => [
            event.alert,
            ...list.filter((a) => a.id !== event.alert.id),
          ]);
          void queryClient.invalidateQueries({ queryKey: ["alerts"] });
        },
        () => {
          setConnected(true);
          // Anything raised while disconnected reaches the banner through the list.
          void queryClient.invalidateQueries({ queryKey: ["alerts"] });
        },
        () => setConnected(false),
      ),
    [token, queryClient],
  );
  const names = new Map(cameras.data?.map((c) => [c.id, c.name]) || []);
  const alerting = new Set(active.map((a) => a.camera_id));
  const current = active[0];
  return (
    <div className="live">
      <section className="panel">
        <div className="panel-heading">
          <h2>
            <CameraIcon size={17} /> Camera wall
          </h2>
          <span className={`live-state${connected ? " on" : ""}`}>
            {connected ? "LIVE" : "CONNECTING"}
          </span>
        </div>
        {cameras.data?.length ? (
          <div className="camera-wall">
            {cameras.data.map((camera) => (
              <Tile
                key={camera.id}
                camera={camera}
                token={token}
                alerting={alerting.has(camera.id)}
              />
            ))}
          </div>
        ) : (
          <p className="empty-live">
            No camera yet. Load a site with{" "}
            <code>python -m app.cli seed-site FILE</code>.
          </p>
        )}
        {current && (
          <div role="alert" className="alert-banner">
            <div className="alert-line">
              <Siren size={18} />
              <strong>
                Alert · {names.get(current.camera_id) || "camera"}
              </strong>
              <span>
                {kinds[current.kind] || current.kind}
                {current.details.confidence !== undefined &&
                  ` · ${Math.round(current.details.confidence * 100)}%`}
                {` · ${time(current.created_at)}`}
              </span>
              {active.length > 1 && (
                <span className="alert-more">+{active.length - 1} more</span>
              )}
            </div>
            <div className="alert-actions">
              <button
                onClick={() => setOpen(open === current.id ? "" : current.id)}
              >
                {open === current.id ? "Hide snapshot" : "View snapshot"}
              </button>
              <button
                aria-label="Dismiss alert"
                onClick={() =>
                  setActive((list) => list.filter((a) => a.id !== current.id))
                }
              >
                <X size={15} /> Dismiss
              </button>
            </div>
            {open === current.id && <Snapshot alert={current} token={token} />}
          </div>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>
            <Siren size={17} /> Recent alerts
          </h2>
        </div>
        {alerts.data?.length ? (
          <ul className="alert-list">
            {alerts.data.map((alert) => (
              <li key={alert.id}>
                <strong>{names.get(alert.camera_id) || "camera"}</strong>
                <span>{kinds[alert.kind] || alert.kind}</span>
                <time>{time(alert.created_at)}</time>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty-live">No alert so far.</p>
        )}
      </section>
    </div>
  );
}
