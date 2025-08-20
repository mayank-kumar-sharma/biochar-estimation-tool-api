from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from pyproj import Geod
from PIL import Image
import re
import io

app = FastAPI(
    title="Biochar Estimation API",
    version="1.0",
    description="API to estimate biochar yield from direct area, polygon coordinates, or JPEG images."
)

# --- Feedstock Lookup Table ---
FEEDSTOCK_DATA = {
    "Rice husk": {"density": 96, "yield_factor": 0.25, "default_height": 0.2},
    "Wood chips": {"density": 208, "yield_factor": 0.30, "default_height": 0.3},
    "Corn cobs": {"density": 190, "yield_factor": 0.28, "default_height": 0.25},
    "Coconut shells": {"density": 220, "yield_factor": 0.35, "default_height": 0.3},
    "Bamboo": {"density": 180, "yield_factor": 0.33, "default_height": 0.25},
    "Sugarcane bagasse": {"density": 140, "yield_factor": 0.22, "default_height": 0.2},
    "Groundnut shells": {"density": 130, "yield_factor": 0.26, "default_height": 0.2},
    "Sludge": {"density": 110, "yield_factor": 0.50, "default_height": 0.15},
}

COVERAGE_FRACTION = 0.05    # 5% of land covered with biomass
geod = Geod(ellps="WGS84")

# --- Resolution mapping for JPEG image sources ---
RESOLUTION_LOOKUP = {
    "Satellite": 0.04,
    "Low Drone": 0.06,
    "High Drone": 0.02
}

# --- Request Schemas ---
class DirectAreaRequest(BaseModel):
    feedstock_type: str
    hectares: float
    pile_height: float | None = None

class PolygonRequest(BaseModel):
    feedstock_type: str
    coordinates: str   # "lat,lon\nlat,lon\n..."
    pile_height: float | None = None

# --- Response Schema (Only final outputs) ---
class BiocharResponse(BaseModel):
    biomass_mass_kg: float
    biochar_yield_kg: float
    application_rate_kg_per_ha: float

# --- Core Calculation ---
def calculate(feedstock_type: str, area_m2: float, pile_height: float | None):
    if feedstock_type not in FEEDSTOCK_DATA:
        raise HTTPException(status_code=400, detail="Invalid feedstock type")

    feedstock_info = FEEDSTOCK_DATA[feedstock_type]
    height_m = pile_height if pile_height else feedstock_info["default_height"]

    density = feedstock_info["density"]
    yield_factor = feedstock_info["yield_factor"]
    area_ha = area_m2 / 10000.0

    # Apply coverage fraction
    pile_area_m2 = area_m2 * COVERAGE_FRACTION
    volume_m3 = pile_area_m2 * height_m

    # Biomass & biochar calculation
    biomass_kg = volume_m3 * density
    biochar_kg = biomass_kg * yield_factor
    application_rate_kg_per_ha = biochar_kg / area_ha if area_ha > 0 else 0

    return BiocharResponse(
        biomass_mass_kg=round(biomass_kg, 2),
        biochar_yield_kg=round(biochar_kg, 2),
        application_rate_kg_per_ha=round(application_rate_kg_per_ha, 2)
    )

# --- Endpoints ---
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Biochar Estimation API is running"}

@app.post("/estimate/direct", response_model=BiocharResponse)
def estimate_direct(req: DirectAreaRequest):
    area_m2 = req.hectares * 10000
    return calculate(req.feedstock_type, area_m2, req.pile_height)

@app.post("/estimate/polygon", response_model=BiocharResponse)
def estimate_polygon(req: PolygonRequest):
    try:
        coords = [tuple(map(float, re.split(r"[,\s]+", line.strip())))
                  for line in req.coordinates.strip().split("\n") if line.strip()]
        if len(coords) < 3:
            raise HTTPException(status_code=400, detail="At least 3 coordinate points required.")
        lons, lats = zip(*[(lon, lat) for lat, lon in coords])
        area_m2, _ = geod.polygon_area_perimeter(lons, lats)
        area_m2 = abs(area_m2)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid coordinate format. Use 'lat,lon' per line.")

    return calculate(req.feedstock_type, area_m2, req.pile_height)

# --- Updated JPEG Endpoint ---
@app.post("/estimate/jpeg", response_model=BiocharResponse)
async def estimate_jpeg(
    feedstock_type: str = Form(...),
    pile_height: float = Form(None),
    image_source: str = Form(...),   # New form field
    file: UploadFile = File(...)
):
    # Validate image source
    if image_source not in RESOLUTION_LOOKUP:
        raise HTTPException(status_code=400, detail="Invalid image source. Choose Satellite, Low Drone, or High Drone.")

    resolution = RESOLUTION_LOOKUP[image_source]

    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        width, height = image.size
        area_m2 = (width * resolution) * (height * resolution)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JPEG image.")

    return calculate(feedstock_type, area_m2, pile_height)
