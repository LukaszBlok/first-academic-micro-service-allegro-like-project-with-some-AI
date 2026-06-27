import asyncio
import ollama
import json
from playwright.async_api import async_playwright, Browser, BrowserContext

# -- Globalne obiekty przegladarki
browser: Browser = None
context: BrowserContext = None

# -- Inicjalizacja Playwright
async def init_browser():
    global browser, context
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    print("Przegladarka uruchomiona")

# -- Ollama - generuje zapytania
async def get_search_queries(user_question: str) -> list[str]:
    prompt = f"""
Uzytkownik pyta: "{user_question}"

Wygeneruj dokladnie 5 zapytan do wyszukiwarki Google ktore najlepiej odpowiedza na to pytanie.
Odpowiedz TYLKO jako JSON, bez zadnego tekstu przed ani po. Format:
{{"queries": ["zapytanie 1", "zapytanie 2", "zapytanie 3", "zapytanie 4", "zapytanie 5"]}}
"""
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}]
        )
    )

    raw = response["message"]["content"]

    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
        return data["queries"]
    except Exception as e:
        print(f"Blad parsowania JSON: {e}")
        return [user_question]

# -- Playwright - otwiera karty
async def open_tabs(queries: list[str]):
    pages = []
    for i, query in enumerate(queries):
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        page = await context.new_page()
        await page.goto(url)
        pages.append(page)
        print(f"Karta {i+1}: {query}")

    if pages:
        await pages[0].bring_to_front()

# -- Agent
async def run_agent(question: str):
    print(f"\nAgent uruchomiony dla: '{question}'")
    print("Ollama generuje zapytania...")
    queries = await get_search_queries(question)
    print(f"Zapytania: {queries}")
    await open_tabs(queries)
    print(f"Gotowe! Otwarto {len(queries)} kart.\n")

# -- Glowna petla terminala
async def listen_terminal():
    print("Wpisz pytanie i wcisnij Enter (Ctrl+C aby wyjsc):\n")
    loop = asyncio.get_event_loop()

    while True:
        question = await loop.run_in_executor(None, input, ">> ")
        question = question.strip()
        if question:
            await run_agent(question)

# -- Start
async def main():
    await init_browser()
    try:
        await listen_terminal()
    except KeyboardInterrupt:
        print("\nZamykam...")
    finally:
        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
