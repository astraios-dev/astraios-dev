import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        await register(email, password, name);
      } else {
        await login(email, password);
      }
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const isRegister = mode === "register";

  return (
    <div className="login-page">
      <div className="login-card">
        <Link to="/" className="login-brand" aria-label="Back to home">
          <span
            className="logo-mark logo-mark--small"
            role="img"
            aria-label="Astraios A mark"
          />
        </Link>

        <div className="login-header">
          <h1>{isRegister ? "Create account" : "Sign in"}</h1>
          <p>
            {isRegister
              ? "Join the private beta and start paper trading."
              : "Access your trading dashboard and signals."}
          </p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {isRegister && (
            <div className="form-field">
              <label htmlFor="name">Name</label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
              />
            </div>
          )}

          <div className="form-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="trader@astraios.tech"
            />
          </div>

          <div className="form-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete={isRegister ? "new-password" : "current-password"}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isRegister ? "Choose a password" : "Enter password"}
            />
          </div>

          {error && (
            <p className="login-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="login-submit" disabled={loading}>
            {loading
              ? (isRegister ? "Creating account…" : "Signing in…")
              : (isRegister ? "Create account" : "Sign in")}
          </button>
        </form>

        <p className="login-toggle">
          {isRegister ? "Already have an account?" : "No account yet?"}{" "}
          <button
            type="button"
            className="login-toggle__btn"
            onClick={() => { setMode(isRegister ? "login" : "register"); setError(""); }}
          >
            {isRegister ? "Sign in" : "Create one"}
          </button>
        </p>
      </div>
    </div>
  );
}
