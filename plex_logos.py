import os
import requests
import re
import time
import logging
import json
from datetime import datetime
from plexapi.server import PlexServer
from PIL import Image
from io import BytesIO
from rapidfuzz import fuzz

# --- CONFIGURATION (via Environment Variables) ---
PLEX_URL = os.environ.get('PLEX_URL')
PLEX_TOKEN = os.environ.get('PLEX_TOKEN')
FANART_API_KEY = os.environ.get('FANART_API_KEY')
LIBRARY_NAME = os.environ.get('LIBRARY_NAME', 'Music')
UPDATE_PLEX = os.environ.get('UPDATE_PLEX', 'False').lower() == 'true'
FORCE_REFRESH = os.environ.get('FORCE_REFRESH', 'False').lower() == 'true'
FUZZY_THRESHOLD = int(os.environ.get('FUZZY_THRESHOLD', 90))
BASE_OUTPUT_DIR = '/app/ArtistLogos'
LOG_DIR = '/app/Logs'

# Ensure directories exist
for folder in [BASE_OUTPUT_DIR, LOG_DIR]:
    os.makedirs(folder, exist_ok=True)

# --- LOGGING SETUP ---
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(LOG_DIR, f"run_{timestamp}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
)
logger = logging.getLogger()

stats = {
    "total_scanned": 0,
    "already_exists_skipped": 0,
    "new_downloads": 0,
    "plex_posters_updated": 0,
    "not_found_list": [],
    "errors": 0
}

def sanitize(name):
    """Removes illegal characters for folder paths."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_logo(mbid, plex_name):
    """Fetches logo from Fanart.tv with fuzzy validation and SD fallback."""
    time.sleep(0.3)  # Rate limiting
    url = f"https://webservice.fanart.tv/v3/music/{mbid}?api_key={FANART_API_KEY}"
    
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 404:
            return None, "Artist MBID not found in Fanart.tv database"
            
        if res.status_code == 200:
            data = res.json()
            fanart_name = data.get('name', 'Unknown')
            score = fuzz.token_sort_ratio(plex_name, fanart_name)
            
            if score < FUZZY_THRESHOLD:
                return None, f"Fuzzy Match Failed (Score: {score}, Fanart Name: '{fanart_name}')"
            
            # Asset Priority: HD Logo > Standard Logo
            hd = data.get('hdmusiclogo', [])
            sd = data.get('musiclogo', [])
            
            if hd:
                return hd[0]['url'], f"Success (HD) - Match: {score}%"
            elif sd:
                return sd[0]['url'], f"Success (SD Fallback) - Match: {score}%"
            else:
                return None, "Artist exists on Fanart, but has no Logo assets (only backgrounds/art)"
                
        return None, f"API Error (Status: {res.status_code})"
    except Exception as e:
        return None, f"Connection Error: {str(e)}"

def process_image(url, save_path):
    """Downloads image, makes it square with black background."""
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        img = Image.open(BytesIO(res.content)).convert("RGBA")
        
        # Create square canvas
        side = max(img.size)
        canvas = Image.new('RGB', (side, side), (0, 0, 0))
        
        # Center the logo
        offset = ((side - img.width) // 2, (side - img.height) // 2)
        canvas.paste(img, offset, img)
        
        canvas.save(save_path, "JPEG", quality=95)
        return True
    except Exception as e:
        logger.error(f"  Image Processing Error: {e}")
        return False

# --- MAIN EXECUTION ---
try:
    logger.info("Connecting to Plex...")
    plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    music = plex.library.section(LIBRARY_NAME)
    artists = music.all()
    stats["total_scanned"] = len(artists)
    logger.info(f"Scanning {len(artists)} artists in library '{LIBRARY_NAME}'...")
except Exception as e:
    logger.critical(f"Plex Connection Failed: {e}")
    exit(1)

for artist in artists:
    try:
        clean_name = sanitize(artist.title)
        artist_dir = os.path.join(BASE_OUTPUT_DIR, clean_name)
        img_path = os.path.join(artist_dir, "artist.jpg")

        # Skip logic
        if os.path.exists(img_path) and not FORCE_REFRESH:
            stats["already_exists_skipped"] += 1
            continue

        # MBID Extraction
        mbid = next((g.id.split('://')[-1] for g in artist.guids if 'mbid' in g.id), None)
        if not mbid:
            reason = "Plex has no MusicBrainz ID for this artist"
            stats["not_found_list"].append(f"{artist.title} | {reason}")
            logger.info(f"Skipping: {artist.title} -> {reason}")
            continue

        # API Fetch
        logo_url, result_msg = get_logo(mbid, artist.title)
        
        if logo_url:
            os.makedirs(artist_dir, exist_ok=True)
            if process_image(logo_url, img_path):
                logger.info(f"✅ Saved: {artist.title} ({result_msg})")
                stats["new_downloads"] += 1
                
                if UPDATE_PLEX:
                    try:
                        artist.uploadPoster(filepath=img_path)
                        stats["plex_posters_updated"] += 1
                    except Exception as pe:
                        logger.error(f"  Plex Upload Failed for {artist.title}: {pe}")
        else:
            stats["not_found_list"].append(f"{artist.title} | {result_msg}")
            logger.warning(f"Missing: {artist.title} -> {result_msg}")

    except Exception as e:
        stats["errors"] += 1
        logger.error(f"Critical error on {artist.title}: {e}")

# --- WRAP UP ---
# Save Not Found report
with open(os.path.join(LOG_DIR, f"missing_report_{timestamp}.txt"), "w") as f:
    f.write(f"Artists missing logos as of {timestamp}\n")
    f.write("="*50 + "\n")
    f.write("\n".join(stats["not_found_list"]))

# Save Stats JSON
with open(os.path.join(LOG_DIR, f"stats_{timestamp}.json"), "w") as f:
    json.dump(stats, f, indent=4)

logger.info(f"""
Run Complete!
- Scanned: {stats['total_scanned']}
- New Downloads: {stats['new_downloads']}
- Plex Updates: {stats['plex_posters_updated']}
- Skipped (Already Local): {stats['already_exists_skipped']}
- Not Found (See report): {len(stats['not_found_list'])}
""")