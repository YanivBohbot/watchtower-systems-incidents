export type Zone = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  dwell_seconds: number;
};
export type User = {
  id: string;
  email: string;
  role: "admin" | "operator" | "viewer";
};
export type Video = {
  id: string;
  name: string;
  zone: Zone;
  created_at: string;
};
export type Job = {
  id: string;
  kind: string;
  resource_id: string;
  status: string;
  progress: number;
  error: string | null;
};
export type Document = { id: string; name: string; status: string };
export type Incident = {
  id: string;
  video_id: string;
  seconds: number;
  track_id: number;
  details: { confidence: number; zone: Zone };
};
export type Source = {
  id: string;
  document: string;
  page: number;
  text: string;
};
export type Report = {
  summary: string;
  findings: string[];
  recommendation: string;
  limitations: string[];
  sources: Source[];
  tool_trace: string[];
};
export type Investigation = {
  id: string;
  incident_id: string;
  status: string;
  report: Report | null;
  ticket: { id: string; title: string } | null;
};
export type CameraStatus = {
  state: "live" | "error";
  frames_analyzed: number;
  analysis_fps: number;
  last_seen: string;
  error: string | null;
};
export type Camera = {
  id: string;
  site: string;
  name: string;
  labels: string[];
  enabled: boolean;
  zone: Zone | null;
  status: CameraStatus | null;
};
export type Alert = {
  id: string;
  camera_id: string;
  kind: string;
  status: string;
  created_at: string;
  details: { confidence?: number; track_id?: number };
};
export type LiveEvent = { type: "alert"; alert: Alert };
