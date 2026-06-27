terraform {
  required_version = ">= 1.0"
  backend "gcs" {}
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

# --- Compute Engine API ---

resource "google_project_service" "compute" {
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

# --- Qdrant VM ---

resource "google_compute_instance" "qdrant" {
  name         = "qdrant-vm"
  machine_type = "e2-standard-2"
  zone         = var.zone

  depends_on = [google_project_service.compute]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 50
      type  = "pd-standard"
    }
  }

  network_interface {
    network = "default"
    access_config {}
  }

  tags = ["qdrant"]

  service_account {
    scopes = ["cloud-platform"]
  }

  metadata = {
    startup-script = <<-STARTUP
      #!/bin/bash
      set -e

      # Docker
      apt-get update -y
      apt-get install -y ca-certificates curl gnupg
      install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null
      apt-get update -y
      apt-get install -y docker-ce docker-ce-cli containerd.io

      # Qdrant
      mkdir -p /opt/qdrant/storage
      docker run -d \
        --name qdrant \
        --restart always \
        -p 6333:6333 \
        -v /opt/qdrant/storage:/qdrant/storage \
        qdrant/qdrant:latest

      # Skrypt idle-shutdown (co 5 min sprawdza aktywnosc przez REST API Qdrant)
      cat > /usr/local/bin/idle-shutdown.sh <<'SCRIPT'
      #!/bin/bash
      PREV_VECTORS=0
      IDLE_MINUTES=0

      while true; do
          sleep 300

          CURR_VECTORS=$(curl -s http://localhost:6333/collections 2>/dev/null \
            | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    total = sum(c.get('vectors_count', 0) for c in data.get('result', {}).get('collections', []))
    print(total)
except:
    print(-1)
" 2>/dev/null || echo "-1")

          if [ "$CURR_VECTORS" = "-1" ]; then
              sleep 300
              continue
          fi

          if [ "$CURR_VECTORS" = "$PREV_VECTORS" ]; then
              IDLE_MINUTES=$((IDLE_MINUTES + 5))
          else
              IDLE_MINUTES=0
              PREV_VECTORS=$CURR_VECTORS
          fi

          if [ "$IDLE_MINUTES" -ge 30 ]; then
              ZONE=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/zone" \
                -H "Metadata-Flavor: Google" | cut -d/ -f4)
              NAME=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/name" \
                -H "Metadata-Flavor: Google")
              gcloud compute instances stop "$NAME" --zone="$ZONE" --quiet
          fi
      done
      SCRIPT

      chmod +x /usr/local/bin/idle-shutdown.sh
      nohup /usr/local/bin/idle-shutdown.sh >> /var/log/idle-shutdown.log 2>&1 &
    STARTUP
  }
}

# Firewall — port 6333 (Qdrant REST API)
resource "google_compute_firewall" "qdrant" {
  name    = "allow-qdrant"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["6333"]
  }

  target_tags   = ["qdrant"]
  source_ranges = ["0.0.0.0/0"]

  depends_on = [google_project_service.compute]
}

# --- Service Account dla Cloud Run (auto-start VM) ---

resource "google_service_account" "embedding_sa" {
  account_id   = "embedding-service"
  display_name = "Embedding Service"
}

resource "google_project_iam_member" "embedding_compute_admin" {
  project = var.project
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.embedding_sa.email}"
}

# --- Cloud Run: embedding-service ---

resource "google_cloud_run_v2_service" "embedding_service" {
  name     = var.service_name
  location = var.region

  template {
    service_account = google_service_account.embedding_sa.email

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "QDRANT_URL"
        value = "http://${google_compute_instance.qdrant.network_interface[0].access_config[0].nat_ip}:6333"
      }

      env {
        name  = "GCP_PROJECT"
        value = var.project
      }

      env {
        name  = "QDRANT_VM_NAME"
        value = google_compute_instance.qdrant.name
      }

      env {
        name  = "QDRANT_VM_ZONE"
        value = var.zone
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.embedding_service.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
