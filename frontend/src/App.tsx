import { Routes, Route, Navigate } from "react-router-dom";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { LoginPage } from "./pages/LoginPage";

function isAuthenticated(): boolean {
  return !!localStorage.getItem("access_token");
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/projects"
        element={isAuthenticated() ? <ProjectsPage /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/projects/:id"
        element={isAuthenticated() ? <ProjectDetailPage /> : <Navigate to="/login" replace />}
      />
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}
