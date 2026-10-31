
"""
MEDIRED - Configuración del backend.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_USER = os.getenv("MEDIRED_DB_USER", "postgres")
DB_PASSWORD = os.getenv("MEDIRED_DB_PASSWORD", "postgres")
DB_HOST = os.getenv("MEDIRED_DB_HOST", "localhost")
DB_PORT = os.getenv("MEDIRED_DB_PORT", "5432")
DB_NAME = os.getenv("MEDIRED_DB_NAME", "medired")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

DB_SCHEMA = "medired"

CORS_ORIGINS = os.getenv(
    "MEDIRED_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8000,http://127.0.0.1:8000"
).split(",")

# Clave para firmar las sesiones. En .env agrega una propia y larga, p. ej.:
#   MEDIRED_SECRET_KEY=<cadena aleatoria de 40+ caracteres>
# Si no existe se usa una de desarrollo (sirve para el proyecto académico,
# pero cualquiera que conozca esa clave podría fabricar sesiones).
SECRET_KEY = os.getenv("MEDIRED_SECRET_KEY", "medired-clave-de-desarrollo-cambiar")
TOKEN_HORAS = int(os.getenv("MEDIRED_TOKEN_HORAS", "12"))
