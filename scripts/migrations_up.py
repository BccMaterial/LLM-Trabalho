import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
ADMIN_API_TOKEN = os.environ["ADMIN_API_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]
PSYCOPG_DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
MAX_ATTEMPTS = 30
RETRY_DELAY_SECONDS = 2


def wait_for_database() -> None:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with psycopg.connect(PSYCOPG_DATABASE_URL, connect_timeout=2):
                print("Banco de dados disponível.")
                return
        except psycopg.OperationalError:
            if attempt == MAX_ATTEMPTS:
                break
            print(f"Aguardando o banco subir ({attempt}/{MAX_ATTEMPTS})...")
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError("O banco de dados não ficou disponível.")


def apply_migrations() -> None:
    request = Request(
        f"{API_BASE_URL}/api/migrations",
        headers={"Authorization": f"Bearer {ADMIN_API_TOKEN}"},
        method="POST",
    )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urlopen(request) as response:
                result = json.loads(response.read().decode())
            print(f"Migrations aplicadas: {json.dumps(result, ensure_ascii=False)}")
            return
        except HTTPError as error:
            if error.code not in {502, 503, 504}:
                detail = error.read().decode()
                raise RuntimeError(
                    f"Não foi possível aplicar migrations ({error.code}): {detail}"
                ) from error
        except (URLError, ConnectionResetError, TimeoutError):
            pass

        if attempt < MAX_ATTEMPTS:
            print(f"Aguardando a API subir ({attempt}/{MAX_ATTEMPTS})...")
            time.sleep(RETRY_DELAY_SECONDS)

    raise RuntimeError("A API não ficou disponível para aplicar as migrations.")


if __name__ == "__main__":
    wait_for_database()
    apply_migrations()
