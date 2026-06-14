import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import type { Token } from "../api/types";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { data } = await apiClient.post<Token>("/auth/login", { email, password });
      localStorage.setItem("access_token", data.access_token);
      navigate("/projects");
    } catch {
      setError("Invalid email or password.");
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: "80px auto", padding: 24 }}>
      <h1>Task Manager</h1>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 12 }}>
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={{ display: "block", width: "100%", marginTop: 4 }} />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ display: "block", width: "100%", marginTop: 4 }} />
        </div>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit">Log in</button>
      </form>
    </div>
  );
}
