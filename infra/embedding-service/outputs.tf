output "qdrant_ip" {
  description = "External IP of Qdrant VM"
  value       = google_compute_instance.qdrant.network_interface[0].access_config[0].nat_ip
}

output "embedding_service_url" {
  description = "Cloud Run URL of embedding-service"
  value       = google_cloud_run_v2_service.embedding_service.uri
}
