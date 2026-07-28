import requests
from bs4 import BeautifulSoup
import json
import os
import time

# ==========================================
# CONFIGURATION
# ==========================================
GAMES_LIST_URL = "https://steamrip.com/games-list-page/"
GAMES_JSON_FILE = "games_list.json"
COLLECTIONS_JSON_FILE = "collections.json"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def fetch_games_list():
    print(f"🔍 [1/4] Fetching games list from {GAMES_LIST_URL}...")
    try:
        response = requests.get(GAMES_LIST_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        games = []
        # Look for post titles in the main content. SteamRIP uses <h3 class="post-title"><a href="...">Game Name</a></h3>
        post_titles = soup.find_all('h3', class_='post-title')
        
        for h3 in post_titles:
            a_tag = h3.find('a')
            if a_tag and a_tag.get('href'):
                name = a_tag.get_text(strip=True)
                link = a_tag['href']
                if not link.startswith('http'):
                    link = "https://steamrip.com" + link
                
                # Basic validation to ensure it's a game post and not a category/archive page
                if "/category/" not in link and "/page/" not in link:
                    games.append({"name": name, "link": link})
        
        # Remove duplicates based on link
        seen = set()
        unique_games = []
        for game in games:
            if game['link'] not in seen:
                seen.add(game['link'])
                unique_games.append(game)
                
        print(f"✅ [1/4] Found {len(unique_games)} unique games on Steamrip")
        return unique_games
        
    except Exception as e:
        print(f"❌ [1/4] Failed to fetch games list: {e}")
        return []

def save_games_json(games):
    print(f"💾 [2/4] Saving {GAMES_JSON_FILE}...")
    try:
        with open(GAMES_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(games, f, indent=2, ensure_ascii=False)
        print(f"✅ [2/4] Successfully saved {len(games)} games to {GAMES_JSON_FILE}")
    except Exception as e:
        print(f"❌ [2/4] Failed to save games JSON: {e}")

def analyze_collections_with_gemini(potential_collections):
    print(f"🤖 [3/4] Analyzing {len(potential_collections)} potential collections with Gemini AI...")
    
    # Format the list nicely for the prompt
    titles_list = "\n".join([f"- {gc['name']}" for gc in potential_collections])
    
    prompt = f"""You are an expert in PC gaming and Steam game collections.
I have a list of game download page titles from a website. Some of these titles represent multi-game collections, anthologies, or trilogies, while others are single games.

Your task:
1. Identify which of the provided titles are actually multi-game collections/bundles.
2. For each collection, list the EXACT individual game titles included in that bundle, based on your knowledge of the game.
3. If a title is a single game, ignore it (do not include it in the output).

Return ONLY a valid JSON object where the keys are the collection titles (exactly as provided in the list) and the values are arrays of individual game title strings.
Example format:
{{
  "Assassin's Creed Chronicles Trilogy": ["Assassin's Creed Chronicles: China", "Assassin's Creed Chronicles: India", "Assassin's Creed Chronicles: Russia"]
}}
(Only include keys that are actual collections. Omit single games entirely).

Here is the list of titles to analyze:
{titles_list}
"""

    try:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json"
            }
        }
        
        headers = {"Content-Type": "application/json"}
        url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        
        print("📡 Sending request to Gemini API (this may take a moment)...")
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        print(f"📡 Gemini API Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Gemini API Error Response:\n{response.text}")
            return {}
            
        response_data = response.json()
        print("✅ Received response from Gemini API")
        
        # Robust parsing of Gemini response
        candidates = response_data.get("candidates", [])
        if not candidates:
            print("❌ Gemini API returned no candidates.")
            print(f"Full response: {json.dumps(response_data, indent=2)}")
            return {}
            
        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        
        if not parts:
            print("❌ Gemini API response has no 'parts' in 'content'.")
            print(f"Full candidate: {json.dumps(candidate, indent=2)}")
            return {}
            
        response_text = parts[0].get("text", "{}")
        
        # Clean up markdown formatting if present
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        try:
            parsed_result = json.loads(response_text)
            print("✅ Successfully parsed JSON response from Gemini")
            
            # Filter out any null values or single games if the AI included them
            final_collections = {k: v for k, v in parsed_result.items() if isinstance(v, list) and len(v) > 0}
            print(f"📦 Identified {len(final_collections)} valid collections.")
            return final_collections
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON from Gemini response: {e}")
            print(f"Raw text returned by Gemini:\n{response_text}")
            return {}
            
    except Exception as e:
        print(f"❌ Exception during Gemini API call: {e}")
        return {}

def save_collections_json(collections):
    print(f"💾 [4/4] Saving {COLLECTIONS_JSON_FILE}...")
    try:
        with open(COLLECTIONS_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(collections, f, indent=2, ensure_ascii=False)
        print(f"✅ [4/4] Successfully saved {len(collections)} collections to {COLLECTIONS_JSON_FILE}")
    except Exception as e:
        print(f"❌ [4/4] Failed to save collections JSON: {e}")

def main():
    print("🚀 ==========================================")
    print("🚀 Starting Steamrip Collection Scraper")
    print("🚀 ==========================================")
    
    # Step 1: Fetch all games
    games = fetch_games_list()
    if not games:
        print("❌ No games found. Exiting.")
        return
        
    # Step 2: Save games JSON
    save_games_json(games)
    
    # Step 3: Filter potential collections based on keywords
    keywords = ["trilogy", "anthology", "collection", "complete edition", "complete pack", "bundle", "remastered collection"]
    potential_collections = []
    for game in games:
        if any(kw in game['name'].lower() for kw in keywords):
            potential_collections.append(game)
            
    print(f"📦 Found {len(potential_collections)} potential collections based on keywords.")
    
    if not potential_collections:
        print("✅ No potential collections found. Done!")
        save_collections_json({})
        return
        
    # Step 4: Analyze with Gemini
    collections_data = analyze_collections_with_gemini(potential_collections)
    
    # Step 5: Save results
    save_collections_json(collections_data)
    
    print("🚀 ==========================================")
    print("✅ Done!")
    print("🚀 ==========================================")

if __name__ == "__main__":
    main()
