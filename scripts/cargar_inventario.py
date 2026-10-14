"""Carga 8 productos de prueba con stock en Odoo usando JSON-2.

Se puede correr varias veces: si un producto ya existe (misma referencia) no lo
duplica, solo le ajusta el stock si no coincide.
Uso:  python -m scripts.cargar_inventario
      python -m scripts.cargar_inventario --env .env.odoo19   (otro Odoo)
"""
from src.services.odoo_client import OdooClient, archivo_env

# (nombre, referencia, código de barras, precio sin IVA, lleva IVA 15%, stock)
PRODUCTOS = [
    ("ARROZ FLOR 2KG", "1", "7861000000011", 2.75, False, 50),
    ("AZUCAR BLANCA 1KG", "2", "7861000000028", 1.10, False, 80),
    ("HARINA DE TRIGO 9KG", "3", "7861000000035", 6.00, False, 12),
    ("ACEITE DE GIRASOL 1LT", "4", "7861000000042", 2.95, False, 35),
    ("CHOCOLATE LISTO 220GR", "5", "7861000000059", 1.54, True, 40),
    ("CHOCOLATE FAMILIAR NEGRO", "6", "7861000000066", 1.13, True, 25),
    ("GASEOSA COLA 3LT", "7", "7861000000073", 2.25, True, 60),
    ("CARRITO HOT WHEELS", "8", "7861000000080", 1.20, True, 30),
]


def impuesto(odoo, porcentaje: float, nombre_ecuador: str) -> list[int]:
    """IVA de venta para bienes.

    Con la localización de Ecuador usa el del SRI (ej. "IVA 0% (415, B)"): el SRI pide un
    impuesto en cada línea, también en las de 0%. Sin ella, el primero con ese porcentaje,
    y ninguno para 0%.
    """
    base = [["type_tax_use", "=", "sale"], ["amount_type", "=", "percent"], ["amount", "=", porcentaje]]
    ids = odoo.call("account.tax", "search", limit=1, context={"lang": "es_EC"},
                    domain=base + [["name", "=", nombre_ecuador]])
    if ids or porcentaje == 0:
        return ids
    return odoo.call("account.tax", "search", limit=1, domain=base)


def main():
    odoo = OdooClient.desde_env(archivo_env())
    print(f"Odoo: {odoo.url}  base: {odoo.db}")

    iva15 = impuesto(odoo, 15, "IVA 15% (411, B)")
    iva0 = impuesto(odoo, 0, "IVA 0% (415, B)")
    bodega = odoo.call("stock.warehouse", "search_read", domain=[], fields=["lot_stock_id"], limit=1)
    ubicacion = bodega[0]["lot_stock_id"][0]

    for nombre, ref, barras, precio, con_iva, stock in PRODUCTOS:
        existe = odoo.call("product.product", "search_read", limit=1,
                           domain=[["default_code", "=", ref]], fields=["qty_available"])
        if existe:
            producto_id, actual = existe[0]["id"], existe[0]["qty_available"]
            print(f"Ya existe: {ref} {nombre}")
        else:
            # Crear el producto (product.template crea también su product.product)
            tmpl_id = odoo.call("product.template", "create", vals_list=[{
                "name": nombre,
                "default_code": ref,
                "barcode": barras,
                "list_price": precio,
                "type": "consu",
                "is_storable": True,
                "available_in_pos": True,
                "taxes_id": [[6, 0, iva15 if con_iva else iva0]],
            }])[0]
            producto_id = odoo.call("product.product", "search",
                                    domain=[["product_tmpl_id", "=", tmpl_id]], limit=1)[0]
            actual = 0
            print(f"Creado:    {ref} {nombre}  precio {precio}")

        if actual != stock:
            # Poner la cantidad en bodega: ajuste de inventario y aplicarlo
            quant_id = odoo.call("stock.quant", "create", context={"inventory_mode": True}, vals_list=[{
                "product_id": producto_id,
                "location_id": ubicacion,
                "inventory_quantity": stock,
            }])[0]
            odoo.call("stock.quant", "action_apply_inventory", ids=[quant_id])
            print(f"           stock {actual:g} -> {stock}")


if __name__ == "__main__":
    main()
