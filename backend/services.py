import csv
import time
import requests
from io import StringIO
from fastapi import HTTPException
from logger import get_logger
import models

logger = get_logger("integration_service")

API_URL = "https://jsonplaceholder.typicode.com/users"

def fetch_api_data_with_retry(max_retries=3):
    # fetch data
    backoff = 1
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching API data, attempt {attempt + 1}")
            response = requests.get(API_URL, timeout=10)
            response.raise_for_status()
            logger.info("Successfully fetched data from API")
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"API fetch failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {backoff} seconds...")
                time.sleep(backoff)
                backoff *= 2
            else:
                logger.error("Max retries reached. API is unavailable.")
                raise HTTPException(status_code=502, detail="External API unavailable after retries")

def transform_user_data(user_data: dict) -> dict:
    # transform data
    email = user_data.get("email", "")
    domain = email.split('@')[-1] if '@' in email else "unknown"
    return {
        "id": int(user_data["id"]),
        "name": user_data.get("name", "Unknown"),
        "email": email,
        "domain": domain
    }

def upsert_users(db, users_list):
    # insert update users
    inserted = 0
    updated = 0
    
    try:
        for raw_user in users_list:
            user = transform_user_data(raw_user)
            
            existing = db.query(models.User).filter(models.User.id == user["id"]).first()
            if not existing:
                new_user = models.User(**user)
                db.add(new_user)
                inserted += 1
            else:
                existing.name = user["name"]
                existing.email = user["email"]
                existing.domain = user["domain"]
                updated += 1
                
        db.commit()
        logger.info(f"Upsert complete: {inserted} inserted, {updated} updated.")
        return inserted, updated
    except Exception as e:
        db.rollback()
        logger.error(f"Database upsert failed: {e}")
        raise HTTPException(status_code=500, detail="Database operation failed")

def process_csv_upload(db, file_content: str):
    # parse csv
    logger.info("Processing CSV upload content")
    reader = csv.DictReader(StringIO(file_content))
    users = []
    
    for row in reader:
        if "id" in row and "name" in row and "email" in row:
            users.append(row)
        else:
            logger.warning(f"Skipping invalid CSV row: {row}")
            
    if not users:
        logger.warning("No valid rows found in CSV")
        return 0, 0
        
    logger.info(f"Parsed {len(users)} valid rows from CSV")
    return upsert_users(db, users)
