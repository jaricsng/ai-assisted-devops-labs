import { useState, useCallback } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { LoginPage } from "./pages/LoginPage";

export function App() {
  const [isAuthed, setIsAuthed] = useState(() => !!localStorage.getItem("access_token"));
  const handleLogin = useCallback(() => setIsAuthed(true), []);
  const handleLogout = useCallback(() => setIsAuthed(false), []);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage onLogin={handleLogin} />} />
      <Route
        path="/projects"
        element={isAuthed ? <ProjectsPage onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/projects/:id"
        element={isAuthed ? <ProjectDetailPage /> : <Navigate to="/login" replace />}
      />
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}
