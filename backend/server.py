from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import requests
from urllib.parse import quote


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter()


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class TourismQuery(BaseModel):
    place: str

class TourismResponse(BaseModel):
    success: bool
    message: str
    place: Optional[str] = None
    coordinates: Optional[dict] = None

# ==================== AGENT FUNCTIONS ====================

def geo_agent(place_name: str) -> dict:
    """
    GeoAgent: Finds coordinates of a place using Nominatim API.
    Returns: {"status": "found"/"not_found", "lat": float, "lon": float, "display_name": str}
    """
    try:
        url = f"https://nominatim.openstreetmap.org/search"
        params = {
            "q": place_name,
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": "TourismPlanner/1.0"}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data or len(data) == 0:
            return {"status": "not_found"}
        
        place_data = data[0]
        return {
            "status": "found",
            "lat": float(place_data["lat"]),
            "lon": float(place_data["lon"]),
            "display_name": place_data.get("display_name", place_name)
        }
    except Exception as e:
        logging.error(f"GeoAgent error: {str(e)}")
        return {"status": "error", "message": str(e)}


def weather_agent(lat: float, lon: float) -> dict:
    """
    WeatherAgent: Fetches weather information using Open-Meteo API.
    Returns: {"status": "success"/"error", "temperature": float, "precipitation_prob": float}
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "hourly": "temperature_2m,precipitation_probability,relativehumidity_2m,windspeed_10m",
            "timezone": "auto",
            "forecast_hours": 1
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current_weather = data.get("current_weather", {})
        temperature = current_weather.get("temperature", 0)
        
        # Get current hour's precipitation probability
        hourly_data = data.get("hourly", {})
        precip_probs = hourly_data.get("precipitation_probability", [])
        current_precip = precip_probs[0] if precip_probs else 0
        
        # Get humidity for more accurate weather info
        humidity = hourly_data.get("relativehumidity_2m", [])[0] if hourly_data.get("relativehumidity_2m") else 0
        wind_speed = hourly_data.get("windspeed_10m", [])[0] if hourly_data.get("windspeed_10m") else 0
        
        return {
            "status": "success",
            "temperature": round(temperature, 1),
            "precipitation_prob": round(current_precip, 1),
            "humidity": round(humidity, 1),
            "windspeed": round(wind_speed, 1)
        }
    except Exception as e:
        logging.error(f"WeatherAgent error: {str(e)}")
        return {"status": "error", "message": str(e)}


def generate_wikipedia_url(place_name: str, tags: dict) -> str:
    """Generate Wikipedia URL for a place."""
    import urllib.parse
    
    # Try to use existing Wikipedia tag if available
    wikipedia_tag = tags.get("wikipedia")
    if wikipedia_tag:
        # Handle different language Wikipedia formats
        if ":" in wikipedia_tag:
            lang, article = wikipedia_tag.split(":", 1)
            return f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(article.replace(' ', '_'))}"
        else:
            return f"https://en.wikipedia.org/wiki/{urllib.parse.quote(wikipedia_tag.replace(' ', '_'))}"
    
    # Try to use Wikidata tag to find Wikipedia article
    wikidata_tag = tags.get("wikidata")
    if wikidata_tag:
        # For now, generate based on place name (could be enhanced with Wikidata API)
        pass
    
    # Generate Wikipedia URL based on place name
    clean_name = place_name.strip()
    
    # Common place name patterns to improve Wikipedia search
    name_mappings = {
        "Lalbagh": "Lalbagh Botanical Garden",
        "Cubbon Park": "Cubbon Park",
        "Bangalore Palace": "Bangalore Palace",
        "Bannerghatta National Park": "Bannerghatta National Park",
        "Jawaharlal Nehru Planetarium": "Jawaharlal Nehru Planetarium, Bangalore",
        "MG Road": "Mahatma Gandhi Road, Bangalore",
        "Commercial Street": "Commercial Street, Bangalore",
        "Brigade Road": "Brigade Road",
        "UB City": "UB City",
        "Vidhana Soudha": "Vidhana Soudha",
        "Tipu Sultan's Summer Palace": "Tipu Sultan's Summer Palace",
        "Bull Temple": "Bull Temple",
        "ISKCON Temple": "ISKCON Temple Bangalore",
        "St. Mary's Basilica": "St. Mary's Basilica, Bangalore",
        "Bangalore Fort": "Bangalore Fort",
        "Lalbagh Glasshouse": "Lalbagh Botanical Garden"
    }
    
    # Use mapped name if available
    wiki_name = name_mappings.get(clean_name, clean_name)
    
    # Create Wikipedia URL
    encoded_name = urllib.parse.quote(wiki_name.replace(' ', '_'))
    return f"https://en.wikipedia.org/wiki/{encoded_name}"


def places_agent(lat: float, lon: float, radius: int = 10000) -> dict:
    """
    PlacesAgent: Finds tourist attractions using Overpass API with Wikipedia links.
    Returns: {"status": "success"/"error", "places": [list of place names with Wikipedia URLs]}
    """
    try:
        url = "https://overpass-api.de/api/interpreter"
        
        # Simple Overpass query for tourist attractions
        query = f"""
        [out:json][timeout:25];
        (
          node["tourism"](around:{radius},{lat},{lon});
          node["historic"](around:{radius},{lat},{lon});
          node["amenity"~"museum|gallery|theatre"](around:{radius},{lat},{lon});
          node["leisure"~"park|garden"](around:{radius},{lat},{lon});
          way["tourism"](around:{radius},{lat},{lon});
          way["historic"](around:{radius},{lat},{lon});
          way["amenity"~"museum|gallery|theatre"](around:{radius},{lat},{lon});
          way["leisure"~"park|garden"](around:{radius},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        response = requests.post(url, data={"data": query}, timeout=25)
        response.raise_for_status()
        data = response.json()
        
        elements = data.get("elements", [])
        places = []
        seen_places = set()
        
        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name")
            
            if name and name not in seen_places:
                # Generate Wikipedia URL for the place
                wikipedia_url = generate_wikipedia_url(name, tags)
                
                place_data = {
                    "name": name.strip(),
                    "wikipedia_url": wikipedia_url
                }
                places.append(place_data)
                seen_places.add(name.strip())
            
            if len(places) >= 5:
                break
        
        return {
            "status": "success",
            "places": places[:5]  # Return exactly 5 places with Wikipedia URLs
        }
    except Exception as e:
        logging.error(f"PlacesAgent error: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_place_category(tags: dict) -> str:
    """Determine the category of a place based on its tags."""
    if tags.get("tourism"):
        tourism = tags["tourism"]
        if tourism in ["museum", "gallery"]:
            return "Museum & Gallery"
        elif tourism in ["attraction", "theme_park", "amusement_park"]:
            return "Attraction & Entertainment"
        elif tourism in ["zoo", "aquarium"]:
            return "Wildlife & Nature"
        elif tourism in ["viewpoint", "artwork", "monument"]:
            return "Landmark & Viewpoint"
    
    if tags.get("historic"):
        return "Historic Site"
    
    if tags.get("amenity"):
        amenity = tags["amenity"]
        if amenity in ["theatre", "cinema", "concert_hall"]:
            return "Arts & Culture"
        elif amenity in ["restaurant", "cafe"]:
            return "Food & Dining"
    
    if tags.get("leisure"):
        leisure = tags["leisure"]
        if leisure in ["park", "garden", "nature_reserve"]:
            return "Park & Nature"
        elif leisure in ["stadium", "sports_centre", "arena"]:
            return "Sports & Recreation"
    
    if tags.get("building"):
        building = tags["building"]
        if building in ["church", "cathedral", "temple", "mosque"]:
            return "Religious Site"
    
    return "Tourist Attraction"

def get_place_description(tags: dict, name: str) -> str:
    """Generate a description for a place based on its tags."""
    descriptions = {
        "museum": f"Explore fascinating exhibits and collections at {name}",
        "park": f"Enjoy nature and outdoor activities at {name}",
        "church": f"Visit this beautiful religious site at {name}",
        "castle": f"Discover history and architecture at {name}",
        "palace": f"Experience grandeur and royalty at {name}",
        "garden": f"Wander through beautiful landscapes at {name}",
        "monument": f"Pay tribute to history at {name}",
        "theatre": f"Enjoy cultural performances at {name}",
        "stadium": f"Experience exciting events at {name}",
        "zoo": f"Meet amazing animals from around the world at {name}",
        "aquarium": f"Discover marine life at {name}",
        "gallery": f"Admire artistic masterpieces at {name}",
        "temple": f"Experience spiritual tranquility at {name}",
        "mosque": f"Appreciate Islamic architecture at {name}",
        "cathedral": f"Marvel at Gothic architecture at {name}",
        "viewpoint": f"Enjoy breathtaking views from {name}",
        "beach": f"Relax by the sea at {name}",
        "lake": f"Enjoy peaceful waterside scenery at {name}",
        "mountain": f"Experience majestic mountain landscapes at {name}"
    }
    
    # Check tags for specific place types
    for key, desc in descriptions.items():
        if tags.get(key) or tags.get("tourism") == key or tags.get("leisure") == key or tags.get("historic") == key:
            return desc
    
    # Use Wikipedia description if available
    if tags.get("wikipedia"):
        return f"Learn more about this notable destination: {name}"
    
    # Use generic description based on available information
    if tags.get("tourism"):
        return f"A popular tourist destination worth visiting"
    elif tags.get("historic"):
        return f"A historic site with cultural significance"
    elif tags.get("leisure"):
        return f"A great place for recreation and leisure"
    else:
        return f"An interesting place to explore and discover"

def get_place_image(tags: dict, name: str, lat: float, lon: float) -> str:
    """Get an image URL for a place."""
    # Try to get image from OpenStreetMap tags
    if tags.get("image"):
        return tags["image"]
    
    # Use Wikimedia Commons for free images based on place name
    import urllib.parse
    encoded_name = urllib.parse.quote(name)
    return f"https://picsum.photos/seed/{encoded_name.replace(' ', '')}/400/300.jpg"
    
    # Alternative: Use OpenStreetMap static tiles (free)
    # return f"https://tile.openstreetmap.org/17/{int(lat*100000)%40000}/{int(lon*100000)%40000}.png"


def extract_place_name(user_input: str) -> str:
    """Extract the place name from user input."""
    import re
    
    # Convert to lowercase for processing
    input_lower = user_input.lower()
    
    # More comprehensive patterns to extract place name
    patterns = [
        r"going to ([a-z\s]+),",
        r"going to ([a-z\s]+)\?",
        r"going to ([a-z\s]+)$",
        r"to ([a-z\s]+),",
        r"to ([a-z\s]+)\?",
        r"to ([a-z\s]+)$",
        r"visit ([a-z\s]+)",
        r"about ([a-z\s]+)",
        r"search ([a-z\s]+)",
        r"find ([a-z\s]+)",
        r"what's the weather in ([a-z\s]+)",
        r"weather in ([a-z\s]+)",
        r"places to visit in ([a-z\s]+)",
        r"attractions in ([a-z\s]+)",
        r"what can i do in ([a-z\s]+)",
        r"tell me about ([a-z\s]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, input_lower)
        if match:
            place = match.group(1).strip()
            # Clean up common stop words at the end
            stop_words = [
                "what is the temperature there",
                "and what are the places i can visit",
                "lets plan my trip",
                "what's the weather",
                "weather and",
                "attractions and",
                "for my trip",
                "today",
                "now",
                "right now"
            ]
            for word in stop_words:
                place = place.replace(word, "").strip()
            # Remove extra spaces and capitalize properly
            place = " ".join(place.split()).title()
            return place if place else user_input.strip()
    
    # Try to find capitalized words that might be place names
    words = user_input.split()
    place_words = []
    
    # Look for words that start with capital letter (common for place names)
    for word in words:
        if word[0].isupper() and len(word) > 2 and not word.startswith("I"):
            place_words.append(word.strip(".,?!"))
    
    if place_words:
        return " ".join(place_words[:3])  # Take first 3 capitalized words
    
    # Fallback: return the last word if it looks like a place
    last_word = words[-1].strip(".,?!")
    if last_word and len(last_word) > 2 and last_word[0].isupper():
        return last_word.title()
    
    # Final fallback: try to extract from common patterns
    common_places = {
        "bangalore": "Bangalore",
        "paris": "Paris", 
        "london": "London",
        "new york": "New York",
        "tokyo": "Tokyo",
        "dubai": "Dubai",
        "singapore": "Singapore",
        "sydney": "Sydney",
        "mumbai": "Mumbai",
        "delhi": "Delhi",
        "berlin": "Berlin",
        "rome": "Rome",
        "barcelona": "Barcelona",
        "amsterdam": "Amsterdam",
        "bali": "Bali",
        "thailand": "Thailand",
        "malaysia": "Malaysia",
        "usa": "USA",
        "uk": "UK",
        "uae": "UAE"
    }
    
    for place_key, place_value in common_places.items():
        if place_key in input_lower:
            return place_value
    
    # If all else fails, return the cleaned input
    return user_input.strip().title()

def tourism_agent(user_input: str) -> dict:
    """
    TourismAgent: Main orchestrator that coordinates all child agents.
    Handles natural language input and provides appropriate responses.
    """
    # Extract place name from user input
    place_name = extract_place_name(user_input)
    
    # Step 1: Get coordinates using GeoAgent
    geo_result = geo_agent(place_name)
    
    # Handle non-existent places
    if geo_result.get("status") != "found":
        return {
            "success": False,
            "message": f"I don't know if the place '{place_name}' exists. Please try a different location."
        }
    
    lat = geo_result["lat"]
    lon = geo_result["lon"]
    display_name = geo_result["display_name"]
    
    # Initialize response parts
    response_parts = []
    
    # Check what information is being asked for
    user_lower = user_input.lower()
    asks_for_weather = any(term in user_lower for term in ["temperature", "weather", "climate", "forecast", "rain", "hot", "cold"])
    asks_for_places = any(term in user_lower for term in ["places", "visit", "attractions", "plan my trip", "see", "do", "tourist", "sightseeing"])
    
    # Always show both weather and places for any place search
    asks_for_weather = True
    asks_for_places = True
    
    # Get weather if requested
    weather_info = ""
    if asks_for_weather:
        weather_result = weather_agent(lat, lon)
        if weather_result.get("status") == "success":
            temp = weather_result["temperature"]
            precip = weather_result["precipitation_prob"]
            weather_info = f"In {display_name} it's currently {temp}°C with a chance of {precip}% to rain."
    
    # Get places if requested
    places_info = ""
    if asks_for_places:
        places_result = places_agent(lat, lon)
        if places_result.get("status") == "success" and places_result.get("places"):
            places = places_result["places"]
            if places:
                # Format places with names only (for backward compatibility with frontend)
                place_names = []
                for place in places[:5]:
                    if isinstance(place, dict):
                        place_names.append(place["name"])
                    else:
                        place_names.append(str(place))
                places_list = "\n".join(place_names)
                places_info = f"In {display_name} these are the places you can go,\n{places_list}"
            else:
                places_info = f"In {display_name} there are no specific tourist attractions found nearby."
    
    # Combine the responses
    if weather_info and places_info:
        # Extract just the places list from places_info
        places_list = places_info.replace(f"In {display_name} these are the places you can go,\n", "")
        response = f"{weather_info} And these are the places you can go:\n{places_list}"
    else:
        response = weather_info + places_info
    
    return {
        "success": True,
        "message": response,
        "place": display_name,
        "coordinates": {"lat": lat, "lon": lon},
        "places_data": places if asks_for_places else []  # Include detailed place data with Wikipedia URLs
    }

# ==================== API ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "Tourism Planner API"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

@api_router.post("/tourism/query", response_model=TourismResponse)
async def query_tourism(query: TourismQuery):
    """
    Main endpoint for tourism queries.
    Accepts a place name and returns weather + attractions info.
    """
    if not query.place or len(query.place.strip()) == 0:
        raise HTTPException(status_code=400, detail="Place name cannot be empty")
    
    result = tourism_agent(query.place.strip())
    return result

# Include the router in the main app
app.include_router(api_router, prefix="/api")

# Add a root endpoint for the main app
@app.get("/")
async def app_root():
    return {"message": "Tourism Planner API - Root", "docs": "/api/docs"}

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()