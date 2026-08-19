import { useState } from "react";
import { Eye, EyeOff, Lock, Mail, ShieldAlert } from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Login() {
  const { login, isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!loading && isAuthenticated) {
    return <Navigate to="/chat" replace />;
  }

  async function onSubmit(ev) {
    ev.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate("/chat", { replace: true });
    } catch (err) {
      setError(err.message || "Sign in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <svg width="0" height="0" className="login-clip-defs" aria-hidden="true">
        <defs>
          <clipPath id="left-panel-clip" clipPathUnits="objectBoundingBox">
            <path d="M 0,0 L 0.85,0 Q 1.05,0.45 0.65,1.0 L 0,1.0 Z" />
          </clipPath>
        </defs>
      </svg>

      <div className="login-card">
        <section className="login-left-panel">
          <div className="login-brand">
            <h1>
              <span>Alder AI</span>
            </h1>
            <p>On-premise AI chatbot for documents and images</p>
            <div className="login-brand-rule" />
          </div>
        </section>

        <section className="login-panel">
          <h2>Sign In</h2>
          <form onSubmit={onSubmit}>
            {error ? (
              <div className="login-error" role="alert">
                <ShieldAlert size={15} />
                <span>{error}</span>
              </div>
            ) : null}

            <label>
              Email Address
              <div className="field">
                <Mail className={`field-icon${emailFocused ? " on" : ""}`} size={14} />
                <input
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="Enter your email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onFocus={() => setEmailFocused(true)}
                  onBlur={() => setEmailFocused(false)}
                />
              </div>
            </label>

            <label>
              Password
              <div className="field">
                <Lock className={`field-icon${passwordFocused ? " on" : ""}`} size={14} />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => setPasswordFocused(true)}
                  onBlur={() => setPasswordFocused(false)}
                />
                <button
                  type="button"
                  className="field-toggle"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((v) => !v)}
                >
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </label>

            <button type="submit" className="btn-signin" disabled={submitting}>
              {submitting ? <span className="btn-spinner" /> : "SIGN IN"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
