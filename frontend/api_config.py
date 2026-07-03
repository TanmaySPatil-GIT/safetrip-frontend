import os

# Centralized API Base URL for the FastAPI backend
API_BASE_URL = os.getenv("BACKEND_URL", "https://safetrip-backend-aryg.onrender.com")

# Centralized Reflex API server URL (for state sync)
REFLEX_API_URL = os.getenv("API_URL", "https://safetrip-backend-aryg.onrender.com")
