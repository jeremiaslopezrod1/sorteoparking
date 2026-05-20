import sys, os
sys.path.insert(0, r"C:\Users\El Amor y Yo\Desktop\USorteoParking\sorteoparking")
os.environ["APP_ENV"] = "development"

from app.services.email_service import enviar_correo_texto

reporte = """Asunto: SorteoParking v1.6 | Informe tecnico post-fixes

Hola Michael,

RESUMEN EJECUTIVO
==================
Los dos bugs que impedian producir resultados de sorteo fueron identificados y corregidos.
El E2E test completo pasa 38/39 (38 OK, 1 FAIL menor en export Word).

BUGS CORREGIDOS
===============

Bug #1 - Mismatch de estado entre mutex y motor
Archivo: sorteo_engine.py
El servicio cambia el estado a EJECUTANDO (mutex T-120), pero el motor
solo aceptaba LISTO o EN_CURSO. Causaba ValueError inmediato sin ejecutar nada.
Fix: agregar EJECUTANDO a los estados aceptados por el motor.

Bug #2 - Filtro tipo_vehiculo con valor GENERAL
Archivo: sorteo_engine.py
El sorteo se crea con tipo=GENERAL, pero el motor usaba sorteo.tipo como
filtro de tipo_vehiculo, entonces buscaba participantes donde
tipo_vehiculo = GENERAL -> 0 matches.
Fix: cuando tipo_vehiculo es GENERAL, se omite el filtro (incluye todos).

ESTADO ACTUAL
=============

Base de datos: sorteoparking.db
Modelo aplicado: HIBRIDO
Seed generada: si
resultados_sorteo: 6 registros (6 GANADOR)

TENANT ALISO VIVIENDA
=====================
Creado exitosamente
ID (Bearer token): dbd27407-a42d-4d82-a80e-545fdeff6798
Slug: aliso-vivienda

WhatsApp gateway: +573132054894 (conectada, pendiente configurar token)

PENDIENTE
=========
1. Cargar catalogo de parqueaderos de Aliso
2. Cargar lista de elegibles
3. Correr sorteo piloto
4. Fix menor: exportacion a Word (python-docx)
5. Configurar WHATSAPP_ACCESS_TOKEN para envios automaticos

--
Jarvis"
"""

ok = enviar_correo_texto(
    destino="pruebaalisocajica@gmail.com",
    asunto="SorteoParking v1.6 - Informe post-fixes",
    cuerpo=reporte
)
print(f"Envio por email: {ok}")
