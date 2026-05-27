import logging
import requests
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db
import models

# Initialize database tables
models.Base.metadata.create_all(bind=engine)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-System Integration API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_URL = "https://jsonplaceholder.typicode.com/users"

@app.get("/fetch-api-data")
def fetch_api_data_endpoint():
    """Fetch user data from the external REST API."""
    return fetch_api_data()

def fetch_api_data():
    logger.info("Fetching data from external API")
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching API data: {e}")
        raise HTTPException(status_code=502, detail="Error communicating with external API")

@app.post("/sync-data")
def sync_data(db: Session = Depends(get_db)):
    """Fetch data from API, transform, and sync it with the local SQLite database."""
    logger.info("Starting data sync process")
    api_data = fetch_api_data()
    
    synced_count = 0
    updated_count = 0
    try:
        for user_data in api_data:
            # Transformation: Extract domain
            email = user_data.get("email", "")
            domain = email.split('@')[-1] if '@' in email else "unknown"
            
            existing_user = db.query(models.User).filter(models.User.id == user_data["id"]).first()
            if not existing_user:
                new_user = models.User(
                    id=user_data["id"],
                    name=user_data["name"],
                    email=email,
                    domain=domain
                )
                db.add(new_user)
                synced_count += 1
            else:
                # Update existing user if needed
                existing_user.name = user_data["name"]
                existing_user.email = email
                existing_user.domain = domain
                updated_count += 1
        db.commit()
        logger.info(f"Sync complete: {synced_count} inserted, {updated_count} updated.")
        return {"message": f"Successfully synced data: {synced_count} inserted, {updated_count} updated."}
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during sync: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during database operation")

@app.get("/get-merged-data")
def get_merged_data(db: Session = Depends(get_db)):
    """Fetch data from API and DB, then merge them."""
    logger.info("Fetching merged data")
    
    # 1. Fetch from Database
    try:
        db_users = db.query(models.User).all()
        db_data = {user.id: {"id": user.id, "name": user.name, "email": user.email, "domain": user.domain, "source": "Database"} for user in db_users}
        logger.info(f"Fetched {len(db_users)} users from database")
    except Exception as e:
        logger.error(f"Error reading from database: {e}")
        raise HTTPException(status_code=500, detail="Error reading from database")

    # 2. Fetch from API
    try:
        api_users = fetch_api_data()
        api_data = {}
        for user in api_users:
            email = user.get("email", "")
            domain = email.split('@')[-1] if '@' in email else "unknown"
            api_data[user["id"]] = {"id": user["id"], "name": user["name"], "email": email, "domain": domain, "source": "API"}
        logger.info(f"Fetched {len(api_users)} users from API")
    except Exception as e:
        logger.error(f"Error fetching from API: {e}")
        raise HTTPException(status_code=502, detail="Error communicating with external API")

    # 3. Merge Datasets
    merged_data_map = {}
    
    all_ids = set(db_data.keys()).union(set(api_data.keys()))
    for user_id in all_ids:
        in_db = user_id in db_data
        in_api = user_id in api_data
        
        # Base user info (prefer DB)
        base_info = db_data[user_id] if in_db else api_data[user_id]
        
        source = "Both" if (in_db and in_api) else ("Database" if in_db else "API")
        
        merged_data_map[user_id] = {
            "id": base_info["id"],
            "name": base_info["name"],
            "email": base_info["email"],
            "domain": base_info["domain"],
            "source": source
        }
    
    # Convert map back to list and sort by ID
    merged_list = list(merged_data_map.values())
    merged_list.sort(key=lambda x: x["id"])
    
    logger.info(f"Returning {len(merged_list)} merged records")
    return {"data": merged_list}
