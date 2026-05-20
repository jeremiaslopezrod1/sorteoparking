from fastapi import Request
from starlette.middleware.base import (
    BaseHTTPMiddleware
)

SECURITY_HEADERS = {
    "Strict-Transport-Security": 
        "max-age=31536000; includeSubDomains",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": 
        "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        # TODO: Replace 'unsafe-inline' with nonce-based CSP for XSS protection
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    ),
    "Permissions-Policy": 
        "geolocation=(), microphone=(), camera=()",
}

PUBLIC_CACHE_HEADERS = {
    "Cache-Control": 
        "public, max-age=300, "
        "stale-while-revalidate=60"
}

PRIVATE_CACHE_HEADERS = {
    "Cache-Control": 
        "no-store, no-cache, must-revalidate"
}

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Aplicar headers de seguridad a todas
        # las respuestas
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # Cache diferenciado por tipo de ruta
        if request.url.path.startswith("/p/"):
            # Vista pública — cacheable
            for h, v in PUBLIC_CACHE_HEADERS.items():
                response.headers[h] = v
        else:
            # Panel admin y API — nunca cachear
            for h, v in PRIVATE_CACHE_HEADERS.items():
                response.headers[h] = v
        
        return response
