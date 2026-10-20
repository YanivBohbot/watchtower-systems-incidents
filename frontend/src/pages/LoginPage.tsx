import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Radar } from "lucide-react";
import { request } from "../api/client";

export default function LoginPage({
  onLogin,
}: {
  onLogin: (token: string) => void;
}) {
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
