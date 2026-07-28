import json
from playwright.sync_api import sync_playwright

def main():
    print("🚀 ==========================================")
    print("🚀 Starting Steamrip Games Scraper")
    print("🚀 ==========================================")
    
    games_list_url = "https://steamrip.com/games-list-page/"
    print(f"🔍 Fetching games list from {games_list_url}...")
    
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
            except Exception:
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
                
        print(f"✅ Found {len(games)} unique games on Steamrip")
        
    except Exception as e:
        print(f"❌ Failed to fetch games list: {e}")
        # Save empty JSON to avoid workflow failure
        with open("games_list.json", "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        return

    if not games:
        print("❌ No games found. Exiting.")
        with open("games_list.json", "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        return

    print("💾 Saving to games_list.json...")
    with open("games_list.json", "w", encoding="utf-8") as f:
        json.dump(games, f, indent=2)
    print("✅ Saved successfully!")

if __name__ == "__main__":
    main()
