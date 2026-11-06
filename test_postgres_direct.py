import psycopg
import tomllib

with open(".streamlit/secrets.toml", "rb") as f:
    config = tomllib.load(f)["postgres_cobros"]

try:
    with psycopg.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["dbname"],
        user=config["user"],
        password=config["password"],
        sslmode="require",
        connect_timeout=15
    ) as conn:

        with conn.cursor() as cur:
            cur.execute("""
                SELECT current_user, current_database();
            """)
            print("CONEXION EXITOSA:", cur.fetchone())

except Exception as e:
    print("ERROR:", type(e).__name__)
    print(str(e))