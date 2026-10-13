from src.models.producto import Producto
from src.services.odoo_client import OdooClient

# Solo bienes (no servicios) que se pueden vender y están en el Punto de Venta
DOMINIO_BASE = [["sale_ok", "=", True], ["type", "=", "consu"], ["available_in_pos", "=", True]]


class ProductoController:
    """Consultas de productos e inventario a Odoo para la pantalla de factura."""

    def __init__(self, odoo: OdooClient):
        self.odoo = odoo
        self._tasas = None  # {id_impuesto: porcentaje}

    def _porcentaje_iva(self, impuestos: list[int]) -> float:
        if self._tasas is None:
            filas = self.odoo.call("account.tax", "search_read",
                                   domain=[["amount_type", "=", "percent"]],
                                   fields=["amount"])
            self._tasas = {f["id"]: f["amount"] for f in filas}
        return sum(self._tasas.get(i, 0.0) for i in impuestos)

    def _leer(self, domain: list, limit: int) -> list[Producto]:  # 🟠 CONSULTA 5: agrega DOMINIO_BASE
        filas = self.odoo.call("product.product", "search_read",  # 🟠 CONSULTA 5: pide a Odoo
                               domain=DOMINIO_BASE + domain,
                               fields=list(Producto.CAMPOS),
                               limit=limit, order="name",
                               # sin el "[referencia]" delante del nombre
                               context={**self.odoo.context, "display_default_code": False})
        productos = [Producto.model_validate(f) for f in filas]
        for p in productos:
            p.iva = self._porcentaje_iva(p.impuestos)
        return productos

    def por_codigo(self, codigo: str) -> list[Producto]:  # 🟠 CONSULTA 4: filtro por código
        """Coincidencia exacta por codigo de barras o referencia interna."""
        return self._leer(["|", ["barcode", "=", codigo], ["default_code", "=", codigo]], limit=2)

    def buscar(self, patron: str, limit: int = 200) -> list[Producto]:
        """Busca por nombre, codigo de barras o referencia.

        Si el patron trae % se usa como comodin (CHOCOL% = empieza con CHOCOL);
        si no, busca que contenga el texto.
        """
        op = "=ilike" if "%" in patron else "ilike"
        return self._leer(["|", "|", ["name", op, patron], ["barcode", op, patron],
                           ["default_code", op, patron]], limit=limit)
