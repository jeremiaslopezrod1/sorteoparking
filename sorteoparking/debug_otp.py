"""Debug OTP hash matching."""
import sys; sys.path.insert(0, '.')
from app.core.config import otp_config
from app.services.otp_service import hashear_otp, generar_otp_numerico_seis_digitos

otp = generar_otp_numerico_seis_digitos()
h = hashear_otp(otp)

print(f'Pepper: "{otp_config.pepper}"')
print(f'OTP: {otp}')
print(f'Hash: {h}')

# Now test what the server would compute
h2 = hashear_otp(otp)
print(f'Hash again: {h2}')
print(f'Match: {h == h2}')
