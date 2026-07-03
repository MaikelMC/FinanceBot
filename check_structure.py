import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("=== VERIFICACIÓN DE TODOS LOS MÓDULOS ===")

try:
    import config
    print("✓ config.py - Cargado correctamente")
    print("  TELEGRAM_BOT_TOKEN: " + (config.TELEGRAM_BOT_TOKEN[:20] + "..." if config.TELEGRAM_BOT_TOKEN else "No configurado"))
except Exception as e:
    print("✗ config.py - Error:", str(e))

try:
    import database
    print("✓ database.py - Cargado correctamente")
    database.crear_tablas()
    print("  Tablas de base de datos creadas/verificadas")
except Exception as e:
    print("✗ database.py - Error:", str(e))

try:
    import knowledge
    print("✓ knowledge.py - Cargado correctamente")
except Exception as e:
    print("✗ knowledge.py - Error:", str(e))

try:
    import handlers
    print("✓ handlers.py - Cargado correctamente")
except Exception as e:
    print("✗ handlers.py - Error:", str(e))

print("\n=== VERIFICACIÓN DE ESTRUCTURA DE ARCHIVOS ===")

files_needed = [
    "config.py",
    "database.py", 
    "knowledge.py",
    "handlers.py",
    "main.py",
    ".env"
]

for file in files_needed:
    if os.path.exists(file):
        print(f"✓ {file} - Present")
    else:
        print(f"✗ {file} - FALTANTE")

print("\n=== DIRECTORIOS NECESARIOS ===")
directories_needed = ["data", "prompts"]
for dir_name in directories_needed:
    if os.path.exists(dir_name) and os.path.isdir(dir_name):
        print(f"✓ {dir_name}/ - Present")
    else:
        print(f"✗ {dir_name}/ - FALTANTE")

print("\n=== PROCESOS DE VERIFICACIÓN ===")
print("Prueba de conexión a base de datos SQLite...")
try:
    conn = sqlite3.connect("data/finanzas.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"✓ Base de datos conectada, tablas: {[t[0] for t in tables]}")
    conn.close()
except Exception as e:
    print("✗ Error de conexión a base de datos:", str(e))
    import traceback
    traceback.print_exc()