import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Check,
  ChevronRight,
  FileText,
  Film,
  LogOut,
  MonitorPlay,
  Radar,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import { mediaUrl, request } from "./api";
import LiveWall from "./LiveWall";
import ZoneEditor from "./ZoneEditor";
import type {
  Document,
  Incident,
  Investigation,
  Job,
  User,
  Video,
  Zone,
} from "./types";

const initialZone: Zone = {
  x1: 0.3,
  y1: 0.2,
  x2: 0.8,
  y2: 0.85,
  dwell_seconds: 3,
};
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

function Status({ value }: { value: string }) {
  return <span className={`status ${value}`}>{labels[value] || value}</span>;
}

function useMedia(path: string | null, token: string) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    setUrl("");
    setError("");
    if (!path) return;
    const abort = new AbortController();
    let current = "";
    mediaUrl(path, token, abort.signal)
      .then((value) => {
        current = value;
        if (abort.signal.aborted) URL.revokeObjectURL(value);
        else setUrl(value);
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(String(e));
      });
    return () => {
      abort.abort();
      if (current) URL.revokeObjectURL(current);
    };
  }, [path, token]);
  return { url, error };
}

function Evidence({ incident, token }: { incident: Incident; token: string }) {
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

function Login({ onLogin }: { onLogin: (token: string) => void }) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const login = useMutation({
    mutationFn: () =>
      request<{ access_token: string }>("/auth/login", "", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    onSuccess: (r) => onLogin(r.access_token),
  });
  return (
    <div className="login-page">
      <div className="login-copy">
        <div className="brand">
          <Radar /> WATCHTOWER
        </div>
        <span className="eyebrow">VIDEO INCIDENT INTELLIGENCE</span>
        <h1>
          Observations.
          <br />
          Evidence.
          <br />
          <em>Informed decisions.</em>
        </h1>
        <p>
          Video analysis, documented procedures and assisted investigation, in a
          single workspace.
        </p>
      </div>
      <form
        className="login-card"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <span className="eyebrow">OPERATOR WORKSPACE</span>
        <h2>Welcome.</h2>
        <p>Sign in with the account created during setup.</p>
        <label>
          Email address
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {login.error && (
          <p role="alert" className="error">
            {login.error.message}
          </p>
        )}
        <button className="primary" disabled={login.isPending}>
          Sign in <ArrowRight size={16} />
        </button>
        <small>Reports always require human review.</small>
      </form>
    </div>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(
    () => sessionStorage.getItem("watchtower-token") || "",
  );
  const [tab, setTab] = useState<
    "live" | "workspace" | "knowledge" | "investigations"
  >("live");
  const [file, setFile] = useState<File | null>(null),
    [localUrl, setLocalUrl] = useState("");
  const [zone, setZone] = useState<Zone>(initialZone),
    [selected, setSelected] = useState("");
  const [notice, setNotice] = useState("");
  const user = useQuery({
    queryKey: ["me", token],
    queryFn: () => request<User>("/me", token),
    enabled: !!token,
    retry: false,
  });
  function useList<T>(name: string) {
    return useQuery({
      queryKey: [name, token],
      queryFn: () => request<T[]>(`/${name}`, token),
      enabled: !!token && !!user.data,
      refetchInterval: 2500,
    });
  }
  const videos = useList<Video>("videos"),
    jobs = useList<Job>("jobs"),
    documents = useList<Document>("documents"),
    incidents = useList<Incident>("incidents"),
    investigations = useList<Investigation>("investigations");
  const activeVideo =
    videos.data?.find((v) => v.id === selected) || videos.data?.[0];
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
  function refresh() {
    void queryClient.invalidateQueries();
  }
  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Select a video");
      const body = new FormData();
      body.append("file", file);
      body.append("zone", JSON.stringify(zone));
      return request<Video>("/videos", token, { method: "POST", body });
    },
    onSuccess: (v) => {
      setSelected(v.id);
      setFile(null);
      setNotice("Video saved. Processing has started in the background.");
      refresh();
    },
  });
  const docUpload = useMutation({
    mutationFn: (doc: File) => {
      const body = new FormData();
      body.append("file", doc);
      return request("/documents", token, { method: "POST", body });
    },
    onSuccess: () => {
      setNotice("Document saved. Check its indexing status.");
      refresh();
    },
  });
  const action = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: object }) =>
      request(path, token, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      }),
    onSuccess: () => {
      refresh();
      setNotice("Request saved.");
    },
  });
  function connect(value: string) {
    sessionStorage.setItem("watchtower-token", value);
    setToken(value);
  }
  function logout() {
    sessionStorage.removeItem("watchtower-token");
    setToken("");
    queryClient.clear();
  }
  if (!token) return <Login onLogin={connect} />;
  if (user.isError)
    return (
      <div className="center">
        <h2>Session expired or server unavailable</h2>
        <p>{user.error.message}</p>
        <button onClick={logout}>Back to sign in</button>
      </div>
    );
  if (!user.data)
    return <div className="center">Connecting to WatchTower…</div>;
  const canWrite = user.data.role !== "viewer";
  const pending =
    jobs.data?.filter((j) => j.status === "running" || j.status === "queued")
      .length || 0;
  const reviews =
    investigations.data?.filter((i) => i.status === "awaiting_review").length ||
    0;
  const error =
    upload.error ||
    docUpload.error ||
    action.error ||
    videos.error ||
    documents.error ||
    incidents.error ||
    investigations.error ||
    jobs.error;
  const visibleIncidents =
    incidents.data?.filter((i) => i.video_id === activeVideo?.id) || [];
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Radar size={27} /> WATCHTOWER<span>INTELLIGENCE WORKSPACE</span>
        </div>
        <div className="nav-label">YOUR WORKSPACE</div>
        <nav>
          <button
            className={tab === "live" ? "active" : ""}
            onClick={() => setTab("live")}
          >
            <MonitorPlay size={18} /> Live cameras
          </button>
          <button
            className={tab === "workspace" ? "active" : ""}
            onClick={() => setTab("workspace")}
          >
            <Film size={18} /> Video analysis <ChevronRight size={14} />
          </button>
          <button
            className={tab === "knowledge" ? "active" : ""}
            onClick={() => setTab("knowledge")}
          >
            <FileText size={18} /> Procedures
          </button>
          <button
            className={tab === "investigations" ? "active" : ""}
            onClick={() => setTab("investigations")}
          >
            <ShieldCheck size={18} /> Investigations{" "}
            {reviews > 0 && <b>{reviews}</b>}
          </button>
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={20} />
          <strong>You keep the final say.</strong>
          <p>
            The agent gathers the facts. You approve the conclusions and the
            actions.
          </p>
        </div>
        <div className="account">
          <div className="avatar">{user.data.email[0].toUpperCase()}</div>
          <div>
            <strong>{user.data.email.split("@")[0]}</strong>
            <small>{user.data.role}</small>
          </div>
          <button aria-label="Sign out" onClick={logout}>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <main>
        <header>
          <span>
            Workspace <ChevronRight size={13} />{" "}
            {tab === "live"
              ? "Live cameras"
              : tab === "workspace"
                ? "Video analysis"
                : tab === "knowledge"
                  ? "Procedures"
                  : "Investigations"}
          </span>
          <span className="environment">
            <i /> LOCAL ENVIRONMENT
          </span>
        </header>
        <div className="page-heading">
          <div>
            <span className="eyebrow">FROM OBSERVATION TO ACTION</span>
            <h1>
              {tab === "live"
                ? "Every camera at a glance."
                : tab === "workspace"
                  ? "A clear view of every event."
                  : tab === "knowledge"
                    ? "The context behind every decision."
                    : "Conclusions you can verify."}
            </h1>
            <p>
              {tab === "live"
                ? "Alerts reach you within seconds. You decide what happens next."
                : tab === "workspace"
                  ? "Upload a video, define a zone and find all the evidence in one place."
                  : tab === "knowledge"
                    ? "Indexed procedures feed investigations with verifiable references."
                    : "Review the observations, sources and limitations before approving a report."}
            </p>
          </div>
        </div>
        {error && (
          <div role="alert" className="banner error">
            {error.message}
          </div>
        )}
        {notice && (
          <div role="status" className="banner">
            {notice}
            <button aria-label="Close" onClick={() => setNotice("")}>
              <X size={15} />
            </button>
          </div>
        )}
        <section className="stats">
          <div>
            <Film />
            <span>Uploaded videos</span>
            <strong>{videos.data?.length || 0}</strong>
          </div>
          <div>
            <Activity />
            <span>Detected events</span>
            <strong>{incidents.data?.length || 0}</strong>
          </div>
          <div>
            <ShieldCheck />
            <span>Reports to review</span>
            <strong>{reviews}</strong>
          </div>
          <div>
            <span className="live-dot" />
            <span>Active jobs</span>
            <strong>{pending}</strong>
          </div>
        </section>
        {tab === "live" && <LiveWall token={token} />}
        {tab === "workspace" && (
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
                  {videos.data?.map((v) => (
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
                    upload.mutate();
                  }}
                >
                  <div>
                    <strong>{file.name}</strong>
                    <span className="hint">
                      Rectangular zone · tracked point: bottom of the detection
                      box
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
                  <button className="primary" disabled={upload.isPending}>
                    Start analysis <ArrowRight size={15} />
                  </button>
                </form>
              )}
              {!file && activeVideo && (
                <div className="video-info">
                  <span>
                    Zone A · threshold {activeVideo.zone.dwell_seconds} s
                  </span>
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
                    <Evidence incident={incident} token={token} />
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
                          disabled={action.isPending}
                          onClick={() => {
                            action.mutate({
                              path: `/incidents/${incident.id}/investigate`,
                            });
                            setTab("investigations");
                          }}
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
        )}
        {tab === "knowledge" && (
          <section className="panel">
            <div className="panel-heading">
              <h2>Procedure library</h2>
              {canWrite && (
                <label className="button primary">
                  <Upload size={15} /> Add a document
                  <input
                    type="file"
                    accept=".pdf,.txt"
                    hidden
                    disabled={docUpload.isPending}
                    onChange={(e) => {
                      if (e.target.files?.[0])
                        docUpload.mutate(e.target.files[0]);
                      e.target.value = "";
                    }}
                  />
                </label>
              )}
            </div>
            <p className="section-description">
              Text-based PDF or UTF-8 TXT. Each passage keeps its document name
              and page number. Scanned PDFs require OCR, which is not included
              in this version.
            </p>
            {!documents.data?.length ? (
              <div className="empty">
                <FileText />
                <h3>Add your first procedure</h3>
                <p>
                  A sample demo procedure is provided in the examples folder.
                </p>
              </div>
            ) : (
              documents.data.map((doc) => (
                <div className="document-row" key={doc.id}>
                  <FileText />
                  <div>
                    <strong>{doc.name}</strong>
                    <small>{doc.id.slice(0, 8)}</small>
                  </div>
                  <Status value={doc.status} />
                </div>
              ))
            )}
          </section>
        )}
        {tab === "investigations" && (
          <section className="investigations-list">
            {!investigations.data?.length ? (
              <div className="panel empty">
                <ShieldCheck />
                <h3>No investigations yet</h3>
                <p>Start an investigation from a detected event.</p>
              </div>
            ) : (
              investigations.data.map((inv) => (
                <article className="panel report" key={inv.id}>
                  <div className="panel-heading">
                    <h2>Investigation {inv.id.slice(0, 8)}</h2>
                    <Status value={inv.status} />
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
                            disabled={action.isPending}
                            onClick={() =>
                              action.mutate({
                                path: `/investigations/${inv.id}/review`,
                                body: { approved: true, create_ticket: true },
                              })
                            }
                          >
                            <Check size={16} /> Approve and create ticket
                          </button>
                          <button
                            disabled={action.isPending}
                            onClick={() =>
                              action.mutate({
                                path: `/investigations/${inv.id}/review`,
                                body: { approved: true, create_ticket: false },
                              })
                            }
                          >
                            Approve without ticket
                          </button>
                          <button
                            className="danger"
                            disabled={action.isPending}
                            onClick={() =>
                              action.mutate({
                                path: `/investigations/${inv.id}/review`,
                                body: { approved: false, create_ticket: false },
                              })
                            }
                          >
                            Reject
                          </button>
                        </div>
                      )}
                      {inv.ticket && (
                        <div className="ticket">
                          <Check size={17} /> Ticket created via MCP ·{" "}
                          {inv.ticket.id}
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="section-description">
                      Processing is queued or running. Check the jobs below for
                      any errors.
                    </p>
                  )}
                </article>
              ))
            )}
          </section>
        )}
        <section className="panel jobs">
          <div className="panel-heading">
            <h2>
              <Activity size={17} /> Job activity
            </h2>
            <span className="subtle">AUTO-REFRESH</span>
          </div>
          {!jobs.data?.length ? (
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
                  {jobs.data.map((job) => (
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
                        <Status value={job.status} />
                      </td>
                      <td>
                        {job.status === "failed" && canWrite && (
                          <button
                            disabled={action.isPending}
                            onClick={() =>
                              action.mutate({ path: `/jobs/${job.id}/retry` })
                            }
                          >
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
        <footer>
          WATCHTOWER{" "}
          <span>
            Technical observations · assisted reports · human decisions
          </span>
        </footer>
      </main>
    </div>
  );
}
