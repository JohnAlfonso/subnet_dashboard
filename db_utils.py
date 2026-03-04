import requests
from typing import Dict
import logging

# Use the backend API instead of direct database connections
API_BACKEND_URL = "http://localhost:9900"

logger = logging.getLogger(__name__)

def get_count_from_api(endpoint: str, description: str = "") -> int:
    """
    Get count from backend API.
    """
    try:
        response = requests.get(f"{API_BACKEND_URL}{endpoint}", timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('count', 0)
    except Exception as e:
        logger.error(f"Error getting count from API {description}: {e}")
        return 0
   
def count_raw_company():
    return get_count_from_api("/api/counts/raw-company", "count_raw_company")

def count_scored_company():
    return get_count_from_api("/api/counts/scored-company", "count_scored_company")

def count_useful_company():
    return get_count_from_api("/api/counts/useful-company", "count_useful_company")

def count_person_company():
    return get_count_from_api("/api/counts/person-company", "count_person_company")

def count_true_list():
    return get_count_from_api("/api/counts/true-list", "count_true_list")

def count_checked_company():
    return get_count_from_api("/api/counts/checked-company", "count_checked_company")

def count_generated_leads():
    return get_count_from_api("/api/counts/generated-leads", "count_generated_leads")

def count_valued_leads():
    return get_count_from_api("/api/counts/valued-leads", "count_valued_leads")

def count_connection_pool():
    return get_count_from_api("/api/counts/connection-pool", "count_connection_pool")

def max_connection_pool():
    return get_count_from_api("/api/counts/max-connections", "max_connection_pool")