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
api_router = APIRouter(prefix="/api")


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
            "hourly": "precipitation_probability"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current_weather = data.get("current_weather", {})
        temperature = current_weather.get("temperature", "N/A")
        
        # Get average precipitation probability for next few hours
        hourly_precip = data.get("hourly", {}).get("precipitation_probability", [])
        avg_precip = sum(hourly_precip[:6]) / 6 if hourly_precip else 0
        
        return {
            "status": "success",
            "temperature": temperature,
            "precipitation_prob": round(avg_precip, 1),
            "windspeed": current_weather.get("windspeed", "N/A")
        }
    except Exception as e:
        logging.error(f"WeatherAgent error: {str(e)}")
        return {"status": "error", "message": str(e)}


def places_agent(lat: float, lon: float, radius: int = 5000) -> dict:
    """
    PlacesAgent: Finds tourist attractions using Overpass API.
    Returns: {"status": "success"/"error", "places": [list of place names]}
    """
    try:
        url = "https://overpass-api.de/api/interpreter"
        
        # Overpass query to find tourism attractions
        query = f"""
        [out:json][timeout:25];
        (
          node["tourism"](around:{radius},{lat},{lon});
          way["tourism"](around:{radius},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        response = requests.post(url, data={"data": query}, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        elements = data.get("elements", [])
        places = []
        
        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name")
            if name and name not in places:
                places.append(name)
            
            if len(places) >= 5:
                break
        
        return {
            "status": "success",
            "places": places
        }
    except Exception as e:
        logging.error(f"PlacesAgent error: {str(e)}")
        return {"status": "error", "message": str(e)}


def tourism_agent(place_name: str) -> dict:
    """
    TourismAgent: Main orchestrator that coordinates all child agents.
    """
    # Step 1: Get coordinates using GeoAgent
    geo_result = geo_agent(place_name)
    
    if geo_result.get("status") == "not_found":
        return {
            "success": False,
            "message": f"I don't know if the place '{place_name}' exists. Please try a different location."
        }
    
    if geo_result.get("status") == "error":
        return {
            "success": False,
            "message": f"Error finding location: {geo_result.get('message', 'Unknown error')}"
        }
    
    lat = geo_result["lat"]
    lon = geo_result["lon"]
    display_name = geo_result["display_name"]
    
    # Step 2: Get weather using WeatherAgent
    weather_result = weather_agent(lat, lon)
    
    # Step 3: Get places using PlacesAgent
    places_result = places_agent(lat, lon)
    
    # Step 4: Combine all results into a clean summary
    summary_parts = []
    summary_parts.append(f"📍 Location: {display_name}")
    summary_parts.append(f"📐 Coordinates: {lat:.4f}, {lon:.4f}")
    summary_parts.append("")
    
    # Weather info
    if weather_result.get("status") == "success":
        temp = weather_result["temperature"]
        precip = weather_result["precipitation_prob"]
        wind = weather_result["windspeed"]
        summary_parts.append(f"🌤️ Weather: {temp}°C with {precip}% chance of rain")
        summary_parts.append(f"💨 Wind speed: {wind} km/h")
    else:
        summary_parts.append("⚠️ Weather information unavailable")
    
    summary_parts.append("")
    
    # Places info
    if places_result.get("status") == "success":
        places = places_result["places"]
        if places:
            summary_parts.append(f"🎯 Top {len(places)} attractions to visit:")
            for i, place in enumerate(places, 1):
                summary_parts.append(f"  {i}. {place}")
        else:
            summary_parts.append("📍 No major tourist attractions found in this area.")
    else:
        summary_parts.append("⚠️ Unable to fetch tourist attractions")
    
    return {
        "success": True,
        "message": "\n".join(summary_parts),
        "place": display_name,
        "coordinates": {"lat": lat, "lon": lon}
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
app.include_router(api_router)

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