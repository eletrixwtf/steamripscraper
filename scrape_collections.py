import requests
from bs4 import BeautifulSoup
import json
import os

def scrape_games():
    url = "https://steamrip.com/games-list-page/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    print(f"🔍 Scraping {url}...")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch page. Status code: {response.status_code}")
        return []
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Based on the provided HTML source, games are in: <li class="az-list-item"><a href="...">Title</a></li>
    game_links = soup.select('li.az-list-item a')
    
    games = []
    for link in game_links:
        title = link.get_text(strip=True)
        href = link.get('href')
        
        # Clean up the title slightly for better AI processing
        clean_title = title.replace("Free Download", "").strip()
        
        # Ensure it's a valid absolute URL
        if href and href.startswith('/'):
            full_url = f"https://steamrip.com{href}"
        else:
            # Fallback for absolute URLs or malformed links
            full_url = href if href else ""
            
        games.append({
            "title": clean_title,
            "url": full_url
        })
        
    print(f"✅ Found {len(games)} total games on Steamrip")
    return games

def find_collections(games):
    print(f"🔍 Analyzing games for collections...")
    
    # Filter down to only potential collections to save API calls and time
    keywords = ["trilogy", "collection", "anthology", "chronicles", "compilation"]
    potential_collections = [game['title'] for game in games if any(kw in game['title'].lower() for kw in keywords)]
    
    print(f"📦 Found {len(potential_collections)} potential collections based on keywords.")
    
    if not potential_collections:
        return {}
        
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not found in environment variables.")
        return {}
    
    prompt = f"""You are an expert in video game collections.
I have a list of game titles from a website that are likely collections, anthologies, or trilogies.
For each title, determine the EXACT individual game titles included in that collection.
Return ONLY a valid JSON object where keys are the exact collection titles from the input, and values are arrays of the individual game titles.

Example:
{{
  "Assassin's Creed Chronicles Trilogy": ["Assassin's Creed Chronicles: China", "Assassin's Creed Chronicles: India", "Assassin's Creed Chronicles: Russia"],
  "Half-Life Anthology": ["Half-Life", "Half-Life: Opposing Force", "Half-Life: Blue Shift", "Team Fortress Classic"]
}}

Titles to analyze:
{json.dumps(potential_collections, indent=2)}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={gemini_api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "response_mime_type": "application/json"
        }
    }
    
    print("🤖 Sending to Gemini AI...")
    response = requests.post(url, json=payload)
    
    if response.status_code != 200:
        print(f"❌ Gemini API failed. Status code: {response.status_code}")
        print(response.text)
        return {}
        
    try:
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        text = text.replace("```json", "").replace("```", "").strip()
        collections_data = json.loads(text)
        print(f"✅ Gemini identified {len(collections_data)} collections.")
        return collections_data
    except Exception as e:
        print(f"❌ Failed to parse Gemini response: {e}")
        return {}

if __name__ == "__main__":
    games = scrape_games()
    
    # Save all games list (useful for debugging or future features)
    with open("games_list.json", "w", encoding="utf-8") as f:
        json.dump(games, f, indent=2)
    print(f"💾 Saved games_list.json ({len(games)} games)")
    
    collections = find_collections(games)
    
    # Save the final collections mapping
    with open("collections.json", "w", encoding="utf-8") as f:
        json.dump(collections, f, indent=2)
    print(f"💾 Saved collections.json ({len(collections)} collections)")
    
    print("✅ Done!")
