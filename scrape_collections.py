import os
import json
import time
import logging
import requests
from playwright.sync_api import sync_playwright

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set!")

GEMINI_MODEL = "gemini-2.0-flash"

# Keywords that strongly indicate a collection/bundle on Steamrip
COLLECTION_KEYWORDS = [
    "anthology", "trilogy", "collection", "complete edition", 
    "complete pack", "bundle", "chronicles", "remastered collection"
]

# URLs to scrape (add more as needed)
TARGET_URLS = [
    "https://steamrip.com/games-list-page/",
    # Add specific collection pages here if they aren't in the main list
    # e.g., "https://steamrip.com/half-life-free-download-m1/"
]

def fetch_page_content(url: str) -> str | None:
    """Scrape page content using Playwright."""
    logger.info(f"Scraping {url}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--disable-gpu', '--no-sandbox'])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)  # Allow dynamic content to load
            
            # Extract all visible text from the article/content area
            content = page.evaluate("""() => {
                // Try common content selectors first
                const article = document.querySelector('article, .entry-content, .post-content, #the-post');
                if (article) return article.innerText;
                
                // Fallback: get all body text but exclude nav/footer
                const body = document.body.cloneNode(true);
                ['nav', 'footer', 'header', 'script', 'style'].forEach(tag => {
                    body.querySelectorAll(tag).forEach(el => el.remove());
                });
                return body.innerText;
            }""")
            browser.close()
            
        logger.info(f"Successfully scraped {len(content)} characters from {url}")
        return content
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return None

def detect_and_extract_games(title: str, content: str) -> list[str]:
    """Use Gemini to determine if this is a collection and extract individual games."""
    
    # Quick keyword check - skip if definitely not a collection
    title_lower = title.lower()
    if not any(kw in title_lower for kw in COLLECTION_KEYWORDS):
        logger.debug(f"'{title}' doesn't match collection keywords, skipping.")
        return []
    
    logger.info(f"Analyzing '{title}' for collection contents...")
    
    prompt = f"""You are an expert video game analyst specializing in Steamrip collections.

Analyze the following game page content. The page title is: "{title}"

Determine if this page represents a COLLECTION/BUNDLE containing multiple individual standalone PC games.

RULES:
1. If it IS a collection, return ONLY a JSON array of the EXACT Steam store titles of each individual game included.
2. If it is a single game or DLC, return an empty array [].
3. Do NOT include DLCs, soundtracks, or non-game items in the output.
4. Return ONLY valid JSON. No markdown formatting. No explanations.

Examples:
- "Half-Life Anthology" -> ["Half-Life", "Half-Life: Opposing Force", "Half-Life: Blue Shift"]
- "Assassin's Creed Chronicles Trilogy" -> ["Assassin's Creed Chronicles: China", "Assassin's Creed Chronicles: India", "Assassin's Creed Chronicles: Russia"]
- "Resident Evil 4 Ultimate HD Edition" -> []
- "Cyberpunk 2077" -> []

Page content:
{content[:8000]}
"""
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "response_mime_type": "application/json"
            }
        }
        
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        
        response_data = r.json()
        candidates = response_data.get("candidates", [])
        if not candidates:
            logger.warning(f"No candidates returned for '{title}'")
            return []
        
        response_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "[]")
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        result = json.loads(response_text)
        
        if isinstance(result, list) and len(result) > 0:
            logger.info(f"'{title}' contains {len(result)} games: {result}")
            return result
        else:
            logger.debug(f"'{title}' is not a collection (returned: {result})")
            return []
            
    except Exception as e:
        logger.error(f"Gemini analysis failed for '{title}': {e}")
        return []

def main():
    """Main entry point for GitHub Actions."""
    logger.info("=" * 60)
    logger.info("Steamrip Collection Scraper Starting")
    logger.info("=" * 60)
    
    results = {}
    
    for url in TARGET_URLS:
        content = fetch_page_content(url)
        if not content:
            continue
        
        # Extract potential collection titles from the page
        # Look for links/titles that contain collection keywords
        potential_collections = []
        
        # Parse the page for game titles that look like collections
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if any(kw in line.lower() for kw in COLLECTION_KEYWORDS) and len(line) < 200:
                # Clean up the title
                title = line.split('Free Download')[0].strip()
                if title and len(title) > 5:
                    potential_collections.append((title, content))
        
        # Also check if the page itself might be a collection based on its URL/title
        page_title = url.split('/')[-1].replace('-', ' ').replace('.html', '').title()
        if any(kw in page_title.lower() for kw in COLLECTION_KEYWORDS):
            potential_collections.insert(0, (page_title, content))
        
        logger.info(f"Found {len(potential_collections)} potential collections on {url}")
        
        for title, content in potential_collections:
            games = detect_and_extract_games(title, content)
            if games:
                results[title] = games
    
    # Save results
    output_file = "collections.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info("=" * 60)
    logger.info(f"Results saved to {output_file}")
    logger.info(f"Total collections found: {len(results)}")
    for title, games in results.items():
        logger.info(f"  - {title}: {len(games)} games")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
