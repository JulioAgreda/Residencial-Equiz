
import tomllib
import psycopg

with open(".streamlit/secrets.toml", "rb") as f:
    config = tomllib.load(f)["postgres_cobros"]

config["port"] = 6543

try:
    with psycopg.connect(**config, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_database();")
            print("CONEXIÓN EXITOSA")
            print(cur.fetchone())

except Exception as e:
    print("ERROR DE CONEXIÓN:")
    print(type(e).__name__)
    print(str(e))
