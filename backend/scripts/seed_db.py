import asyncio
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.db.indexes import create_indexes
from app.services.data_service import DataService
from app.services.hotspot_service import HotspotService

async def main():
    await connect_to_mongo()
    await create_indexes()
    
    # 1. Check observations count
    collection = DataService._clean_nan
    csv_path = backend_dir / "data" / "processed" / "ocean_water_clean.csv"
    res = await DataService.import_data(str(csv_path))
    print("Seed observations result:", res)
    
    # 2. Run initial hotspot detection
    print("Running DBSCAN hotspot detection...")
    hotspot_res = await HotspotService.detect_hotspots()
    print("Hotspot detection result:", hotspot_res)
    
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
