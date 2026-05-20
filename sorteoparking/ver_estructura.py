import sqlite3

conn = sqlite3.connect('sorteoparking.db')
cursor = conn.cursor()

# Ver columnas de la tabla sorteos
cursor.execute("PRAGMA table_info(sorteos)")
print("=== Columnas de tabla 'sorteos' ===")
for col in cursor.fetchall():
    print(f"  {col[1]} ({col[2]})")

# Ver columnas de participantes
cursor.execute("PRAGMA table_info(participantes)")
print("\n=== Columnas de tabla 'participantes' ===")
for col in cursor.fetchall():
    print(f"  {col[1]} ({col[2]})")

# Ver columnas de resultados_sorteo
cursor.execute("PRAGMA table_info(resultados_sorteo)")
print("\n=== Columnas de tabla 'resultados_sorteo' ===")
for col in cursor.fetchall():
    print(f"  {col[1]} ({col[2]})")

# Ver columnas de tenants
cursor.execute("PRAGMA table_info(tenants)")
print("\n=== Columnas de tabla 'tenants' ===")
for col in cursor.fetchall():
    print(f"  {col[1]} ({col[2]})")

conn.close()
