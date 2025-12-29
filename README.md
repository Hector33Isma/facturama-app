# Factura Global CFDI 4.0 (FastAPI + Facturama Sandbox)

Proyecto de referencia para timbrar Factura Global CFDI 4.0 con Facturama (sandbox), FastAPI y Jinja2. Incluye carga y validación de Excel, control de folios por serie, historial y descarga de PDF/XML.

## Requisitos
- Python 3.11+
- Acceso a credenciales de Facturama sandbox (`FACTURAMA_USER`/`FACTURAMA_PASSWORD`)

## Configuración rápida (Windows PowerShell / Linux/macOS)
```powershell
python -m venv .venv
.\.venv\Scripts\activate   # en Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env     # en Linux/macOS: cp .env.example .env
```
Edita `.env` con tus credenciales y rutas deseadas.

## Base de datos y migraciones
```powershell
alembic upgrade head
```
Usa SQLite (`app.db`) por defecto. Ajusta `DATABASE_URL` en `.env` para otra base.

## Ejecutar
```powershell
uvicorn app.main:app --reload
```
Abre http://127.0.0.1:8000 para la UI.

## Funcionalidad principal
- **Timbrar Factura Global:** carga un Excel (`sample.xlsx` de ejemplo), valida columnas y totales, genera CFDI usando Facturama. En caso de errores crea un Excel con columna `Errores`.
- **Series (CRUD):** alta/edita/activa-inactiva series y muestra último folio por serie.
- **Historial:** consulta facturas guardadas, descarga PDF/XML si existen.
- **Consultar CFDIs:** consulta emitidos en Facturama por rango de fechas.

## Estructura
- `app/core`: configuración, logging, conexión DB.
- `app/models`: modelos SQLAlchemy (series, folios, invoices, items).
- `app/services`: Excel/validación, folios, cliente Facturama (httpx), orquestador de timbrado.
- `app/routers/ui.py`: rutas FastAPI con vistas Jinja2.
- `app/templates`: Jinja2 + Bootstrap 5.
- `storage/facturas`: PDFs/XMLs y uploads.

## Plantilla Excel
`sample.xlsx` incluye todas las columnas requeridas. Cada fila es un concepto y el campo **Pedido** se usa como `IdentificationNumber`. Un archivo = una factura global.

## Notas
- El cliente Facturama usa autenticación básica y timeout de 30s con manejo de errores amigable.
- Las descargas de PDF/XML usan endpoints `.../file/{fmt}`; si sandbox no devuelve contenido, se registra warning.
- Se usa `Decimal` para importes y tolerancia de 0.02 para validar `Subtotal + IVA ≈ Total`.
