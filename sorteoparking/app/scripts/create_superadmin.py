import argparse
import getpass
import secrets
import sys
from pathlib import Path
from uuid import uuid4

from argon2 import PasswordHasher

# Configuración Argon2id según §13 del SDD
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4
)

def _imprimir_banner() -> None:
    print("\n" + "=" * 60)
    print("  SorteoParking - Inicialización de Seguridad SUPER_ADMIN")
    print("  SDD §13 - T-107")
    print("=" * 60 + "\n")

def _actualizar_env(user: str, password_hash: str, token: str) -> None:
    """Escribe o actualiza las variables en el archivo .env."""
    env_path = Path(".env")
    lines = []
    
    keys_to_update = {
        "SUPER_ADMIN_USER": user,
        "SUPER_ADMIN_PASSWORD_HASH": password_hash,
        "SUPER_ADMIN_TOKEN": token
    }
    
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key = line.split("=")[0].strip()
                    if key in keys_to_update:
                        continue
                lines.append(line)
    
    for key, value in keys_to_update.items():
        lines.append(f"{key}={value}\n")
    
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    print(f"  [OK] Archivo .env actualizado en: {env_path.absolute()}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Configura el acceso seguro del SUPER_ADMIN.")
    parser.add_argument("--env-only", action="store_true", help="Solo genera valores sin guardar en BD (v1.0 default).")
    args = parser.parse_args()

    _imprimir_banner()

    print("  Configuración de credenciales de administrador")
    user = input("  Usuario [admin]: ").strip() or "admin"
    
    while True:
        password = getpass.getpass("  Nueva contraseña: ")
        if len(password) < 8:
            print("  Error: La contraseña debe tener al menos 8 caracteres")
            continue
        confirm = getpass.getpass("  Confirmar contraseña: ")
        
        if password == confirm:
            break
        print("  [ERROR] Las contraseñas no coinciden. Intente de nuevo.")

    print("\n  Generando hash Argon2id y token...")
    password_hash = ph.hash(password)
    token = str(uuid4())

    _actualizar_env(user, password_hash, token)

    print("\n" + "=" * 60)
    print("  [EXITO] Configuración completada.")
    print("  - Los secretos han sido guardados en el archivo .env")
    print("  - No comparta el archivo .env con nadie.")
    print("  - Reinicie el servidor para aplicar los cambios.")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
