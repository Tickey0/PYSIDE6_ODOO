"""Ejemplos de consultas a Odoo con la API JSON-2. Solo lee: no cambia nada en Odoo.

Uso:  python -m scripts.ejemplos_api                    (Odoo del .env)
      python -m scripts.ejemplos_api --env .env.odoo19  (Odoo 19)

Toda llamada tiene la misma forma:
    odoo.call("<modelo>", "<método>", ids=[...], argumento=valor, ...)
que se convierte en  POST <ODOO_URL>/json/2/<modelo>/<método>  con la clave API.
"""
from src.services.odoo_client import OdooClient, archivo_env


def titulo(texto):
    print(f"\n=== {texto}")


def main():
    odoo = OdooClient.desde_env(archivo_env())
    odoo.context = {"lang": "es_EC"}  # nombres en español
    print(f"Odoo {odoo.version()} en {odoo.url}, base {odoo.db}")

    titulo("1. ¿De quién es la clave API?  res.users / context_get")
    print(odoo.call("res.users", "context_get"))

    titulo("2. Productos del Punto de Venta con su stock  product.product / search_read")
    productos = odoo.call(
        "product.product", "search_read",
        domain=[["available_in_pos", "=", True], ["type", "=", "consu"]],  # el filtro (WHERE)
        fields=["default_code", "name", "lst_price", "qty_available"],     # las columnas
        order="default_code", limit=10,
    )
    for p in productos:
        print(f"  [{p['default_code']}] {p['name']:<28} ${p['lst_price']:>6.2f}  stock {p['qty_available']:g}")

    titulo("3. Buscar por nombre, como el F9  product.product / search_read con ilike")
    for p in odoo.call("product.product", "search_read", fields=["name"],
                       domain=[["name", "ilike", "choco"]]):
        print(f"  id {p['id']}: {p['name']}")

    titulo("4. Contar sin traer los datos  sale.order / search_count")
    print("  pedidos confirmados:", odoo.call("sale.order", "search_count", domain=[["state", "=", "sale"]]))
    print("  facturas publicadas:", odoo.call("account.move", "search_count",
                                              domain=[["move_type", "=", "out_invoice"], ["state", "=", "posted"]]))

    titulo("5. Últimos pedidos de venta  sale.order / search_read con order y limit")
    for s in odoo.call("sale.order", "search_read", order="id desc", limit=5,
                       fields=["name", "date_order", "partner_id", "amount_total", "state"], domain=[]):
        print(f"  {s['name']}  {s['date_order']}  {s['partner_id'][1]:<20} ${s['amount_total']:>7.2f}  {s['state']}")

    titulo("6. Leer un registro por id  res.partner / read")
    cliente = odoo.call("res.partner", "search", domain=[["vat", "=", "9999999999999"]], limit=1)
    if cliente:
        print(odoo.call("res.partner", "read", ids=cliente, fields=["name", "vat", "country_id"]))

    titulo("7. Dónde está el stock  stock.quant / search_read")
    for q in odoo.call("stock.quant", "search_read", limit=5,
                       domain=[["location_id.usage", "=", "internal"]],
                       fields=["product_id", "location_id", "quantity"]):
        print(f"  {q['product_id'][1]:<30} {q['location_id'][1]:<12} {q['quantity']:g}")

    titulo("8. Qué campos tiene un modelo  product.product / fields_get")
    campos = odoo.call("product.product", "fields_get", attributes=["string", "type"])
    for nombre in ("barcode", "default_code", "lst_price", "qty_available", "taxes_id", "uom_id"):
        print(f"  {nombre:<15} {campos[nombre]['type']:<10} {campos[nombre]['string']}")
    print(f"  ... y {len(campos) - 6} campos más")

    # Para CAMBIAR datos (no se ejecuta aquí):
    #   odoo.call("product.product", "write", ids=[9], vals={"lst_price": 1.60})          # modificar
    #   odoo.call("res.partner", "create", vals_list=[{"name": "JUAN PEREZ",
    #                                                  "vat": "0912345678"}])             # crear
    #   odoo.call("sale.order", "action_confirm", ids=[5])                                # un botón


if __name__ == "__main__":
    main()
