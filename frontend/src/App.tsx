import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ChevronRight,
  FileText,
  Film,
  LogOut,
  MonitorPlay,
  Radar,
  ShieldCheck,
  X,
} from "lucide-react";
import { request } from "./api/client";
import { useList } from "./api/queries";
import type {
  Document,
  Incident,
  Investigation,
  Job,
  User,
  Video,
} from "./api/types";
import JobActivity from "./components/JobActivity";
import InvestigationsPage from "./pages/InvestigationsPage";
import type { ReviewDecision } from "./pages/InvestigationsPage";
import LiveCamerasPage from "./pages/LiveCamerasPage";
import LoginPage from "./pages/LoginPage";
import ProceduresPage from "./pages/ProceduresPage";
import VideoAnalysisPage, { useVideoDraft } from "./pages/VideoAnalysisPage";

type Tab = "live" | "workspace" | "knowledge" | "investigations";

/** Breadcrumb label, heading and introduction of each tab. */
const PAGES: Record<Tab, { label: string; title: string; intro: string }> = {
  live: {
    label: "Live cameras",
    title: "Every camera at a glance.",
    intro: "Alerts reach you within seconds. You decide what happens next.",
  },
  workspace: {
    label: "Video analysis",
    title: "A clear view of every event.",
    intro:
      "Upload a video, define a zone and find all the evidence in one place.",
  },
  knowledge: {
    label: "Procedures",
    title: "The context behind every decision.",
    intro:
      "Indexed procedures feed investigations with verifiable references.",
  },
  investigations: {
    label: "Investigations",
    title: "Conclusions you can verify.",
    intro:
      "Review the observations, sources and limitations before approving a report.",
  },
};

/** Sign-in gate, sidebar navigation, shared banners and statistics around the active tab. */
export default function App() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(
    () => sessionStorage.getItem("watchtower-token") || "",
  );
  const [tab, setTab] = useState<Tab>("live");
  const [notice, setNotice] = useState("");
  const draft = useVideoDraft();
  const user = useQuery({
    queryKey: ["me", token],
    queryFn: () => request<User>("/me", token),
    enabled: !!token,
    retry: false,
  });
  const signedIn = !!token && !!user.data;
  const videos = useList<Video>("videos", token, signedIn),
    jobs = useList<Job>("jobs", token, signedIn),
    documents = useList<Document>("documents", token, signedIn),
    incidents = useList<Incident>("incidents", token, signedIn),
    investigations = useList<Investigation>("investigations", token, signedIn);
  function refresh() {
    void queryClient.invalidateQueries();
  }
  const upload = useMutation({
    mutationFn: () => {
      if (!draft.file) throw new Error("Select a video");
      const body = new FormData();
      body.append("file", draft.file);
      body.append("zone", JSON.stringify(draft.zone));
      return request<Video>("/videos", token, { method: "POST", body });
    },
    onSuccess: (v) => {
      draft.setSelected(v.id);
      draft.setFile(null);
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
  // One mutation for every small POST (investigate, review, retry): its pending state disables all of their buttons.
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
  if (!token) return <LoginPage onLogin={connect} />;
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
  const page = PAGES[tab];
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
            Workspace <ChevronRight size={13} /> {page.label}
          </span>
          <span className="environment">
            <i /> LOCAL ENVIRONMENT
          </span>
        </header>
        <div className="page-heading">
          <div>
            <span className="eyebrow">FROM OBSERVATION TO ACTION</span>
            <h1>{page.title}</h1>
            <p>{page.intro}</p>
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
        {tab === "live" && <LiveCamerasPage token={token} />}
        {tab === "workspace" && (
          <VideoAnalysisPage
            token={token}
            canWrite={canWrite}
            videos={videos.data}
            incidents={incidents.data}
            draft={draft}
            uploading={upload.isPending}
            onStartAnalysis={() => upload.mutate()}
            busy={action.isPending}
            onInvestigate={(incidentId) => {
              action.mutate({ path: `/incidents/${incidentId}/investigate` });
              setTab("investigations");
            }}
          />
        )}
        {tab === "knowledge" && (
          <ProceduresPage
            documents={documents.data}
            canWrite={canWrite}
            uploading={docUpload.isPending}
            onUpload={(file) => docUpload.mutate(file)}
          />
        )}
        {tab === "investigations" && (
          <InvestigationsPage
            investigations={investigations.data}
            canWrite={canWrite}
            busy={action.isPending}
            onReview={(investigationId, decision: ReviewDecision) =>
              action.mutate({
                path: `/investigations/${investigationId}/review`,
                body: decision,
              })
            }
          />
        )}
        <JobActivity
          jobs={jobs.data}
          canWrite={canWrite}
          busy={action.isPending}
          onRetry={(jobId) => action.mutate({ path: `/jobs/${jobId}/retry` })}
        />
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
