// TaskManager Aspire AppHost
//
// Local dev:   dotnet run --project aspire/TaskManager.AppHost
// Cloud manifest (for CI reference or custom publishers):
//   dotnet run --project aspire/TaskManager.AppHost -- --publisher manifest --output-path aspire-manifest.json
//
// Cloud deployment paths:
//   Azure Container Apps — azd up  (reads azure.yaml, uses this AppHost as the Aspire entry point)
//   AWS ECS Fargate      — aws/deploy.sh  (manifest used as reference; ECS task defs are the deploy target)
//   GCP Cloud Run        — infra/gcp/deploy.sh  (same pattern as AWS)
//   Fly.io               — flyctl deploy  (fly.toml + publish.yml deploy jobs)

var builder = DistributedApplication.CreateBuilder(args);

// ── Parameters ────────────────────────────────────────────────────────────────
// Defaults live in appsettings.Development.json (safe for dev).
// In production, override via:
//   Azure:  azd env set <key> <value>  (stored in .azure/<env>/.env)
//   Local:  dotnet user-secrets set "Parameters:db-password" "..."
//   CI:     Parameters__db-password env var
var dbPassword  = builder.AddParameter("db-password",  secret: true);
var secretKey   = builder.AddParameter("secret-key",   secret: true);
var corsOrigins = builder.AddParameter("cors-origins");

// ── PostgreSQL ────────────────────────────────────────────────────────────────
var postgres = builder.AddPostgres("db", password: dbPassword)
    .WithDataVolume("taskmanager-data")
    .WithPgAdmin();   // pgAdmin UI at a random host port

// ── API: Python / FastAPI ─────────────────────────────────────────────────────
// asyncpg requires "postgresql+asyncpg://" prefix; Aspire's Npgsql connection
// string uses a different key=value format, so we build the URL explicitly.
var pgEndpoint = postgres.GetEndpoint("tcp");
var api = builder.AddDockerfile("api", "../../backend")
    .WithHttpEndpoint(port: 8000, name: "http")
    .WaitFor(postgres)
    .WithEnvironment("DATABASE_URL",
        ReferenceExpression.Create(
            $"postgresql+asyncpg://postgres:{dbPassword}@{pgEndpoint.Host}:{pgEndpoint.Port}/taskmanager"))
    .WithEnvironment("SECRET_KEY",   secretKey)
    .WithEnvironment("CORS_ORIGINS", corsOrigins)
    .WithEnvironment("OTEL_ENABLED", "true")
    .WithEnvironment("ENVIRONMENT",  "development");

// ── Frontend: React / Vite dev server ────────────────────────────────────────
// VITE_API_URL is read by Vite at startup (not compile-time in dev mode).
builder.AddDockerfile("frontend", "../../frontend")
    .WithHttpEndpoint(port: 5173, name: "http")
    .WaitFor(api)
    .WithEnvironment("VITE_API_URL", api.GetEndpoint("http"));

builder.Build().Run();
