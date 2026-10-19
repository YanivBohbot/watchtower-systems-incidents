import { useRef, useState } from "react";
import type { PointerEvent } from "react";
import type { Zone } from "./types";

export default function ZoneEditor({
  src,
  zone,
  onChange,
}: {
  src: string;
  zone: Zone;
  onChange: (zone: Zone) => void;
}) {
  const overlay = useRef<HTMLDivElement>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const [ratio, setRatio] = useState(16 / 9);
  const [editing, setEditing] = useState(true);
  function point(event: PointerEvent) {
    const box = overlay.current!.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)),
      y: Math.max(0, Math.min(1, (event.clientY - box.top) / box.height)),
    };
  }
  function move(event: PointerEvent) {
    if (!start.current) return;
    const end = point(event),
      p = start.current;
    const next = {
      ...zone,
      x1: Math.min(p.x, end.x),
      y1: Math.min(p.y, end.y),
      x2: Math.max(p.x, end.x),
      y2: Math.max(p.y, end.y),
    };
    if (next.x2 - next.x1 > 0.005 && next.y2 - next.y1 > 0.005) onChange(next);
  }
  return (
    <div>
      <div className="video-stage" style={{ aspectRatio: ratio }}>
        <video
          src={src}
          muted
          controls
          onLoadedMetadata={(e) =>
            setRatio(e.currentTarget.videoWidth / e.currentTarget.videoHeight)
          }
        />
        <div
          ref={overlay}
          className="zone-overlay"
          style={{ pointerEvents: editing ? "auto" : "none" }}
          onPointerDown={(e) => {
            start.current = point(e);
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={move}
          onPointerUp={(e) => {
            move(e);
            start.current = null;
          }}
          onPointerCancel={() => {
            start.current = null;
          }}
        >
          <div
            className="zone-rectangle"
            style={{
              left: `${zone.x1 * 100}%`,
              top: `${zone.y1 * 100}%`,
              width: `${(zone.x2 - zone.x1) * 100}%`,
              height: `${(zone.y2 - zone.y1) * 100}%`,
            }}
          >
            <span>ZONE A</span>
          </div>
        </div>
      </div>
      <p className="hint">
        {editing
          ? "Drag on the image to define the zone."
          : "Selection locked; you can play the video."}{" "}
        <button
          type="button"
          className="text-button"
          onClick={() => setEditing(!editing)}
        >
          {editing ? "Finish selection" : "Edit zone"}
        </button>
      </p>
    </div>
  );
}
