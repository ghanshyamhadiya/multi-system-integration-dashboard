from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, get_db
import models
from logger import get_logger, get_recent_logs
from services import fetch_api_data_with_retry, upsert_users, process_csv_upload

# Initialize database tables
models.Base.metadata.create_all(bind=engine)

logger = get_logger("main")
logger.info("Starting Multi-System Integration API")

app = FastAPI(title="Multi-System Integration API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/fetch-api-data")
def fetch_api_data_endpoint():
    """Fetch user data from the external REST API."""
    return fetch_api_data_with_retry()

@app.post("/sync-data")
def sync_data(db: Session = Depends(get_db)):
    """Fetch data from API, transform, and sync it with the local SQLite database."""
    logger.info("Sync requested via API")
    api_data = fetch_api_data_with_retry()
    inserted, updated = upsert_users(db, api_data)
    return {"message": f"Successfully synced data: {inserted} inserted, {updated} updated."}

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a CSV file for integration."""
    logger.info(f"CSV upload requested: {file.filename}")
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be CSV.")
    
    try:
        content = await file.read()
        decoded = content.decode('utf-8')
        inserted, updated = process_csv_upload(db, decoded)
        return {
            "message": f"CSV processed: {inserted} inserted, {updated} updated.",
            "records_inserted": inserted,
            "records_updated": updated
        }
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to process CSV file.")

@app.get("/logs")
def get_logs():
    """Return the recent system logs."""
    return {"logs": get_recent_logs()}

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
        api_users = fetch_api_data_with_retry()
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
