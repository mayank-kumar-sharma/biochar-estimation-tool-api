from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from shapely.geometry import Polygon
from pyproj import Geod
from PIL import Image
import re
import io

app = FastAPI(title="Biochar Estimator API", version="1.0")

# --- Static Lookup Tables ---
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

COVERAGE_FRACTION = 0.05    # 5% of land covered
DEFAULT_RESOLUTION = 0.04   # m/pixel
geod = Geod(ellps="WGS84")

# --- Request Schemas ---
class DirectAreaRequest(BaseModel):
    feedstock_type: str
    hectares: float
    pile_height: float | None = None

class PolygonRequest(BaseModel):
    feedstock_type: str
    coordinates: str   # "lat,lon\nlat,lon\n..."
    pile_height: float | None = None

# --- Response Schema ---
class BiocharResponse(BaseModel):
    area_m2: float
    area_hectares: float
    pile_area_m2: float
    pile_area_hectares: float
    volume_m3: float
    biomass_mass_kg: float
    biochar_yield_kg: float
    application_rate_kg_per_ha: float


def calculate(feedstock_type: str, area_m2: float, pile_height: float | None):
    feedstock_info = FEEDSTOCK_DATA[feedstock_type]
    height_m = pile_height if pile_height else feedstock_info["default_height"]

    density = feedstock_info["density"]
    yield_factor = feedstock_info["yield_factor"]
    area_ha = area_m2 / 10000.0

    pile_area_m2 = area_m2 * COVERAGE_FRACTION
    volume_m3 = pile_area_m2 * height_m
    biomass_kg = volume_m3 * density
    biochar_kg = biomass_kg * yield_factor
    application_rate_kg_per_ha = biochar_kg / area_ha if area_ha > 0 else 0

    return BiocharResponse(
        area_m2=round(area_m2, 2),
        area_hectares=round(area_ha, 2),
        pile_area_m2=round(pile_area_m2, 2),
        pile_area_hectares=round(pile_area_m2/10000, 4),
        volume_m3=round(volume_m3, 2),
        biomass_mass_kg=round(biomass_kg, 2),
        biochar_yield_kg=round(biochar_kg, 2),
        application_rate_kg_per_ha=round(application_rate_kg_per_ha, 2)
    )


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
            return {"error": "At least 3 coordinate points required."}
        lons, lats = zip(*[(lon, lat) for lat, lon in coords])
        area_m2, _ = geod.polygon_area_perimeter(lons, lats)
        area_m2 = abs(area_m2)
    except Exception:
        return {"error": "Invalid coordinate format. Please use 'lat,lon' per line."}

    return calculate(req.feedstock_type, area_m2, req.pile_height)


@app.post("/estimate/jpeg", response_model=BiocharResponse)
async def estimate_jpeg(feedstock_type: str = Form(...), 
                        pile_height: float = Form(None),
                        file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        width, height = image.size
        area_m2 = (width * DEFAULT_RESOLUTION) * (height * DEFAULT_RESOLUTION)
    except Exception:
        return {"error": "Invalid JPEG image."}

    return calculate(feedstock_type, area_m2, pile_height)
