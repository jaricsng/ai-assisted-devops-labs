import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { projectsApi } from "../api/projects";

export function ProjectsPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const { data: projects, isLoading } = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });

  const createProject = useMutation({
    mutationFn: (n: string) => projectsApi.create({ name: n }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      setName("");
    },
  });

  if (isLoading) return <p>Loading…</p>;

  return (
    <div style={{ maxWidth: 700, margin: "40px auto", padding: 24 }}>
      <h1>Projects</h1>
      <form
        onSubmit={(e) => { e.preventDefault(); if (name.trim()) createProject.mutate(name.trim()); }}
        style={{ display: "flex", gap: 8, marginBottom: 24 }}
      >
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New project name" style={{ flex: 1 }} />
        <button type="submit">Create</button>
      </form>
      {projects?.length === 0 && <p>No projects yet. Create one above.</p>}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {projects?.map((p) => (
          <li key={p.id} style={{ padding: "12px 0", borderBottom: "1px solid #e5e7eb" }}>
            <Link to={`/projects/${p.id}`} style={{ fontWeight: 600 }}>{p.name}</Link>
            {p.description && <p style={{ color: "#6b7280", margin: "4px 0 0" }}>{p.description}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
