# Mini Allegro — Platforma e-commerce (Projekt laboratoryjny PAW 2026)

> Projekt akademicki realizowany na Uniwersytecie Mikołaja Kopernika w Toruniu w ramach kursu **Aplikacje Wielkoskalowe (PAW)**, rok akademicki 2025/2026.

Projekt symuluje platformę e-commerce w stylu Allegro, zbudowaną jako **zestaw niezależnych mikroserwisów** wdrożonych na **Google Cloud Platform**. Każdy mikroserwis jest napisany w innej technologii, ma własny Dockerfile, własną infrastrukturę Terraform i niezależny pipeline CI/CD.

---

## Spis treści

- [Architektura systemu](#architektura-systemu)
- [Mikroserwisy](#mikroserwisy)
  - [symphony-monolith (PHP / Symfony)](#symphony-monolith--php--symfony)
  - [products-service (Scala)](#products-service--scala)
  - [purchase-service (Python / Flask)](#purchase-service--python--flask)
  - [product-review-service (Java / Spring Boot)](#product-review-service--java--spring-boot)
  - [offers-service (Go)](#offers-service--go)
  - [embedding-service (Python)](#embedding-service--python)
  - [twitch-agent (Python / AI Agent)](#twitch-agent--python--ai-agent)
- [Infrastruktura (GCP + Terraform)](#infrastruktura-gcp--terraform)
- [Audit Log — centralny system logowania](#audit-log--centralny-system-logowania)
- [Pub/Sub — komunikacja między serwisami](#pubsub--komunikacja-między-serwisami)
- [CI/CD (GitHub Actions)](#cicd-github-actions)
- [Testy integracyjne](#testy-integracyjne)
- [Uruchomienie lokalne](#uruchomienie-lokalne)
- [Zespół i podział prac](#zespół-i-podział-prac)

---

## Architektura systemu

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Google Cloud Platform                        │
│                                                                     │
│  ┌──────────────────┐    ┌──────────────────┐                       │
│  │ symphony-monolith│    │  offers-service  │                       │
│  │   PHP / Symfony  │    │       Go         │                       │
│  │   Cloud Run      │    │   Cloud Run      │──► Pub/Sub topic      │
│  └──────────┬───────┘    └──────────────────┘                       │
│             │                                                        │
│      ┌──────┴──────┐   ┌──────────────────┐                        │
│      │  delegates  │   │ purchase-service  │                        │
│      │  HTTP calls │   │  Python / Flask  │                        │
│      └──────┬──────┘   │   Cloud Run      │                        │
│             │           └──────────────────┘                        │
│  ┌──────────▼───────┐   ┌──────────────────┐                       │
│  │product-review-svc│   │ products-service  │                       │
│  │ Java/Spring Boot │   │      Scala        │                       │
│  │   Cloud Run      │   │   Cloud Run       │                       │
│  │   Firestore DB   │   └──────────────────┘                        │
│  └──────────────────┘                                               │
│                                                                     │
│  ┌──────────────────────────────────────────┐                       │
│  │           embedding-service              │                       │
│  │  Python + Qdrant (vector DB)             │                       │
│  │  Modele: nomic-embed-text, gemini-emb-2  │                       │
│  └──────────────────────────────────────────┘                       │
│                                                                     │
│  ┌──────────────────────────────────────────┐                       │
│  │           Cloud SQL (PostgreSQL)         │                       │
│  │  Dane główne + Audit Log (partycjonowany)│                       │
│  └──────────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Projekt GCP:** `paw-2026-496213`
**Region:** `europe-central2` (Warszawa)

---

## Mikroserwisy

### symphony-monolith — PHP / Symfony

**Lokalizacja:** `services/symphony-monolith/`

Główna aplikacja projektu. Monolith w PHP 8.3 oparty o framework **Symfony 7**, wystawiający REST API dla frontendowych klientów. Zarządza encjami: `users`, `offers`, `products`, `purchases`, `product-reviews`.

**Technologie:**
- PHP 8.3 + Symfony 7
- Doctrine ORM + migracje bazodanowe
- Symfony HTTP Client (delegowanie requestów do mikroserwisów)
- Monolog (logowanie)
- Symfony Serializer + Validator

**Kluczowe endpointy:**

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/offers` | Lista ofert |
| `GET` | `/users` | Lista użytkowników |
| `GET` | `/products` | Lista produktów |
| `GET` | `/purchases` | Lista zakupów |
| `GET` | `/purchases/offer/{id}` | Zakupy dla oferty |
| `GET` | `/product-reviews` | Delegowane do product-review-service |
| `POST` | `/product-reviews` | Delegowane do product-review-service |
| `GET` | `/health` | Health check |
| `GET` | `/health/error` | Endpoint testowy — generuje błąd (testy alertów) |

**Infrastruktura:**
- Cloud Run (serverless kontenery)
- Cloud SQL PostgreSQL
- Artifact Registry (obrazy Docker)
- Cloud Build (budowanie obrazów po stronie GCP)

---

### products-service — Scala

**Lokalizacja:** `services/products-service/`

Mikroserwis zarządzający katalogiem produktów. Napisany w **Scala** z użyciem systemu budowania `sbt`.

**Technologie:**
- Scala
- sbt (build tool)
- Docker
- Cloud Run

---

### purchase-service — Python / Flask

**Lokalizacja:** `services/purchase-service/`

Mikroserwis obsługujący zakupy. Napisany w **Python/Flask**, z własnym Dockerfile i skryptami uruchamiającymi.

**Technologie:**
- Python 3 + Flask
- PostgreSQL (Cloud SQL)
- Docker
- Cloud Run

---

### product-review-service — Java / Spring Boot

**Lokalizacja:** `services/product-review-service/`

Mikroserwis obsługujący recenzje produktów i ofert. Zbudowany jako osobny serwis w **Java/Spring Boot**, baza danych przeniesiona z PostgreSQL na **Google Cloud Firestore**.

**Technologie:**
- Java + Spring Boot
- Maven (`pom.xml`)
- Google Cloud Firestore (NoSQL — baza dokumentowa)
- Docker
- Cloud Run

**Kluczowe endpointy:**

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/product-reviews` | Pobierz recenzje |
| `POST` | `/product-reviews` | Dodaj recenzję |
| `GET` | `/reviews-super` | Rozszerzony widok recenzji z offer_id |

Monolith Symfony deleguje requesty `/product-reviews` bezpośrednio do tego serwisu przez HTTP Client.

---

### offers-service — Go

**Lokalizacja:** `services/offers-service/`

Mikroserwis zarządzający ofertami. Napisany w **Go**, z migracjami bazodanowymi i integracją z **Google Cloud Pub/Sub** (logowanie zdarzeń).

**Technologie:**
- Go (Golang)
- PostgreSQL
- Google Cloud Pub/Sub (`cloud.google.com/go/pubsub/v2`)
- Docker
- Cloud Run

**Architektura Pub/Sub w tym serwisie:**
- Po każdym `CreateOffer` i `AssignSuperSeller` wysyłany jest log do tematu Pub/Sub `mini-allegro-service-logs`
- Fallback `NoopPublisher` gdy `PUBSUB_TOPIC` nie jest ustawiony (bezpieczne lokalne uruchomienie)

---

### embedding-service — Python

**Lokalizacja:** `services/embedding-service/`

Serwis do **semantycznego wyszukiwania dokumentów** z bazy wiedzy na podstawie wpisanej przez użytkownika frazy. Generuje i przechowuje wektorowe reprezentacje (embeddingi) artykułów naukowych z datasetu **AI arXiv** (41 584 chunków tekstowych).

**Technologie:**
- Python 3
- **Qdrant** — vector database (wyszukiwanie ANN algorytmem HNSW)
- **Ollama** — lokalne embeddingi przez model `nomic-embed-text` (768 dims)
- **Google Gemini API** — embeddingi przez model `gemini-embedding-2` (3072 dims)
- `qdrant-client`, `google-genai`, `datasets`, `tqdm`
- Docker Compose (lokalne uruchomienie Qdrant)

**Dataset:**
- Źródło: `ai-arxiv-chunked` (artykuły z arXiv dotyczące AI)
- 41 584 chunków tekstowych załadowanych z dysku (`data/ai-arxiv-chunked/`)

**Schemat kolekcji Qdrant (`ai-arxiv`):**

```json
{
  "id": 1,
  "vector": {
    "nomic-embed-text": [... 768 floatów ...],
    "gemini-embedding-2": [... 3072 floatów ...]
  },
  "payload": {
    "raw": "oryginalny tekst chunka"
  }
}
```

Kolekcja używa **named vectors** — jeden punkt przechowuje embeddingi z wielu modeli w osobnych przestrzeniach wektorowych.

**Flow wyszukiwania semantycznego:**

```
1. Użytkownik wpisuje frazę + wybiera model (nomic lub gemini)
2. System generuje embedding frazy TYM SAMYM modelem
3. Qdrant: filter { named_vector = "<wybrany model>" } + ANN search (HNSW)
4. Zwracane top-K najbardziej podobnych dokumentów (cosine similarity)
```

**Wyszukiwanie HNSW (Hierarchical Navigable Small World):**
- Zamiast porównywać z każdym wektorem (O(n)), Qdrant buduje wielowarstwowy graf połączeń
- Wyszukiwanie sprawdza ~200–500 wektorów zamiast milionów — accuracy 95–99%
- Miara podobieństwa: **cosine similarity** (od -1 do 1)

**Skrypty:**
- `embed_and_store.py` — główny skrypt embedowania i zapisu do Qdrant. Obsługuje `--limit N` do testowego uruchomienia na podzbiorze
- `download_dataset.py` — pobranie datasetu AI arXiv
- `docker-compose.yml` — lokalne uruchomienie Qdrant z trwałym volumem `qdrant_data`

**Decyzje architektoniczne:** patrz `services/embedding-service/VECTOR_DB_DECISIONS.md`

---

### twitch-agent — Python / AI Agent

**Lokalizacja:** `services/twitch-agent/`

Agent AI oparty na modelu językowym, zintegrowany z platformą Twitch. Implementacja w pliku `agent.py`.

---

## Infrastruktura (GCP + Terraform)

**Lokalizacja:** `infra/`

Cała infrastruktura zarządzana jest przez **Terraform**. Istnieją dwa oddzielne środowiska: `dev` i `prod`.

```
infra/
├── main.tf              # główne zasoby GCP (Artifact Registry, Cloud SQL)
├── variables.tf
├── outputs.tf
├── purchase-service.tf  # zasoby dla purchase-service
├── dev/                 # środowisko deweloperskie
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── prod/                # środowisko produkcyjne
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── offers-service/      # zasoby dla offers-service
├── products-service/    # zasoby dla products-service
├── product-review-service/ # zasoby dla product-review-service
└── embedding-service/   # zasoby dla embedding-service
```

**Zasoby GCP zarządzane przez Terraform:**

| Zasób | Opis |
|-------|------|
| `google_cloud_run_service` | Hosting każdego mikroserwisu (serverless) |
| `google_sql_database_instance` | Cloud SQL PostgreSQL (dev + prod) |
| `google_artifact_registry_repository` | Rejestr obrazów Docker (`mini-allegro`) |
| `google_pubsub_topic` | Temat Pub/Sub `mini-allegro-service-logs` |
| `google_pubsub_subscription` | Subskrypcja pull (retencja 7 dni) |
| `google_compute_instance` | VM z Elasticsearch (Audit Log) |
| `google_firestore_database` | Firestore dla product-review-service |
| `google_monitoring_alert_policy` | Alert przy 5+ błędach w 5 minut |

**Kolejność deploymentu:**

```
terraform apply (Artifact Registry)
→ docker push (obraz do Artifact Registry)
→ terraform apply (Cloud Run + pozostałe zasoby)
```

**Uruchomienie infrastruktury:**

```bash
gcloud auth login
gcloud config set project paw-2026-496213
gcloud auth configure-docker europe-central2-docker.pkg.dev

cd infra
terraform init
terraform apply -var="alert_email=twoj.email@domena.pl"
```

---

## Audit Log — centralny system logowania

**Dokumentacja:** `audit-log-design.md`

Centralny system przechowujący historię wszystkich operacji na encjach w całym projekcie. Oparty o **event sourcing** — każda operacja CREATE/UPDATE/DELETE jest zapisywana jako niemutowalny log.

**Baza danych:** PostgreSQL (Cloud SQL) z tabelą `audit_logs` partycjonowaną kwartalnie po kolumnie `timestamp`.

**Struktura logu:**

```json
{
  "timestamp": "2026-05-06T10:23:00Z",
  "entity": "product",
  "operation": "CREATE",
  "payload": { "id": 42, "name": "Laptop", "price": 3499.99 },
  "endpoint": "/products/42"
}
```

**Obsługiwane encje:** `product`, `purchase`, `review`, `user`
**Obsługiwane operacje:** `CREATE`, `UPDATE` (delta — tylko zmienione pola), `DELETE` (payload = NULL)

**Indeksowanie:**

| Typ indeksu | Kolumna | Uzasadnienie |
|-------------|---------|--------------|
| BRIN | `timestamp` | Dane append-only, wstawiane chronologicznie — ułamek rozmiaru B-tree |
| B-tree | `entity`, `operation` | Szybkie filtrowanie po stałym zbiorze wartości |
| GIN | `payload` (JSONB) | Indeksuje każdy klucz i wartość wewnątrz JSON-a — bez tego full table scan |

**Partycjonowanie:**
```sql
CREATE TABLE audit_logs (...)
PARTITION BY RANGE (timestamp);

-- Q2 2026
CREATE TABLE audit_logs_2026_q2 PARTITION OF audit_logs
FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');
```

**API mikroserwisu `audit-log-service`:**

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `POST` | `/logs` | Zapisz log |
| `GET` | `/logs` | Pobierz wszystkie logi |
| `GET` | `/logs?entity=product` | Filtruj po encji |
| `GET` | `/logs?operation=DELETE` | Filtruj po operacji |

---

## Pub/Sub — komunikacja między serwisami

**Temat:** `mini-allegro-service-logs`
**Schemat:** Protobuf z polami `timestamp`, `entity`, `operation`, `payload`, `endpoint`

Aktualnie zintegrowany z `offers-service` — logi zdarzeń `CreateOffer` i `AssignSuperSeller` są publikowane do tematu. Architektura przewiduje podłączenie pozostałych serwisów.

---

## CI/CD (GitHub Actions)

**Lokalizacja:** `.github/workflows/`

Każdy mikroserwis ma własny pipeline. Główny workflow `deploy.yml`:

1. **Build** — `gcloud builds submit` lub `docker buildx` z cache w Artifact Registry
2. **Deploy DEV** — `terraform apply` → Cloud Run DEV
3. **Health check** — weryfikacja endpointu `/health`
4. **Testy integracyjne** — `pytest` (osobno dla `offers`, `users`, `products`)
5. **Auto-PR** — automatyczne tworzenie PR `develop → main` po udanym DEV health check
6. **Deploy PROD** — po merge do `main`

**Deploy produkcyjny z automatycznym rollbackiem:**

```bash
./services/symphony-monolith/scripts/deploy_prod_with_rollback.sh \
  --service mini-allegro \
  --region europe-central2 \
  --project paw-2026-496213 \
  --image europe-central2-docker.pkg.dev/paw-2026-496213/mini-allegro/mini-allegro:latest
```

Skrypt zapamiętuje poprzednią rewizję i przy błędzie healthchecka wykonuje rollback przez `gcloud run services update-traffic`.

**Wymagane sekrety GitHub Actions:**

| Sekret | Opis |
|--------|------|
| `DEV_DATABASE_URL` | Connection string do Cloud SQL DEV |
| `PROD_DATABASE_URL` | Connection string do Cloud SQL PROD |
| `TF_STATE_BUCKET` | Nazwa bucketu GCS na Terraform state |

---

## Testy integracyjne

Testy napisane w **pytest** (Python), strzelają do działającej instancji aplikacji przez HTTP.

```
integ-tests/
├── test_offers.py
├── test_users.py
└── test_products.py
```

**Uruchomienie lokalne:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/symphony-monolith/requirements-dev.txt

pytest integ-tests/test_offers.py
pytest integ-tests/test_users.py
pytest integ-tests/test_products.py
```

Domyślnie testy strzelają pod `http://localhost:8080`. Można zmienić URL:

```bash
APP_BASE_URL=https://twoj-serwis.run.app pytest integ-tests/
```

---

## Uruchomienie lokalne

**Skrypt pomocniczy:**

```bash
./scripts/local-app.sh up      # uruchom aplikację (Docker Compose)
./scripts/local-app.sh test    # uruchom testy integracyjne
./scripts/local-app.sh logs    # podejrzyj logi
./scripts/local-app.sh status  # sprawdź status
./scripts/local-app.sh stop    # zatrzymaj
./scripts/local-app.sh down    # usuń kontenery
```

`local-app.sh` automatycznie pobiera `DATABASE_URL` z Terraform (`infra/dev`) — lokalna instancja łączy się z bazą DEV na Cloud SQL.

**Lokalne uruchomienie embedding-service:**

```bash
cd services/embedding-service

# Uruchom Qdrant (vector DB)
docker compose up -d

# Pobierz dataset
python download_dataset.py

# Uruchom embedowanie (np. pierwsze 500 rekordów testowo)
python embed_and_store.py --limit 500

# Dashboard Qdrant dostępny pod: http://localhost:6333/dashboard
```

Do embedowania przez Gemini wymagana zmienna środowiskowa `GEMINI_API_KEY`.
Do embedowania przez Ollama wymagane uruchomienie: `ollama serve` + `ollama pull nomic-embed-text`.

---

## Zespół i podział prac

Projekt realizowały **4 osoby** w ciągu semestru 2025/2026.

### Łukasz Błok — wkład własny

#### 1. CI/CD i infrastruktura bazowa — od zera

Jako jeden z pierwszych ustawił pełny pipeline GitHub Actions dla projektu:
- Workflow `deploy.yml` — build obrazu Docker, deploy na Cloud Run, health check, testy integracyjne
- Automatyczne tworzenie PR `develop → main` po udanym health checku na DEV
- Dodanie linków do deployu w GitHub Actions summary (commit URL, PR URL, URL serwisu)
- Pierwsza szkieletowa infrastruktura Terraform (`hello-lukasz`)
- Naprawa szeregu problemów z pipeline'em: uprawnienia `pull-requests write`, checkout przed `gh pr create`, IAM binding dla publicznego dostępu, autoloader Symfony w kontenerze

#### 2. Product Review Service — Java / Spring Boot

Największy wkład funkcjonalny w projekcie:

- **Szkielet serwisu** `product-review-service` w Java/Spring Boot od zera (hardcoded data → PostgreSQL → Firestore)
- **Migracja bazy danych** z PostgreSQL na **Google Cloud Firestore** (zmiana architektury storage)
- **Infrastruktura Terraform** dla serwisu (Cloud Run, Firestore) w osobnym module
- **Integracja z monolitem Symfony** — delegowanie `GET /product-reviews` i `POST /product-reviews` z monolitu do mikroserwisu przez Symfony HTTP Client
- Dodanie `symfony/http-client` do zależności monolitu
- Zwiększenie timeoutu HTTP Clienta (obsługa cold startu Cloud Run)
- Dodanie `offer_id` jako klucza obcego, endpointy `/reviews-super`
- Testy integracyjne dla reviews (`integ-tests/`)
- CI/CD dla feature branchy serwisu (osobny workflow `feature.yml`)
- Naprawa duplikatów bloków Firestore w Terraform

#### 3. Audit Log Service

- Zaprojektowanie i wdrożenie centralnego serwisu logowania operacji (event sourcing)
- Architektura `audit_logs` w PostgreSQL: tabela partycjonowana kwartalnie po `timestamp`
- Indeksowanie: BRIN na timestamp, B-tree na entity/operation, GIN na JSONB payload
- Infrastruktura Terraform: VM z **Elasticsearch** na GCP Compute Engine
- Automatyczny restart VM przy błędzie połączenia (`auto-start Elasticsearch VM on connection error`)
- Naprawka Compute Engine API (`google_project_service` przed tworzeniem VM i firewall)
- Dodanie `AUDIT_LOG_SERVICE_URL` do środowisk wszystkich serwisów

#### 4. Embedding Service — semantyczne wyszukiwanie dokumentów

Zbudowanie pipelinu embedowania dla systemu wyszukiwania semantycznego nad bazą wiedzy AI arXiv:

- Skrypt `embed_and_store.py` — wczytuje 41 584 chunków tekstowych z datasetu AI arXiv i zapisuje ich embeddingi do Qdrant
- Integracja z **dwoma modelami embeddings równocześnie**:
  - `nomic-embed-text` (768 dims) przez **Ollama** (lokalnie)
  - `gemini-embedding-2` (3072 dims) przez **Google Gemini API**
- Architektura **named vectors** w Qdrant — jedna kolekcja, dwie przestrzenie wektorowe; użytkownik wybiera model w UI
- Batch processing po 50 rekordów, pasek postępu `tqdm`, parametr `--limit` do testowania
- Debugowanie i migracja z przestarzałego `google.generativeai` na nowe SDK `google.genai`
- Konfiguracja trwałego storage Qdrant (Docker volume `qdrant_data`)
- Dokumentacja decyzji architektonicznych: `VECTOR_DB_DECISIONS.md` (wybór Qdrant vs pgvector/Pinecone/Weaviate, opis algorytmu HNSW, cosine similarity)

**Flow wyszukiwania zaimplementowany przez Łukasza:**
```
użytkownik wpisuje frazę + wybiera model
→ system generuje embedding frazy tym samym modelem
→ Qdrant ANN search (HNSW) w wybranej przestrzeni named vector
→ top-K najbardziej podobnych chunków z artykułów naukowych
```

#### 5. Integracje i merge

- Dodanie `symfony-purchase` mikroserwisu (praca kolegi) do głównego repo bez naruszania istniejących zmian
- Seryjne naprawy konfliktów merge w `product-review-service` Terraform (`main.tf`)
- Merge branchy `fixed → develop`

---

## Technologie wykorzystane przez Łukasza Błoka

### Języki programowania i frameworki

| Technologia | Zastosowanie |
|-------------|-------------|
| **Java** | Implementacja `product-review-service` (Spring Boot) |
| **Spring Boot** | Framework dla mikroserwisu recenzji — REST API, dependency injection, konfiguracja |
| **Python 3** | Skrypty embedding-service (`embed_and_store.py`, `download_dataset.py`) oraz testy integracyjne (pytest) |
| **PHP 8.3 / Symfony 7** | Rozszerzanie monolitu — integracja HTTP Client z mikroserwisem recenzji |

### Bazy danych i storage

| Technologia | Zastosowanie |
|-------------|-------------|
| **PostgreSQL** | Baza główna aplikacji oraz tabela `audit_logs` (Cloud SQL) |
| **Google Cloud Firestore** | Migracja storage dla `product-review-service` z PostgreSQL na NoSQL |
| **Qdrant** | Vector database do przechowywania embeddingów (named vectors, HNSW ANN search) |
| **Elasticsearch** | VM na GCP Compute Engine — backend dla Audit Log Service |

### AI / ML / Embeddingi

| Technologia | Zastosowanie |
|-------------|-------------|
| **Google Gemini API** (`google-genai`) | Generowanie embeddingów przez model `gemini-embedding-2` (3072 dims) |
| **Ollama** | Lokalne generowanie embeddingów przez model `nomic-embed-text` (768 dims) |
| **Qdrant** (HNSW) | Przybliżone wyszukiwanie nearest neighbor (cosine similarity) |
| **HuggingFace `datasets`** | Wczytywanie datasetu AI arXiv z dysku |

### Infrastruktura i Cloud

| Technologia | Zastosowanie |
|-------------|-------------|
| **Google Cloud Platform (GCP)** | Cała infrastruktura projektu (projekt `paw-2026-496213`, region `europe-central2`) |
| **Google Cloud Run** | Serverless hosting mikroserwisów (auto-skalowanie, pay-per-use) |
| **Google Cloud SQL** | Zarządzana baza PostgreSQL (DEV + PROD) |
| **Google Artifact Registry** | Rejestr obrazów Docker |
| **Google Cloud Compute Engine** | VM z Elasticsearch dla Audit Log |
| **Google Cloud Firestore** | NoSQL document database dla product-review-service |
| **Google Cloud Pub/Sub** | Asynchroniczna komunikacja między serwisami (cherry-pick integracji) |
| **Google Cloud Monitoring** | Alert policy (5+ błędów w 5 minut → email) |
| **Terraform** | Infrastructure as Code — zarządzanie wszystkimi zasobami GCP |
| **gcloud CLI** | Operacje na GCP z linii poleceń (deploy, healthcheck, rollback) |

### Konteneryzacja i DevOps

| Technologia | Zastosowanie |
|-------------|-------------|
| **Docker** | Konteneryzacja `product-review-service` i embedding-service |
| **Docker Compose** | Lokalne uruchomienie Qdrant z trwałym volumem `qdrant_data` |
| **Docker Buildx** | Multi-platform build (`linux/amd64`) z cache w Artifact Registry |
| **Google Cloud Build** | Build obrazów Docker po stronie GCP (szybszy niż lokalny) |

### CI/CD i automatyzacja

| Technologia | Zastosowanie |
|-------------|-------------|
| **GitHub Actions** | Główny pipeline CI/CD — build, deploy, testy, auto-PR |
| **gh CLI** | Tworzenie Pull Requestów z poziomu pipeline'u |
| **Maven** | Build tool dla `product-review-service` (Java) |
| **pytest** | Testy integracyjne API (Python) |

### Narzędzia developerskie

| Technologia | Zastosowanie |
|-------------|-------------|
| **Git** | Wersjonowanie kodu, praca na branchach, merge/rebase |
| **GitHub** | Hosting repozytorium, Pull Requesty, code review |
| **tqdm** | Pasek postępu w skrypcie embedowania |
| **PowerShell** | Uruchamianie skryptów na Windows (środowisko deweloperskie) |

---

## Proces pracy na wspólnym repozytorium GitHub

### Struktura branchy

Projekt używał klasycznego modelu **Git Flow** z dwoma głównymi gałęziami:

```
main        ← kod produkcyjny, zawsze stabilny, chroniony przed bezpośrednim push
develop     ← bieżący stan prac, tu trafiają gotowe funkcjonalności
```

Każda nowa funkcjonalność powstawała na osobnym **feature branchu** odgałęzionym od `develop`:

```
develop
  ├── feat/review-service          (Łukasz — product-review-service)
  ├── feat/reviews                 (Łukasz — integracja z monolitem)
  ├── ci/review-feature-workflow   (Łukasz — CI/CD dla reviews)
  ├── feat/pubsub-service-logging  (Szymon — Pub/Sub)
  ├── fixed                        (Łukasz — audit-log + purchase)
  └── docs/vector-db-decisions     (Łukasz — embedding-service docs)
```

### Typowy cykl pracy

```
1. Odgałęzienie feature brancha od develop
   git checkout develop
   git pull origin develop
   git checkout -b feat/moja-funkcjonalnosc

2. Praca lokalna — commity na feature branchu
   git add <pliki>
   git commit -m "feat(review): opis zmiany"

3. Push feature brancha do GitHub
   git push origin feat/moja-funkcjonalnosc

4. Otwarcie Pull Requesta (develop ← feat/moja-funkcjonalnosc)
   - code review przez innych członków zespołu
   - GitHub Actions uruchamia automatyczne testy (build + deploy DEV + pytest)
   - po akceptacji — merge do develop

5. Po udanym merge do develop:
   - GitHub Actions deployuje na środowisko DEV
   - wykonuje health check na /health
   - automatycznie tworzy PR: main ← develop

6. Merge do main → deploy na PROD
```

### Automatyzacja przez GitHub Actions

Kluczowym elementem procesu był w pełni zautomatyzowany pipeline stworzony przez Łukasza. Po każdym push do `develop`:

1. Budowany jest obraz Docker przez **Cloud Build** (natywnie na `linux/amd64`, z cache w Artifact Registry)
2. Obraz deployowany jest na **Cloud Run DEV**
3. Pipeline wykonuje **health check** (`/health`) — czeka na odpowiedź 200 OK
4. Uruchamiane są **testy integracyjne** (`pytest`) osobno dla każdej encji
5. Przy sukcesie tworzony jest automatyczny **Pull Request** `develop → main`
6. Po merge do `main` — ten sam proces na środowisku **PROD**

W razie błędu na produkcji skrypt `deploy_prod_with_rollback.sh` automatycznie przywraca poprzednią rewizję Cloud Run.

### Rozwiązywanie konfliktów merge

Przy równoległej pracy 4 osób na tych samych plikach infrastruktury Terraform (`main.tf`) regularnie pojawiały się konflikty merge. Typowy proces ich rozwiązywania:

```bash
# Aktualizacja lokalnej kopii develop
git fetch origin
git checkout develop
git pull origin develop

# Próba merge feature brancha
git checkout feat/moja-funkcjonalnosc
git merge develop

# Przy konflikcie — ręczne rozwiązanie w edytorze:
# <<<<<< HEAD (moje zmiany)
# ======
# >>>>>> develop (zmiany z develop)
# → usunięcie markerów, zachowanie właściwej treści

git add infra/product-review-service/main.tf
git commit -m "merge: resolve conflict in product-review-service main.tf"
git push origin feat/moja-funkcjonalnosc
```

### Pobieranie pracy kolegi bez naruszania własnych zmian

Kiedy kolega miał gotową funkcjonalność na osobnym branchu, a nie chciało się tracić własnych niezamergowanych zmian, używany był **cherry-pick** — przeniesienie konkretnego commita na własny branch:

```bash
# Pobierz branch kolegi lokalnie
git fetch origin feat/pubsub-service-logging

# Sprawdź SHA commita który chcesz przenieść
git log origin/feat/pubsub-service-logging --oneline

# Cherry-pick — skopiuj ten commit na swój branch
git cherry-pick <SHA>
```

Dzięki temu zmiany kolegi trafiały na właściwy branch bez konieczności mergowania całej jego gałęzi.

### Konwencja commitów

Projekt stosował konwencję **Conventional Commits**:

```
<typ>(<zakres>): <opis>

feat(review): add product-review-service skeleton
fix(infra): remove duplicate Firestore resource blocks
ci(review): add feature branch workflow
docs(embedding-service): add vector DB design decisions
chore: ignore .claude/ directory
merge: resolve conflict in product-review-service main.tf
```

Typy: `feat` (nowa funkcja), `fix` (naprawa błędu), `ci` (CI/CD), `docs` (dokumentacja), `chore` (porządki), `merge` (merge konfliktów).
