# odoo_pyside6

Pantalla de factura en PySide6 que consulta productos e inventario de Odoo 20
con la API externa **JSON-2**.

## Ejecutar

Con Odoo arrancado (en Ubuntu: `odoo -c odoo.conf`), en PowerShell:

```
cd C:\DOCKER\odoo\odoo_pyside6
.venv\Scripts\python main.py
```

Login: `admin` / `admin`.

Para conectarse a otro Odoo, con su propio archivo de configuración:

```
.venv\Scripts\python main.py --env .env.odoo19
```

## Teclas en la factura

| Tecla | Qué hace |
|---|---|
| Enter | Busca lo escrito en "Código de Barras" (código exacto, o por nombre) y salta a una fila nueva en blanco |
| `3.CODIGO` + Enter | Igual, pero con cantidad 3 (sirve con escáner: escribir `3.` y escanear) |
| F9 | Abre el Maestro de Artículos (inventario) |
| ↑ ↓ | Cambia de línea |
| Shift+F6 | Vacía la línea donde está el cursor (no la quita): queda en blanco para escribir otro código |
| Ctrl+F | Buscar una línea dentro de la factura (código o descripción). Enter = la siguiente, Esc = volver |
| Ctrl+G | Guardar |

Solo aparecen productos de tipo Bienes, que se venden y con "Disponible en PdV".

## Guardar 💾

Crea en Odoo, en este orden: pedido de venta (Ventas) → entrega validada, baja el
stock (Inventario) → factura confirmada (Facturación) → pago en efectivo.
Cliente: CONSUMIDOR FINAL (9999999999999); se crea solo la primera vez.

Son varias llamadas JSON-2 seguidas: si una falla, el mensaje dice qué alcanzó a
quedar hecho en Odoo para terminarlo a mano.

Guía paso a paso para revisarlo en Odoo: [docs/guia_odoo.md](docs/guia_odoo.md).
Guía del código (qué archivo llama a cuál y qué JSON viaja a Odoo): [docs/guia_codigo.md](docs/guia_codigo.md).

| Ver en Odoo | Menú |
|---|---|
| Facturas | Facturación → Clientes → Facturas |
| Pedidos | Ventas → Órdenes → Órdenes |
| Entregas | Inventario → Operaciones → Traslados |
| Stock | Inventario → Reportes → Existencias |

En el Maestro de Artículos: Enter en "Buscar" busca (`%` es comodín: `CHOCOL%`),
flechas para elegir, Enter acepta, Esc cancela.

## Configuración

Copiar `.env.example` a `.env` y poner la clave API
(Odoo → avatar → Preferencias → Seguridad → Agregar clave API).

Un archivo por cada Odoo; se elige con `--env` (sin `--env` se usa `.env`):

| Archivo | Odoo | ODOO_URL | ODOO_DB |
|---|---|---|---|
| `.env` | 20 | `http://127.0.0.1:8069` | `odoo20` |
| `.env.odoo19` | 19 + localización Ecuador | `http://127.0.0.1:8019` | `odoo19_ec` |

Ningún `.env*` se sube a git (salvo `.env.example`): tienen la clave API.

Usar `127.0.0.1` y no `localhost` en `ODOO_URL`: en Windows `localhost` intenta
IPv6 primero y cada llamada tarda 15 segundos.

## Datos de prueba

```
.venv\Scripts\python -m scripts.cargar_inventario
.venv\Scripts\python -m scripts.cargar_inventario --env .env.odoo19
```

Ejemplos de consultas a la API (solo leen): `python -m scripts.ejemplos_api --env .env.odoo19`.

Crea 8 productos con stock (no duplica si ya existen). Con la localización de
Ecuador usa los IVA del SRI para bienes: 15% (411, B) y 0% (415, B).

## Estructura (MVC)

```
main.py                              arranque: login y ventana
src/services/odoo_client.py          conexión JSON-2 (POST /json/2/<modelo>/<método>)
src/models/producto.py               modelo Pydantic de product.product
src/controllers/producto_controller.py   búsquedas de productos e IVA
src/controllers/venta_controller.py  Guardar: pedido, entrega, factura y pago
src/views/login_view.py              login
src/views/factura_datatable_view.py  pantalla de factura (contenedor) con Guardar
src/views/detalle_factura.py         tabla de líneas con DataTable (pyside6-datatable-widget)
src/views/factura_view.py            versión anterior (grilla de 10 filas), respaldo
src/views/articulos_dialog.py        Maestro de Artículos (F9)
scripts/cargar_inventario.py         carga de productos de prueba
```

Para volver a la versión anterior de la factura, ver el comentario al inicio de `main.py`.

`pyside6-datatable-widget` tiene licencia **GPLv3**: si la app se distribuye a
clientes, revisar qué implica antes.
