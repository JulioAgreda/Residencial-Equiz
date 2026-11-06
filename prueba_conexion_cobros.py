
import streamlit as st
import psycopg

st.title("Prueba de conexión PostgreSQL")
st.caption("Residencial Equise — Módulo de cobros")

try:
    config = dict(st.secrets["postgres_cobros"])

    with psycopg.connect(
        **config,
        connect_timeout=10,
        autocommit=True
    ) as conn:

        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    current_database(),
                    current_user,
                    session_user,
                    has_schema_privilege(
                        current_user,
                        'cobros_private',
                        'USAGE'
                    ),
                    has_schema_privilege(
                        current_user,
                        'cobros_private',
                        'CREATE'
                    ),
                    has_table_privilege(
                        current_user,
                        'public.apartamentos',
                        'SELECT'
                    )
            """)

            resultado = cur.fetchone()

    st.success("Conexión PostgreSQL establecida.")

    st.write("Base de datos:", resultado[0])
    st.write("Usuario conectado:", resultado[1])
    st.write("Usuario de sesión:", resultado[2])
    st.write("Acceso USAGE al esquema:", resultado[3])
    st.write("Permiso CREATE:", resultado[4])
    st.write("Acceso SELECT a apartamentos:", resultado[5])

    if resultado[1] != "equise_cobros_app":
        st.error("El usuario conectado no es el esperado.")

    elif resultado[3] is not True:
        st.error("No tiene acceso USAGE al esquema privado.")

    elif resultado[4] is not False:
        st.error("El usuario tiene permisos CREATE no esperados.")

    elif resultado[5] is not False:
        st.error("ATENCIÓN: tiene acceso directo a apartamentos.")

    else:
        st.success("Las verificaciones iniciales son satisfactorias.")

except Exception as e:
    st.error("No se pudo completar la prueba de conexión.")
    st.code(f"{type(e).__name__}: {e}")
