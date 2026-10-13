"""Guarda una venta en Odoo: pedido -> entrega (baja el stock) -> factura -> pago.

Cada llamada JSON-2 es una transacción aparte. Si una falla a la mitad, lo
anterior ya quedó guardado; por eso el error dice qué alcanzó a hacerse.
"""
from src.models.producto import Producto
from src.services.odoo_client import OdooClient, OdooError

CF_NOMBRE = "CONSUMIDOR FINAL"
CF_IDENTIFICACION = "9999999999999"

ESTADOS_PAGO = {
    "paid": "Pagada",
    "in_payment": "En proceso de pago",
    "partial": "Pagada parcialmente",
    "not_paid": "No pagada",
}


class VentaError(Exception):
    """La venta no se pudo guardar completa."""


class VentaController:
    def __init__(self, odoo: OdooClient):
        self.odoo = odoo

    def _ctx(self, **extra) -> dict:
        return {**self.odoo.context, **extra}

    def _consumidor_final(self) -> int:
        ids = self.odoo.call("res.partner", "search", limit=1,
                             domain=[["vat", "=", CF_IDENTIFICACION]])
        if ids:
            return ids[0]
        return self.odoo.call("res.partner", "create", vals_list=[
            {"name": CF_NOMBRE, "vat": CF_IDENTIFICACION}])[0]

    def _diario_pago(self) -> int:
        """Diario de Efectivo; si la empresa no tiene uno, el de Banco."""
        for tipo in ("cash", "bank"):
            ids = self.odoo.call("account.journal", "search", limit=1, domain=[["type", "=", tipo]])
            if ids:
                return ids[0]
        raise OdooError("No hay un diario de Efectivo ni de Banco en Odoo.")

    def guardar(self, lineas: list[tuple[Producto, float]]) -> dict:
        odoo = self.odoo
        hecho = []
        paso = "buscar el cliente CONSUMIDOR FINAL"
        try:
            cliente = self._consumidor_final()

            paso = "crear el pedido de venta"
            pedido_id = odoo.call("sale.order", "create", vals_list=[{
                "partner_id": cliente,
                # Sin posición fiscal: el IVA es el del producto, el mismo que muestra la factura.
                # (Con la empresa en EE.UU. y el cliente en Ecuador, Odoo aplicaba "Foreign
                # Trade" y cambiaba el 15% por "0% Exports".)
                "fiscal_position_id": False,
                "order_line": [[0, 0, {"product_id": p.id, "product_uom_qty": cantidad,
                                       "price_unit": p.precio}]
                               for p, cantidad in lineas],
            }])[0]
            pedido = odoo.call("sale.order", "read", ids=[pedido_id], fields=["name"])[0]["name"]
            hecho.append(f"pedido {pedido}")

            paso = "confirmar el pedido"
            odoo.call("sale.order", "action_confirm", ids=[pedido_id])
            hecho.append("pedido confirmado")

            paso = "validar la entrega (bajar el stock)"
            entregas = odoo.call("stock.picking", "search_read", fields=["move_ids"], domain=[
                ["sale_id", "=", pedido_id], ["state", "not in", ["done", "cancel"]]])
            for entrega in entregas:
                for mov in odoo.call("stock.move", "read", ids=entrega["move_ids"],
                                     fields=["product_uom_qty"]):
                    odoo.call("stock.move", "write", ids=[mov["id"]],
                              vals={"quantity": mov["product_uom_qty"], "picked": True})
                res = odoo.call("stock.picking", "button_validate", ids=[entrega["id"]],
                                context=self._ctx(skip_backorder=True, skip_sms=True))
                if isinstance(res, dict) and res.get("res_model"):
                    raise OdooError(f"Odoo pidió confirmar algo en la entrega ({res['res_model']}).")
            hecho.append("entrega validada")

            paso = "crear la factura"
            ctx_pedido = self._ctx(active_model="sale.order", active_ids=[pedido_id])
            asistente = odoo.call("sale.advance.payment.inv", "create", context=ctx_pedido,
                                  vals_list=[{"advance_payment_method": "delivered"}])[0]
            odoo.call("sale.advance.payment.inv", "create_invoices", ids=[asistente], context=ctx_pedido)
            factura_id = odoo.call("sale.order", "read", ids=[pedido_id],
                                   fields=["invoice_ids"])[0]["invoice_ids"][-1]

            paso = "confirmar la factura"
            odoo.call("account.move", "action_post", ids=[factura_id])
            hecho.append("factura confirmada")

            paso = "registrar el pago"
            ctx_factura = self._ctx(active_model="account.move", active_ids=[factura_id])
            pago = odoo.call("account.payment.register", "create", context=ctx_factura,
                             vals_list=[{"journal_id": self._diario_pago()}])[0]
            odoo.call("account.payment.register", "action_create_payments", ids=[pago], context=ctx_factura)

            factura = odoo.call("account.move", "read", ids=[factura_id],
                                fields=["name", "amount_total", "payment_state"])[0]
        except OdooError as e:
            ya = f"\n\nYa quedó hecho en Odoo: {', '.join(hecho)}." if hecho else ""
            raise VentaError(f"No se pudo {paso}.\n\n{e}{ya}")

        return {
            "factura": factura["name"],
            "total": factura["amount_total"],
            "estado": ESTADOS_PAGO.get(factura["payment_state"], factura["payment_state"]),
            "pedido": pedido,
        }
