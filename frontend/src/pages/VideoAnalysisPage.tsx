import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Activity, ArrowRight, Film, Radar, Upload } from "lucide-react";
import { useMedia } from "../api/media";
import type { Incident, Video, Zone } from "../api/types";
import EvidenceImage from "../components/EvidenceImage";
import ZoneEditor from "../components/ZoneEditor";

const initialZone: Zone = {
  x1: 0.3,
  y1: 0.2,
  x2: 0.8,
  y2: 0.85,
  dwell_seconds: 3,
};

/**
 * The video being prepared (file + zone) and the selected video. Held by App so
 * they survive a switch to another tab and back.
 */
export function useVideoDraft() {
  const [file, setFile] = useState<File | null>(null);
  const [zone, setZone] = useState<Zone>(initialZone);
  const [selected, setSelected] = useState("");
  return { file, setFile, zone, setZone, selected, setSelected };
}

export type VideoDraft = ReturnType<typeof useVideoDraft>;

/** Upload a video with a watch zone, play it back, and list the events it produced. */
export default function VideoAnalysisPage({
  token,
  canWrite,
  videos,
  incidents,
  draft,
  uploading,
  onStartAnalysis,
  busy,
  onInvestigate,
}: {
  token: string;
  canWrite: boolean;
  videos: Video[] | undefined;
  incidents: Incident[] | undefined;
  draft: VideoDraft;
  uploading: boolean;
  onStartAnalysis: () => void;
  busy: boolean;
  onInvestigate: (incidentId: string) => void;
}) {
  const { file, setFile, zone, setZone, selected, setSelected } = draft;
  const [localUrl, setLocalUrl] = useState("");
  const activeVideo = videos?.find((v) => v.id === selected) || videos?.[0];
  const serverMedia = useMedia(
    !file && activeVideo ? `/videos/${activeVideo.id}/content` : null,
    token,
  );
  useEffect(() => {
    if (!file) {
      setLocalUrl("");
      return;
    }
    const url = URL.createObjectURL(file);
    setLocalUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const visibleIncidents =
    incidents?.filter((i) => i.video_id === activeVideo?.id) || [];
  return (
    <div className="workspace-grid">
      <section className="panel video-panel">
        <div className="panel-heading">
          <h2>
            <Film size={17} /> Video analysis
          </h2>
          <span className="subtle">UPLOADED FILES</span>
        </div>
        <div className="video-controls">
          <select
            aria-label="Video"
            value={activeVideo?.id || ""}
            onChange={(e) => {
              setSelected(e.target.value);
              setFile(null);
            }}
          >
            <option value="" disabled>
              Choose a video
            </option>
            {videos?.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          {canWrite && (
            <label className="button secondary">
              <Upload size={15} /> Upload
              <input
                type="file"
                accept="video/mp4,video/quicktime,video/x-msvideo,video/webm"
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null);
                  setZone(initialZone);
                }}
                hidden
              />
            </label>
          )}
        </div>
        {file && localUrl ? (
          <ZoneEditor src={localUrl} zone={zone} onChange={setZone} />
        ) : serverMedia.url ? (
          <div className="video-stage">
            <video src={serverMedia.url} controls />
          </div>
        ) : (
          <div className="empty-video">
            <Radar size={46} />
            <h3>Your first analysis starts here.</h3>
            <p>
              {serverMedia.error ||
                "A 30 to 60 second video from a fixed camera is enough to get started."}
            </p>
          </div>
        )}
        {file && (
          <form
            className="analysis-settings"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              onStartAnalysis();
            }}
          >
            <div>
              <strong>{file.name}</strong>
              <span className="hint">
                Rectangular zone · tracked point: bottom of the detection box
              </span>
            </div>
            <label>
              Minimum presence (s)
              <input
                type="number"
                min="0.1"
                max="600"
                step="0.1"
                value={zone.dwell_seconds}
                onChange={(e) =>
                  setZone({
                    ...zone,
                    dwell_seconds: Number(e.target.value),
                  })
                }
              />
            </label>
            <button className="primary" disabled={uploading}>
              Start analysis <ArrowRight size={15} />
            </button>
          </form>
        )}
        {!file && activeVideo && (
          <div className="video-info">
            <span>Zone A · threshold {activeVideo.zone.dwell_seconds} s</span>
            <span>{activeVideo.name}</span>
          </div>
        )}
      </section>
      <section className="panel events-panel">
        <div className="panel-heading">
          <h2>Events</h2>
          <span className="count">{visibleIncidents.length}</span>
        </div>
        {visibleIncidents.length === 0 ? (
          <div className="empty">
            <Activity size={28} />
            <h3>No events for this video</h3>
            <p>Events will appear here when the presence rule is met.</p>
          </div>
        ) : (
          visibleIncidents.map((incident) => (
            <article className="incident" key={incident.id}>
              <EvidenceImage incident={incident} token={token} />
              <div>
                <span className="eyebrow">PRESENCE IN ZONE A</span>
                <h3>Presence threshold exceeded</h3>
                <p>
                  Track #{incident.track_id} · detector score{" "}
                  {(incident.details.confidence * 100).toFixed(0)} %
                </p>
                {canWrite && (
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => onInvestigate(incident.id)}
                  >
                    Open an investigation <ArrowRight size={15} />
                  </button>
                )}
              </div>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
