import os

import requests
from dotenv import load_dotenv


load_dotenv()


MOBSF_URL = os.getenv("MOBSF_URL", "http://localhost:8001").rstrip("/")


def check_mobsf_health() -> dict:
    try:
        response = requests.get(
            MOBSF_URL,
            timeout=10,
            allow_redirects=True,
        )

        return {
            "mobsf_url": MOBSF_URL,
            "status_code": response.status_code,
            "final_url": response.url,
            "available": response.status_code < 500,
        }

    except requests.RequestException as exc:
        return {
            "mobsf_url": MOBSF_URL,
            "status_code": None,
            "final_url": None,
            "available": False,
            "error": str(exc),
        }