output "api_url" {
  value       = google_cloud_run_v2_service.api.uri
  description = "The deployed API URL"
}

output "db_connection_name" {
  value       = google_sql_database_instance.main.connection_name
  description = "Cloud SQL connection name for the Cloud SQL Auth Proxy"
}

output "service_account_email" {
  value       = google_service_account.api.email
  description = "Service account email for the Cloud Run service"
}
