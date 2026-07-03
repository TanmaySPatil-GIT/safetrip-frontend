import os
import sys
import reflex as rx

sys.path.append(os.path.join(os.path.dirname(__file__), "frontend"))
try:
    from api_config import REFLEX_API_URL
except ImportError:
    REFLEX_API_URL = "https://safetrip-backend-aryg.onrender.com"

config = rx.Config(
    app_name="frontend",
    api_url=REFLEX_API_URL,
    cors_allowed_origins=["*"],
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)