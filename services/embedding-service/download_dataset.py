from datasets import load_dataset
from pathlib import Path
import datasets

# pokazuje pasek postepu podczas pobierania
datasets.utils.logging.set_verbosity_info()

SAVE_PATH = Path(__file__).parent / "data" / "ai-arxiv-chunked"

print("Pobieranie datasetu z HuggingFace...")
dataset = load_dataset("jamescalam/ai-arxiv-chunked", split="train")

total = len(dataset)
print(f"\nPobrano {total} rekordow")
print(f"Kolumny: {dataset.column_names}")
print(f"\nPrzykladowy rekord:")
print(dataset[0])

SAVE_PATH.mkdir(parents=True, exist_ok=True)
print(f"\nZapisywanie na dysk: {SAVE_PATH}...")
dataset.save_to_disk(str(SAVE_PATH))
print(f"Gotowe! Dataset zapisany w: {SAVE_PATH}")
