import os
import argparse
import requests
from pathlib import Path
from datasets import load_from_disk
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from tqdm import tqdm
from google import genai

# --- konfiguracja ---
DATASET_PATH = Path(__file__).parent / "data" / "ai-arxiv-chunked"
TEXT_COLUMN = "chunk"
COLLECTION_NAME = "ai-arxiv"
BATCH_SIZE = 50

QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# nazwa modelu -> rozmiar wektora
MODELS = {
    "nomic-embed-text": 768,
    "gemini-embedding-2": 3072,
}

# --- klienci ---
qdrant = QdrantClient(url=QDRANT_URL)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def create_collection():
    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME in existing:
        qdrant.delete_collection(COLLECTION_NAME)
        print(f"Kolekcja '{COLLECTION_NAME}' usunieta (przebudowa schematu).")
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            name: VectorParams(size=size, distance=Distance.COSINE)
            for name, size in MODELS.items()
        },
    )
    print(f"Kolekcja '{COLLECTION_NAME}' utworzona z named vectors: {list(MODELS.keys())}.")


def embed_ollama(texts: list[str]) -> list[list[float]]:
    embeddings = []
    for text in texts:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
        )
        response.raise_for_status()
        embeddings.append(response.json()["embedding"])
    return embeddings


def embed_gemini(texts: list[str]) -> list[list[float]]:
    embeddings = []
    for text in texts:
        result = gemini_client.models.embed_content(
            model="gemini-embedding-2",
            contents=text,
            config={"output_dimensionality": MODELS["gemini-embedding-2"]},
        )
        embeddings.append(result.embeddings[0].values)
    return embeddings


EMBED_FN = {
    "nomic-embed-text": embed_ollama,
    "gemini-embedding-2": embed_gemini,
}


def embed_and_store(dataset):
    total = len(dataset)
    texts = [dataset[i][TEXT_COLUMN] for i in range(total)]

    print(f"\nEmbedowanie {total} rekordow (modele: {list(MODELS.keys())})...")

    with tqdm(total=total, unit="rek") as bar:
        for i in range(0, total, BATCH_SIZE):
            batch_texts = texts[i:i + BATCH_SIZE]

            # embeduj kazdy batch przez wszystkie aktywne modele
            batch_vectors = {
                model: EMBED_FN[model](batch_texts)
                for model in MODELS
            }

            points = [
                PointStruct(
                    id=i + j,
                    vector={model: batch_vectors[model][j] for model in MODELS},
                    payload={"raw": batch_texts[j]},
                )
                for j in range(len(batch_texts))
            ]

            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
            bar.update(len(batch_texts))

    print(f"Zapisano {total} punktow do Qdrant.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Ile rekordow przetworzyc (domyslnie: wszystkie)")
    args = parser.parse_args()

    print("Ladowanie datasetu z dysku...")
    dataset = load_from_disk(str(DATASET_PATH))
    if args.limit:
        dataset = dataset.select(range(args.limit))
    print(f"Zaladowano {len(dataset)} rekordow.")

    create_collection()
    embed_and_store(dataset)

    print("\nGotowe! Wszystkie embeddingi zapisane w Qdrant.")
