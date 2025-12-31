# Factura Global CFDI 4.0 (FastAPI + Facturama Sandbox)

Proyecto de referencia para timbrar Factura Global CFDI 4.0 con Facturama (sandbox), FastAPI y Jinja2. Incluye autenticación por sesión, roles, validación de Excel, control de folios por serie, historial y descargas de PDF/XML/ZIP.

## Requisitos
- Python 3.11+
- Credenciales Facturama sandbox (`FACTURAMA_USER` / `FACTURAMA_PASSWORD`)

## Configuración rápida (Windows PowerShell / Linux/macOS)
```powershell
python -m venv .venv
.\.venv\Scripts\activate   # en Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env     # en Linux/macOS: cp .env.example .env
```
Edita `.env` con credenciales Facturama y define `SECRET_KEY`.

## Base de datos y migraciones
```powershell
alembic upgrade head
```
Usa SQLite (`app.db`) por defecto. Ajusta `DATABASE_URL` si usas otra base.

## Crear primer usuario admin (obligatorio)
```powershell
python -m app.create_admin
```
El comando:
- verifica si ya existen usuarios (si hay, aborta);
- solicita username/email/password por consola;
- guarda el usuario con rol `admin` e `is_active=true`.

## Ejecutar
```powershell
uvicorn app.main:app --reload
```
UI: http://127.0.0.1:8000  
Rutas abiertas: `/login`, `/static/*`. El resto exige sesión. Rol `admin` requerido para `/users*`.

## Funcionalidad principal
- **Timbrar Factura Global:** carga Excel (`sample.xlsx` de ejemplo), valida columnas y totales, genera CFDI (POST /3/cfdis). Si hay errores, genera Excel con columna `Errores`.
- **Control de folios por serie:** solo se incrementa folio cuando Facturama regresa éxito; fallos no consumen folio.
- **Series (CRUD + último folio editable):** alta/edita/activa-inactiva series y permite ajustar `last_folio` manualmente.
- **Historial:** consulta facturas guardadas, descarga PDF/XML/ZIP si existen.
- **Consultar CFDIs:** consume API de consulta y muestra resultados con bloque de debug en caso de error.
- **Usuarios y roles:** login con bcrypt, roles `admin`/`user`, edición de datos, reset de password, activar/desactivar usuarios. CSRF en formularios y rate limit de login básico.
- **Auditoría:** guarda acciones clave (login ok/fail, create/update/reset/toggle usuario) con ip/user_agent.

## Estructura relevante
- `app/core`: configuración, logging, sesión/CSRF, seguridad.
- `app/models`: SQLAlchemy (series, folios, invoices, items, users, audit_logs).
- `app/services`: Excel/validación, folios, cliente Facturama (httpx), timbrado, auditoría.
- `app/routers`: UI protegida (`ui.py`), auth (`auth.py`), admin usuarios (`users.py`).
- `app/templates`: Jinja2 + Bootstrap 5, incluye login y administración de usuarios.
- `storage/facturas`: PDFs/XMLs/ZIPs y uploads.

## Plantilla Excel
`sample.xlsx` incluye todas las columnas requeridas. Cada fila es un concepto y el campo **Pedido** se usa como `IdentificationNumber`. Un archivo = una factura global.

## Notas
- Cliente Facturama usa autenticación básica, timeout 30s y manejo de errores; descargas de PDF/XML/ZIP usan endpoints Web API (`/api/Cfdi/...` y `/cfdi/zip`).
- Se usa `Decimal` y tolerancia de 0.02 en `Subtotal + IVA ≈ Total`.
- Si Facturama falla, se muestran mensajes amigables en UI y detalle técnico en el bloque “Detalles API” o Excel de errores.
