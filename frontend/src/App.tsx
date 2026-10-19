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
  Radar,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import { mediaUrl, request } from "./api";
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
  queued: "En attente",
  running: "En cours",
  completed: "Terminé",
  failed: "Échec",
  indexed: "Indexé",
  indexing: "Indexation",
  awaiting_review: "À valider",
  approved: "Approuvé",
  rejected: "Rejeté",
  review_queued: "Validation en cours",
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
          alt={`Capture à ${incident.seconds.toFixed(1)} secondes`}
        />
      ) : (
        <span>{error || "Chargement de la preuve…"}</span>
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
          Des observations.
          <br />
          Des preuves.
          <br />
          <em>Des décisions éclairées.</em>
        </h1>
        <p>
          Analyse vidéo, procédures documentées et investigation assistée, dans
          un espace de travail unique.
        </p>
      </div>
      <form
        className="login-card"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <span className="eyebrow">ESPACE OPÉRATEUR</span>
        <h2>Bienvenue.</h2>
        <p>Connecte-toi avec le compte créé à l’installation.</p>
        <label>
          Adresse e-mail
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Mot de passe
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
          Se connecter <ArrowRight size={16} />
        </button>
        <small>Les rapports restent soumis à une validation humaine.</small>
      </form>
    </div>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(
    () => sessionStorage.getItem("watchtower-token") || "",
  );
  const [tab, setTab] = useState<"workspace" | "knowledge" | "investigations">(
    "workspace",
  );
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
      if (!file) throw new Error("Sélectionne une vidéo");
      const body = new FormData();
      body.append("file", file);
      body.append("zone", JSON.stringify(zone));
      return request<Video>("/videos", token, { method: "POST", body });
    },
    onSuccess: (v) => {
      setSelected(v.id);
      setFile(null);
      setNotice("Vidéo enregistrée. Le traitement est lancé en arrière-plan.");
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
      setNotice("Document enregistré. Consulte son état d’indexation.");
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
      setNotice("Demande enregistrée.");
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
        <h2>Connexion expirée ou serveur indisponible</h2>
        <p>{user.error.message}</p>
        <button onClick={logout}>Retour à la connexion</button>
      </div>
    );
  if (!user.data) return <div className="center">Connexion à WatchTower…</div>;
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
        <div className="nav-label">VOTRE ESPACE</div>
        <nav>
          <button
            className={tab === "workspace" ? "active" : ""}
            onClick={() => setTab("workspace")}
          >
            <Film size={18} /> Analyse vidéo <ChevronRight size={14} />
          </button>
          <button
            className={tab === "knowledge" ? "active" : ""}
            onClick={() => setTab("knowledge")}
          >
            <FileText size={18} /> Procédures
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
          <strong>Vous gardez la décision.</strong>
          <p>
            L’agent rassemble les éléments. Vous validez les conclusions et les
            actions.
          </p>
        </div>
        <div className="account">
          <div className="avatar">{user.data.email[0].toUpperCase()}</div>
          <div>
            <strong>{user.data.email.split("@")[0]}</strong>
            <small>{user.data.role}</small>
          </div>
          <button aria-label="Déconnexion" onClick={logout}>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <main>
        <header>
          <span>
            Workspace <ChevronRight size={13} />{" "}
            {tab === "workspace"
              ? "Analyse vidéo"
              : tab === "knowledge"
                ? "Procédures"
                : "Investigations"}
          </span>
          <span className="environment">
            <i /> ENVIRONNEMENT LOCAL
          </span>
        </header>
        <div className="page-heading">
          <div>
            <span className="eyebrow">DE L’OBSERVATION À L’ACTION</span>
            <h1>
              {tab === "workspace"
                ? "Une vue claire sur chaque événement."
                : tab === "knowledge"
                  ? "Le contexte derrière chaque décision."
                  : "Des conclusions que vous pouvez vérifier."}
            </h1>
            <p>
              {tab === "workspace"
                ? "Importez une vidéo, définissez une zone et retrouvez les preuves au même endroit."
                : tab === "knowledge"
                  ? "Les procédures indexées alimentent les investigations avec des références vérifiables."
                  : "Examinez les observations, les sources et les limites avant de valider un rapport."}
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
            <button aria-label="Fermer" onClick={() => setNotice("")}>
              <X size={15} />
            </button>
          </div>
        )}
        <section className="stats">
          <div>
            <Film />
            <span>Vidéos importées</span>
            <strong>{videos.data?.length || 0}</strong>
          </div>
          <div>
            <Activity />
            <span>Événements détectés</span>
            <strong>{incidents.data?.length || 0}</strong>
          </div>
          <div>
            <ShieldCheck />
            <span>Rapports à valider</span>
            <strong>{reviews}</strong>
          </div>
          <div>
            <span className="live-dot" />
            <span>Traitements actifs</span>
            <strong>{pending}</strong>
          </div>
        </section>
        {tab === "workspace" && (
          <div className="workspace-grid">
            <section className="panel video-panel">
              <div className="panel-heading">
                <h2>
                  <Film size={17} /> Analyse vidéo
                </h2>
                <span className="subtle">FICHIERS IMPORTÉS</span>
              </div>
              <div className="video-controls">
                <select
                  aria-label="Vidéo"
                  value={activeVideo?.id || ""}
                  onChange={(e) => {
                    setSelected(e.target.value);
                    setFile(null);
                  }}
                >
                  <option value="" disabled>
                    Choisir une vidéo
                  </option>
                  {videos.data?.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </select>
                {canWrite && (
                  <label className="button secondary">
                    <Upload size={15} /> Importer
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
                  <h3>Votre première analyse commence ici.</h3>
                  <p>
                    {serverMedia.error ||
                      "Une vidéo de 30 à 60 secondes, caméra fixe, suffit pour démarrer."}
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
                      Zone rectangulaire · point suivi : bas du cadre de
                      détection
                    </span>
                  </div>
                  <label>
                    Présence minimale (s)
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
                    Lancer l’analyse <ArrowRight size={15} />
                  </button>
                </form>
              )}
              {!file && activeVideo && (
                <div className="video-info">
                  <span>Zone A · seuil {activeVideo.zone.dwell_seconds} s</span>
                  <span>{activeVideo.name}</span>
                </div>
              )}
            </section>
            <section className="panel events-panel">
              <div className="panel-heading">
                <h2>Événements</h2>
                <span className="count">{visibleIncidents.length}</span>
              </div>
              {visibleIncidents.length === 0 ? (
                <div className="empty">
                  <Activity size={28} />
                  <h3>Aucun événement pour cette vidéo</h3>
                  <p>
                    Les événements apparaîtront ici lorsque la règle de présence
                    sera satisfaite.
                  </p>
                </div>
              ) : (
                visibleIncidents.map((incident) => (
                  <article className="incident" key={incident.id}>
                    <Evidence incident={incident} token={token} />
                    <div>
                      <span className="eyebrow">PRÉSENCE EN ZONE A</span>
                      <h3>Seuil de présence dépassé</h3>
                      <p>
                        Trajectoire #{incident.track_id} · score du détecteur{" "}
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
                          Ouvrir une investigation <ArrowRight size={15} />
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
              <h2>Bibliothèque de procédures</h2>
              {canWrite && (
                <label className="button primary">
                  <Upload size={15} /> Ajouter un document
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
              PDF avec texte ou TXT UTF-8. Chaque passage conserve le nom du
              document et son numéro de page. Les PDF scannés nécessitent un
              OCR, non inclus dans cette version.
            </p>
            {!documents.data?.length ? (
              <div className="empty">
                <FileText />
                <h3>Ajoutez votre première procédure</h3>
                <p>
                  Un exemple de procédure de démonstration est fourni dans le
                  dossier examples.
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
                <h3>Aucune investigation pour le moment</h3>
                <p>Lancez une investigation depuis un événement détecté.</p>
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
                        <span className="eyebrow">RECOMMANDATION</span>
                        <p>{inv.report.recommendation}</p>
                      </div>
                      {inv.report.sources.map((source) => (
                        <details key={source.id}>
                          <summary>
                            <FileText size={14} /> {source.document} · page{" "}
                            {source.page}
                          </summary>
                          <blockquote>{source.text}</blockquote>
                          <small>Référence : {source.id}</small>
                        </details>
                      ))}
                      {inv.report.limitations.length > 0 && (
                        <div className="limitations">
                          <strong>Limites à considérer</strong>
                          <ul>
                            {inv.report.limitations.map((v, i) => (
                              <li key={i}>{v}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <small className="hint">
                        Outils locaux utilisés :{" "}
                        {inv.report.tool_trace.join(" → ") || "aucun"}
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
                            <Check size={16} /> Approuver et créer un ticket
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
                            Approuver sans ticket
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
                            Rejeter
                          </button>
                        </div>
                      )}
                      {inv.ticket && (
                        <div className="ticket">
                          <Check size={17} /> Ticket créé via MCP ·{" "}
                          {inv.ticket.id}
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="section-description">
                      Le traitement est en attente ou en cours. Consultez les
                      tâches ci-dessous pour connaître les éventuelles erreurs.
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
              <Activity size={17} /> Activité des traitements
            </h2>
            <span className="subtle">ACTUALISATION AUTOMATIQUE</span>
          </div>
          {!jobs.data?.length ? (
            <p className="section-description">
              Les analyses, indexations et investigations apparaîtront ici.
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Traitement</th>
                    <th>Identifiant</th>
                    <th>Progression</th>
                    <th>État</th>
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
                            Réessayer
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
            Observations techniques · rapports assistés · décisions humaines
          </span>
        </footer>
      </main>
    </div>
  );
}
