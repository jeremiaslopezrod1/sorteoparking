"""Prueba completa del piloto: cargar Excel + iniciar sorteo."""
import urllib.request
import urllib.error
import json
import uuid

TENANT_ID = "436ae804-2d64-4396-a54c-d316d99dc562"
BASE = "http://127.0.0.1:8000"

# PASO 1: Cargar el Excel real
print("=" * 60)
print("PASO 1: Cargando Excel de elegibles...")
print("=" * 60)

with open(r'c:\Users\El Amor y Yo\Desktop\USorteoParking\SorteoParking_LISTA_ELEGIBLES.xlsx', 'rb') as f:
    file_content = f.read()

boundary = uuid.uuid4().hex
body = (
    b'--' + boundary.encode() + b'\r\n'
    b'Content-Disposition: form-data; name="archivo"; filename="SorteoParking_LISTA_ELEGIBLES.xlsx"\r\n'
    b'Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n' +
    file_content + b'\r\n'
    b'--' + boundary.encode() + b'--\r\n'
)

req = urllib.request.Request(
    f'{BASE}/sorteos/carga-excel',
    data=body,
    headers={
        'Authorization': f'Bearer {TENANT_ID}',
        'Content-Type': f'multipart/form-data; boundary={boundary}'
    }
)

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(f"STATUS: {response.status}")
        print(f"RESPONSE: {json.dumps(data, indent=2)}")
        sorteo_id = data.get("sorteo_id")
except urllib.error.HTTPError as e:
    print(f"ERROR: {e.code} - {e.read().decode()}")
    sorteo_id = None

if not sorteo_id:
    print("No se pudo cargar el Excel. Abortando.")
    exit(1)

# PASO 2: Iniciar sorteo con 5 consejeros de prueba
print()
print("=" * 60)
print(f"PASO 2: Iniciando sorteo {sorteo_id} con 5 consejeros...")
print("=" * 60)

payload = {
    "sorteo_id": sorteo_id,
    "consejeros": [
        {"nombre": "Consejero 1", "whatsapp": "3001234567", "email": "c1@test.com"},
        {"nombre": "Consejero 2", "whatsapp": "3001234568", "email": "c2@test.com"},
        {"nombre": "Consejero 3", "whatsapp": "3001234569", "email": "c3@test.com"},
        {"nombre": "Consejero 4", "whatsapp": "3001234570", "email": "c4@test.com"},
        {"nombre": "Consejero 5", "whatsapp": "3001234571", "email": "c5@test.com"},
    ]
}

req2 = urllib.request.Request(
    f'{BASE}/sorteos/iniciar',
    data=json.dumps(payload).encode(),
    headers={
        'Authorization': f'Bearer {TENANT_ID}',
        'Content-Type': 'application/json'
    }
)

try:
    with urllib.request.urlopen(req2) as response:
        data2 = json.loads(response.read().decode())
        print(f"STATUS: {response.status}")
        print(f"RESPONSE: {json.dumps(data2, indent=2)}")
        
        # Mostrar OTPs de desarrollo
        if "_dev_otps" in data2:
            print()
            print("=" * 60)
            print("OTPs PARA CONFIRMAR (modo desarrollo):")
            print("=" * 60)
            for otp_info in data2["_dev_otps"]:
                print(f"  {otp_info['consejero']}: OTP={otp_info['otp']}  Link={otp_info['link']}")
except urllib.error.HTTPError as e:
    print(f"ERROR: {e.code} - {e.read().decode()}")
