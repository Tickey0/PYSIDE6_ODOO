# Guía: dónde ver en Odoo lo que guarda la app

Odoo encendido → navegador → `http://localhost:8069` → usuario `admin`, contraseña `admin`.
Los menús se abren con el ícono de cuadritos ⋮⋮⋮ de arriba a la izquierda.

Cuando en la app se presiona **Guardar** (Alt+G), Odoo crea 4 cosas enlazadas:

| # | Qué | Dónde se ve |
|---|---|---|
| 1 | Pedido de venta `S0000X` | Ventas → Órdenes → Órdenes |
| 2 | Entrega `WH/OUT/0000X` (baja el stock) | Inventario → Operaciones → Traslados |
| 3 | Factura `INV/2026/0000X` | Facturación → Clientes → Facturas |
| 4 | Pago | Facturación → Clientes → Pagos |

## 1. Historial de facturas

**Facturación → Clientes → Facturas**

- La lista muestra número, cliente, fecha, total y estado.
- Estado **Publicado** = confirmada. **Pagado / No pagado** = si ya se cobró.
- Buscador arriba: por número (`INV/2026/00002`) o cliente.
- Clic en una factura para abrirla: se ven las líneas, el IVA y el total.
  - Botones arriba: **Vista previa** e **Imprimir** (PDF).
  - Si salió "No pagado": botón **Registrar pago** → **Crear pago**.
  - El campo de origen muestra el pedido (`S0000X`) del que salió.

## 2. Pedido de venta

**Ventas → Órdenes → Órdenes**

- Abrir el pedido: arriba a la derecha están los botones **Entrega** y **Factura**,
  que llevan a lo que se creó desde ese pedido.

## 3. Entrega (lo que salió de bodega)

**Inventario → Operaciones → Traslados**

- Las de la app empiezan con `WH/OUT/` y quedan en estado **Hecho**.
- El campo **Documento origen** dice de qué pedido salió.

## 4. Stock

- Cantidad actual: **Inventario → Reportes → Existencias**
- Cada entrada y salida: **Inventario → Reportes → Historial de movimientos**
  (cada venta aparece como salida de `WH/Stock` con su `WH/OUT/...`).
- Es el mismo número que muestra la columna **Stock** de la ventana F9 de la app.

## Registros de prueba en la base `odoo20` (13-10-2026)

| Pedido | Entrega | Factura | Quién | Estado |
|---|---|---|---|---|
| S00001 | WH/OUT/00001 | — | Creados a mano en Odoo (12-10) | Borrador |
| S00002 | WH/OUT/00002 | INV/2026/00001 | Prueba de la app | Pagada, **IVA 0** (antes del arreglo de posición fiscal) |
| S00003 | WH/OUT/00004 | INV/2026/00003 | Desde la app, con el código anterior | 152 líneas, **No pagada** y **IVA 0** |
| S00004 | WH/OUT/00003 | INV/2026/00002 | Prueba de la app | Pagada, IVA 15% correcto |

Por S00003, el ARROZ FLOR 2KG quedó con **stock negativo (-96)**: se vendieron 145 con 49 en bodega.
Odoo lo permite; se corrige con un ajuste en **Inventario → Operaciones → Ajustes**.

Para anular una factura de prueba: abrirla → **Nota de crédito**.

## Configuración de Odoo para revisar con el jefe

1. **La empresa está en Estados Unidos.** Con un cliente de Ecuador, Odoo aplica la posición
   fiscal *Foreign Trade* y cambia el 15% por *0% Exports*. La app ahora crea el pedido sin
   posición fiscal para que el IVA sea el del producto, pero lo correcto es configurar la
   empresa en Ecuador (la localización `l10n_ec` ya está instalada).
2. **No hay diario de Efectivo**, solo *Banco*. La app registra el pago en Efectivo si existe
   y si no, en Banco. Se crea en **Facturación → Configuración → Contabilidad → Diarios**,
   tipo *Efectivo*.
3. **Clave API** de la app (vence el 11-11-2026): Odoo → avatar → **Preferencias** →
   **Seguridad de la cuenta** → **Nueva clave API**, y pegarla en el `.env` de la app.
