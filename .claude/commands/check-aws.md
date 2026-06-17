Review the AWS ECS Fargate deployment configuration (`aws/ecs/`, `aws/deploy.sh`, and the `deploy-aws` job in `.github/workflows/publish.yml`) against AWS best practices for security, reliability, and operational readiness. If `$ARGUMENTS` is provided, review that specific file.

---

## 1. ECS Task Definitions (`aws/ecs/api-task.json`, `aws/ecs/frontend-task.json`)

Read both files.

### 1a. IAM roles — least privilege
- `executionRoleArn` must reference an ECS execution role that has ONLY:
  - `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` (or `AmazonEC2ContainerRegistryReadOnly`)
  - `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
  - `secretsmanager:GetSecretValue` for the specific secret ARNs used in `secrets` — **not** `secretsmanager:*`
- `taskRoleArn` (the role the application itself uses at runtime) must be separate from the execution role, and should have no permissions unless the app calls AWS services. Flag if `taskRoleArn` is set to the same role as `executionRoleArn`.
- Flag any use of `*` in resource ARNs (e.g., `"Resource": "*"` for Secrets Manager — this grants access to every secret in the account).

### 1b. Secrets — Secrets Manager, not plaintext env vars
- Sensitive values (`DATABASE_URL`, `SECRET_KEY`) must appear in the `secrets` array (sourced from Secrets Manager), **not** in the `environment` array as plaintext.
- Run:

```bash
python3 -c "
import json
for f in ['aws/ecs/api-task.json', 'aws/ecs/frontend-task.json']:
    d = json.load(open(f))
    for c in d.get('containerDefinitions', []):
        for e in c.get('environment', []):
            if any(k in e['name'].upper() for k in ['KEY','SECRET','PASSWORD','TOKEN','URL']):
                print(f'POSSIBLE PLAINTEXT SECRET in {f}: {e[\"name\"]}')
"
```

### 1c. Health check
- Every container must define a `healthCheck` with:
  - `command`: `["CMD-SHELL", "curl -f http://localhost:PORT/health || exit 1"]`
  - `interval` ≤ 30s, `timeout` ≤ 10s, `retries` ≥ 3, `startPeriod` ≥ 15s (FastAPI needs time to start)
- Flag missing or overly strict health checks (low `startPeriod` causes containers to be killed before the app finishes starting).

### 1d. Log configuration
- `logConfiguration.logDriver` must be `awslogs` — no container should run without logging.
- `awslogs-region` must be a variable reference (`REGION`), not hardcoded — flag literal region strings.
- The `awslogs-group` name must match the group created in CloudWatch — a mismatch causes silent log loss.

### 1e. Networking mode
- `networkMode` must be `awsvpc` for Fargate — `bridge` and `host` modes are not supported on Fargate. Flag if wrong.
- `requiresCompatibilities` must include `"FARGATE"`.

### 1f. Resource sizing
- CPU and memory must be a valid Fargate combination. Common valid pairs: `(256, 512)`, `(512, 1024)`, `(1024, 2048)`. Invalid combinations fail at task registration.
- Flag `cpu: "256"` with `memory: "2048"` — Fargate does not allow this pairing.

---

## 2. Image Registry

**Check:**
- Images reference `ghcr.io/...` (GitHub Container Registry). For production AWS, consider whether **Amazon ECR** is more appropriate:
  - ECR images stay within the AWS network (no egress cost, faster pulls in the same region)
  - GHCR requires an ECR pull-through cache or external internet access from Fargate tasks
- Flag if the VPC has no NAT Gateway and tasks still reference `ghcr.io/` — pulls will fail (Fargate in a private subnet needs NAT or a VPC endpoint to reach external registries).

---

## 3. Deploy Script (`aws/deploy.sh`)

Read `aws/deploy.sh`.

**Check:**
- `set -euo pipefail` is present — flag if missing (errors silently ignored = partial deploys)
- All required environment variables (`REGION`, `ACCOUNT_ID`, `GITHUB_USERNAME`, `CLUSTER`) are validated with `:?` syntax or explicit checks — flag bare variable use
- The script waits for `aws ecs wait services-stable` after deployment — flag if this step is missing (CI would report success before the new tasks are actually running)
- Placeholder substitution (`ACCOUNT_ID`, `REGION`, `GITHUB_USERNAME`) in the task definition JSON must replace ALL occurrences — run:

```bash
grep -n "ACCOUNT_ID\|REGION\|GITHUB_USERNAME" aws/ecs/api-task.json aws/ecs/frontend-task.json
```

Flag any placeholders that are NOT substituted by the `substitute()` function in the script.

- The deploy script does NOT perform `aws ecs register-task-definition` with `--query "taskDefinition.taskDefinitionArn"` and then immediately deploy — verify it captures the ARN of the newly registered revision, not an old one.

---

## 4. CI/CD Pipeline (`publish.yml` — `deploy-aws` job)

Read `.github/workflows/publish.yml`, focus on the `deploy-aws` job.

**Check:**
- The job uses `aws-actions/configure-aws-credentials@v4` with `role-to-assume` (OIDC / AssumeRoleWithWebIdentity) — **not** `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` static credentials. Static keys have no automatic rotation and are the most common cause of AWS credential leaks.
- If static keys are used, flag as ❌ critical. The fix: create an IAM OIDC provider for GitHub Actions and use a role assumption.
- The deploy job is gated by the `production-aws` GitHub Environment — flag if the environment name is missing.
- `IMAGE_TAG: sha-${{ github.sha }}` is passed to the deploy script — ensures the newly built image is deployed, not the stale `latest` tag.

---

## 5. Networking & Security Groups (advisory)

**Check what should exist (cannot verify from files alone — flag as advisory):**
- ECS tasks should run in **private subnets** — no public IP on tasks.
- An **Application Load Balancer (ALB)** in public subnets routes traffic to the ECS tasks.
- Security groups: ALB SG allows 80/443 from internet; task SG allows port 8000 only from ALB SG.
- PostgreSQL (RDS): should be in a private subnet, accessible only from the task security group on port 5432.
- Flag if task definitions contain `"assignPublicIp": "ENABLED"` — tasks should be in private subnets behind an ALB.

---

## 6. Database: RDS vs Container

**Check:**
- The `DATABASE_URL` secret in Secrets Manager should point to **Amazon RDS for PostgreSQL** (managed), not a PostgreSQL container running in ECS. A DB container in ECS loses data if its task is replaced.
- Run:

```bash
aws secretsmanager get-secret-value \
  --secret-id task-manager/database-url \
  --query SecretString --output text 2>/dev/null || echo "Secret not yet created"
