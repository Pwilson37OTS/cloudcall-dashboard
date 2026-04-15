import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

CLOUDCALL_API_URL = os.getenv("CLOUDCALL_API_URL", "https://apio1.cloudcall.com")
CLOUDCALL_AUTH_URL = os.getenv("CLOUDCALL_AUTH_URL", "https://auth.cloudcall.com")
CLOUDCALL_API_TOKEN = os.getenv("CLOUDCALL_API_TOKEN", "")
CLOUDCALL_REFRESH_TOKEN = os.getenv("CLOUDCALL_REFRESH_TOKEN", "")
CLOUDCALL_CLIENT_ID = os.getenv("CLOUDCALL_CLIENT_ID", "o1-public-api")

REPORT_ENDPOINT = f"{CLOUDCALL_API_URL}/report/data"
TOKEN_ENDPOINT = f"{CLOUDCALL_AUTH_URL}/connect/token"

CACHE_TTL = 300  # 5 minutes

# Path to .env file for updating tokens on refresh
ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
