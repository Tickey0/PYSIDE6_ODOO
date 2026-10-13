"""Cliente de la API externa JSON-2 de Odoo 20.

Cada llamada es un POST a /json/2/<modelo>/<metodo>, autenticado con una
clave API en la cabecera Authorization. Los argumentos van siempre con
nombre (domain=..., fields=...), nunca por posicion.
"""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]


class OdooError(Exception):
    """Error devuelto por Odoo o problema de conexion."""


class OdooClient:
    def __init__(self, url: str, db: str, api_key: str, timeout: int = 15):
        self.url = url.rstrip("/")
        self.db = db
        self.timeout = timeout
        self.context = {}
        self.http = requests.Session()
        self.http.headers.update({
            "Authorization": f"bearer {api_key}",
            "X-Odoo-Database": db,
            "User-Agent": "odoo_pyside6",
        })

    @classmethod
    def desde_env(cls):
        """Lee ODOO_URL, ODOO_DB y ODOO_API_KEY del archivo .env del proyecto."""
        load_dotenv(RAIZ / ".env")
        faltan = [v for v in ("ODOO_URL", "ODOO_DB", "ODOO_API_KEY") if not os.getenv(v)]
        if faltan:
            raise OdooError(f"Faltan en el archivo .env: {', '.join(faltan)}")
        return cls(os.getenv("ODOO_URL"), os.getenv("ODOO_DB"), os.getenv("ODOO_API_KEY"))

    def version(self) -> str:
        try:
            r = self.http.get(f"{self.url}/web/version", timeout=self.timeout)
            return r.json()["version"]
        except requests.RequestException:
            raise OdooError(f"No se pudo conectar a {self.url}. ¿Odoo esta arrancado?")

    def call(self, model: str, method: str, ids: list | None = None, **kwargs):
        """Llama a cualquier metodo publico de un modelo de Odoo."""
        body = dict(kwargs)
        if ids is not None:
            body["ids"] = ids
        if self.context:
            body.setdefault("context", self.context)
        try:
            r = self.http.post(f"{self.url}/json/2/{model}/{method}", json=body, timeout=self.timeout)
        except requests.RequestException:
            raise OdooError(f"No se pudo conectar a {self.url}. ¿Odoo esta arrancado?")
        if r.status_code == 200:
            return r.json()
        if r.status_code == 401:
            raise OdooError("La clave API no es valida o ya vencio (revisa ODOO_API_KEY en .env).")
        try:
            mensaje = r.json().get("message", r.text)
        except ValueError:
            mensaje = r.text[:300]
        raise OdooError(f"{model}.{method}: {mensaje}")

    def login(self, usuario: str, password: str) -> dict:
        """Valida usuario y contraseña, y que la clave API sea de ese mismo usuario.

        JSON-2 no acepta usuario/contraseña, asi que la contraseña se valida con
        /web/session/authenticate (ruta jsonrpc del cliente web, no deprecada).
        """
        try:
            r = requests.post(f"{self.url}/web/session/authenticate", timeout=self.timeout, json={
                "jsonrpc": "2.0", "method": "call",
                "params": {"db": self.db, "login": usuario, "password": password},
            })
            datos = r.json()
        except (requests.RequestException, ValueError):
            raise OdooError(f"No se pudo conectar a {self.url}. ¿Odoo esta arrancado?")
        uid = (datos.get("result") or {}).get("uid")
        if "error" in datos or not uid:
            raise OdooError("Usuario o contraseña incorrectos.")

        ctx = self.call("res.users", "context_get")
        if ctx.get("uid") != uid:
            raise OdooError("La clave API del archivo .env pertenece a otro usuario.")
        self.context = {"lang": ctx.get("lang"), "tz": ctx.get("tz")}

        usuario = self.call("res.users", "read", ids=[uid], fields=["name", "company_id"])[0]
        return {"uid": uid, "nombre": usuario["name"], "empresa": usuario["company_id"][1]}
