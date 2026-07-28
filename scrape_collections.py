import json
import os
import requests
from playwright.sync_api import sync_playwright

def main():
    print("🚀 ==========================================")
    print("🚀 Starting Steamrip Collection Scraper")
    print("🚀 ==========================================")
    
    games_list_url = "https://steamrip.com/games-list-page/"
    print(f"🔍 [1/4] Fetching games list from {games_list_url}...")
    
    games = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--disable-gpu', '--no-sandbox'])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            page = context.new_page()
            page.goto(games_list_url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for the list to load
            try:
                page.wait_for_selector('.az-list-item a', timeout=10000)
            except:
                print("⚠️ Could not find .az-list-item a, trying alternative...")
            
            # Extract all games
            extracted = page.evaluate("""() => {
                const items = [];
                const links = document.querySelectorAll('.az-list-item a');
                links.forEach(link => {
                    items.push({
                        title: link.innerText.trim(),
                        url: link.href
                    });
                });
                return items;
            }""")
            browser.close()
            
        # Remove duplicates and empty titles
        seen = set()
        for item in extracted:
            if item['title'] and item['title'] not in seen:
                games.append(item)
                seen.add(item['title'])
                
        print(f"✅ [1/4] Found {len(games)} unique games on Steamrip")
        
    except Exception as e:
        print(f"❌ Failed to fetch games list: {e}")
        # Save empty JSON to avoid workflow failure
        with open("collections.json", "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
        return

    if not games:
        print("❌ No games found. Exiting.")
        with open("collections.json", "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
        return

    print("🔍 [2/4] Identifying potential collections...")
    collection_keywords = ["trilogy", "anthology", "collection", "complete edition", "complete pack", "bundle", "remastered collection"]
    
    potential_collections = []
    for game in games:
        if any(kw in game['title'].lower() for kw in collection_keywords):
            potential_collections.append(game)
            
    print(f"✅ [2/4] Found {len(potential_collections)} potential collections.")

    if not potential_collections:
        print("✅ No collections found. Saving empty result.")
        with open("collections.json", "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
        return

    print("🔍 [3/4] Scraping collection pages and extracting individual games...")
    
    collections_data = {}
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--disable-gpu', '--no-sandbox'])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = context.new_page()
            
            for game in potential_collections:
                print(f"  -> Scraping: {game['title']}")
                try:
                    page.goto(game['url'], wait_until="domcontentloaded", timeout=15000)
                    try:
                        page.wait_for_selector('.entry-content', timeout=5000)
                    except:
                        pass
                    
                    entry_text = page.evaluate("""() => {
                        const entry = document.querySelector('.entry-content');
                        return entry ? entry.innerText : '';
                    }""")
                    
                    included_games = []
                    if gemini_api_key:
                        prompt = f"""You are an expert in video games. 
Analyze the following text from a game download page.
Extract the EXACT titles of the individual, distinct games included in this collection/bundle.
If it is a single game or you cannot find multiple distinct games, return an empty array [].
Return ONLY a valid JSON array of strings.

Page text:
{entry_text[:3000]}
"""
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={gemini_api_key}"
                        payload = {
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"temperature": 0.0, "response_mime_type": "application/json"}
                        }
                        r = requests.post(url, json=payload, timeout=15)
                        if r.status_code == 200:
                            resp_data = r.json()
                            resp_text = resp_data["candidates"][0]["content"]["parts"][0]["text"].replace("```json", "").replace("```", "").strip()
                            try:
                                included_games = json.loads(resp_text)
                            except:
                                included_games = []
                    
                    if included_games and len(included_games) > 0:
                        print(f"     ✅ Extracted {len(included_games)} games: {included_games}")
                        collections_data[game['title']] = included_games
                    else:
                        print(f"     ⚠️ No individual games found for {game['title']}")
                        
                except Exception as e:
                    print(f"     ❌ Failed to scrape {game['title']}: {e}")
                    
            browser.close()
            
    except Exception as e:
        print(f"❌ Failed to scrape collection pages: {e}")
        return

    print("✅ [3/4] Extraction complete.")
    
    print("💾 [4/4] Saving to collections.json...")
    with open("collections.json", "w", encoding="utf-8") as f:
        json.dump(collections_data, f, indent=2)
    print("✅ [4/4] Saved successfully!")

if __name__ == "__main__":
    main()