```

If the secret exists and contains `@db:5432` or a container hostname, flag it — the host should be an RDS endpoint (e.g., `task-manager-db.xxxx.ap-southeast-1.rds.amazonaws.com`).

---

## 7. Observability

**Check:**
- CloudWatch log groups referenced in `awslogs-group` (`/ecs/task-manager-api`, `/ecs/task-manager-frontend`) must exist — they should be created via IaC before first deploy, not left to auto-create (auto-create gives them no retention policy, defaulting to "never expire" which accumulates cost).
- Recommended: set `--log-group-arn` retention to 30 days.
- For distributed tracing: if `OTEL_ENABLED=true`, `OTLP_ENDPOINT` should point to **AWS X-Ray OTLP endpoint** or an OpenTelemetry Collector sidecar — not to `jaeger:4317` (the local dev endpoint).

---

## Output Format

```
── aws/ecs/api-task.json ────────────────────────────
✅ networkMode: awsvpc
✅ requiresCompatibilities: FARGATE
✅ healthCheck defined (startPeriod: 15s)
❌ DATABASE_URL in environment[] as plaintext — move to secrets[] referencing Secrets Manager
⚠️  taskRoleArn same as executionRoleArn — separate these roles for least privilege

── aws/deploy.sh ────────────────────────────────────
✅ set -euo pipefail present
✅ aws ecs wait services-stable used
⚠️  CLUSTER not validated with :? syntax — will fail silently if unset

── CI/CD (deploy-aws) ───────────────────────────────
❌ Uses AWS_ACCESS_KEY_ID static credentials — migrate to OIDC role assumption
✅ Gated by production-aws GitHub Environment
```

Final summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  AWS Deployment Review — Task Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IAM roles (least privilege)  ✅ / ⚠️ / ❌
  Secrets (Secrets Manager)    ✅ / ⚠️ / ❌
  Health checks                ✅ / ⚠️ / ❌
  Log configuration            ✅ / ⚠️ / ❌
  Fargate compatibility        ✅ / ⚠️ / ❌
  Image registry               ✅ / ⚠️ / ❌
  Deploy script                ✅ / ⚠️ / ❌
  CI/CD (OIDC vs static keys)  ✅ / ⚠️ / ❌
  Networking (advisory)        ✅ / ⚠️ / ❌
  Database (RDS vs container)  ✅ / ⚠️ / ❌
  Observability                ✅ / ⚠️ / ❌

  ❌ Must fix before production:  N
  ⚠️  Should fix:                N
  ✅ Passed:                     N
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For every ❌: quote the problematic config, explain the specific risk (data loss, credential leak, deployment failure), and provide the corrected version.
