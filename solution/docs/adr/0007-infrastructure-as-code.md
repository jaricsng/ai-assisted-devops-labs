# ADR 0007 — Infrastructure as Code: Terraform for GCP Cloud Run

**Date:** 2026-06-16
**Status:** Accepted
**Authors:** Lab Student
**Context module:** Module 17 — Infrastructure as Code

---

## Context

After completing Module 13, the GCP Cloud Run deployment was managed by `infra/gcp/deploy.sh` — a shell script that runs `gcloud` commands in sequence. This approach has three problems:

1. **Not reproducible** — running the script twice may produce different results if manual changes were made in the GCP Console
2. **Not reviewable** — infrastructure changes happen outside of PRs; there is no diff to review
3. **No drift detection** — if someone changes a Cloud Run CPU limit in the console, the script has no awareness of the discrepancy

Module 17 requires adopting an IaC tool that solves these problems.

## Options Considered

| Tool | Language | State management | GCP support |
|------|----------|-----------------|-------------|
| **Terraform** | HCL | GCS bucket (native) | Official `hashicorp/google` provider |
| Pulumi | TypeScript / Python | Pulumi Cloud or self-hosted | Community-maintained provider |
| Google Cloud Deployment Manager | YAML | GCP-native | GCP-native only |
| CDK for Terraform (CDKTF) | TypeScript | Same as Terraform | Same as Terraform |

## Decision

**Terraform** with the official `hashicorp/google` provider and remote state in a GCS bucket.

### What is managed

The `infra/terraform/modules/cloud-run/` module provisions:
- **Cloud SQL** (PostgreSQL 16) with automated backups and PITR enabled in production
- **Secret Manager** secrets for `DATABASE_URL` and `SECRET_KEY`
- **Service account** with `roles/secretmanager.secretAccessor` for only those two secrets
- **Cloud Run v2** service with startup probe (`/health`), liveness probe (`/ready`), and Cloud SQL socket volume

### Environment structure

```
infra/terraform/
  modules/
    cloud-run/          # reusable module (variables, main, outputs)
  environments/
    staging/            # GCS state: task-manager/staging
    production/         # GCS state: task-manager/production
```

Staging and production have separate state files so a failed `plan` in production cannot affect staging resources.

### Secret handling

Secret values are never in `.tf` files or `terraform.tfvars`. They are passed at apply time via `-var="secret_key=..."` sourced from CI environment secrets. `secret_key` is declared `sensitive = true` in the module — Terraform redacts it from plan output.

## Why Terraform over the alternatives?

### Over Pulumi

Pulumi's TypeScript support would align with the frontend language. However:
- The Terraform GCP provider has more mature documentation and more community examples
- Students hitting errors in a Terraform plan can find solutions on StackOverflow easily; Pulumi GCP resources have less coverage
- HCL is simpler to read for infrastructure review — reviewers do not need TypeScript knowledge to understand a Terraform diff

### Over Deployment Manager

Deployment Manager is GCP-only. The skills learned with Terraform (state management, modules, workspace separation) transfer to AWS (`hashicorp/aws`) and Azure (`hashicorp/azurerm`) directly. Deployment Manager skills do not.

### Over CDKTF

CDKTF generates Terraform JSON from TypeScript code. It adds TypeScript compilation as a step before `terraform plan`, making the local workflow more complex without adding expressive power over plain HCL for a 4-resource module.

## Consequences

**Positive:**
- Infrastructure changes go through PRs (`terraform plan` output is included in the PR description)
- `terraform plan` shows the exact diff before any resource is touched
- `terraform destroy` tears down the full environment cleanly — useful for course cleanup and cost control
- Separate state per environment means a `destroy` in staging cannot affect production

**Negative:**
- The GCS state bucket must be created manually before the first `terraform init` — it cannot bootstrap itself
- `deletion_protection = true` on Cloud SQL in production prevents accidental deletion via Terraform; must be set to `false` before running `terraform destroy` in production
- Terraform provider updates (e.g., new major version of `hashicorp/google`) may require HCL changes — Dependabot does not currently cover Terraform provider locks

**Trade-off acknowledged:**
The `hashicorp/` provider is source-available but not open-source (BSL licence since Terraform 1.6). For enterprise use, **OpenTofu** is a fully open-source Terraform-compatible alternative that uses the same HCL syntax and providers. This lab uses Terraform for tooling familiarity; switching to OpenTofu requires no code changes, only the binary.
