import os
import re
import json
import requests
from playwright.sync_api import sync_playwright

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
STEAMRIP_URL = "https://steamrip.com/games-list-page/"

def scrape_games_list():
    """Scrapes all games from Steamrip A-Z list and returns list of {name, url}"""
    print(f"🔍 Scraping {STEAMRIP_URL}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(STEAMRIP_URL, wait_until="domcontentloaded", timeout=60000)
        
        # Extract all game links from the A-Z list
        games = page.evaluate("""() => {
            const games = [];
            // Target the actual game links in the A-Z directory
            const links = document.querySelectorAll('.az-list-item a');
            links.forEach(link => {
                const name = link.innerText.trim();
                const url = link.getAttribute('href');
                if (name && url && !name.includes('Free Download')) {
                    games.push({ name: name, url: url });
                }
            });
            return games;
        }""")
        browser.close()
    
    print(f"✅ Found {len(games)} total games on Steamrip")
    return games

def detect_collections_with_gemini(games):
    """Sends game list to Gemini and returns dict of {game_name: is_collection_bool}"""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    # Prepare the list for Gemini - only send names and URLs
    titles_for_ai = [{"name": g["name"], "url": g["url"]} for g in games]
    
    prompt = f"""You are an expert video game analyst and Steam database expert.
I have a list of game download titles from Steamrip. Some of these titles represent Steam bundles, anthologies, or collections containing multiple individual standalone PC games. Others are single standalone games.

For EACH title provided, determine if it corresponds to a known Steam bundle/anthology/collection.

CRITICAL RULES:
1. If the title is a collection/bundle/anthology (e.g., 'Half-Life', 'Assassin's Creed Chronicles Trilogy'), return TRUE.
2. If the title is strictly a single standalone game or DLC/expansion, return FALSE.
3. Ignore console-specific bundles. Only focus on PC Steam bundles/anthologies.
4. Return ONLY a valid JSON object where keys are the EXACT game names from input and values are boolean (true/false). Do not include markdown formatting.

Format:
{{
  "Exact Game Name From Input": true,
  "Another Game Name": false
}}

Games to analyze ({len(titles_for_ai)} total):
{json.dumps(titles_for_ai, indent=2)}
"""
    
    print(f" Sending {len(titles_for_ai)} games to Gemini AI...")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "response_mime_type": "application/json"
        }
    }
    
    r = requests.post(url, json=payload, timeout=300)
    r.raise_for_status()
    
    response_data = r.json()
    candidates = response_data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini API returned no candidates")
    
    response_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
    response_text = response_text.replace("```json", "").replace("```", "").strip()
    
    collection_map = json.loads(response_text)
    print(f"✅ Gemini identified {sum(1 for v in collection_map.values() if v)} collections out of {len(collection_map)} games")
    
    return collection_map

if __name__ == "__main__":
    try:
        # Step 1: Scrape all games
        games = scrape_games_list()
        
        # Save complete games list
        with open("games_list.json", "w", encoding="utf-8") as f:
            json.dump(games, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved games_list.json ({len(games)} games)")
        
        # Step 2: Detect collections via Gemini
        collection_map = detect_collections_with_gemini(games)
        
        # Save collections map
        with open("collections.json", "w", encoding="utf-8") as f:
            json.dump(collection_map, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved collections.json ({sum(1 for v in collection_map.values() if v)} collections)")
        
        print("✅ Done!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
