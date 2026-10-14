import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTabWidget

from src.controllers.producto_controller import ProductoController
from src.controllers.venta_controller import VentaController
from src.services.odoo_client import OdooClient, OdooError, archivo_env
from src.views.factura_datatable_view import PantallaFactura
from src.views.login_view import LoginView

# Para volver a la factura anterior (grilla fija de 10 filas, sin Guardar):
#   from src.views.factura_view import PantallaFactura
#   y en Ventana: self.addTab(PantallaFactura(productos), "Factura")


class Ventana(QTabWidget):
    def __init__(self, odoo: OdooClient, sesion: dict):
        super().__init__()
        self.setWindowTitle(f"Empresa: {sesion['empresa']} /Opcion: FACTURA /Usuario: {sesion['nombre']}")
        productos = ProductoController(odoo)
        self.factura = PantallaFactura(productos, VentaController(odoo))
        self.addTab(self.factura, "Factura")

    def showEvent(self, event):
        super().showEvent(event)
        self.factura.detalle.enfocar()


def paleta_clara(app: QApplication):
    app.setStyle("Fusion")
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)  # aunque Windows esté en modo oscuro
    claro = QPalette()
    claro.setColor(QPalette.Window, QColor("white"))
    claro.setColor(QPalette.WindowText, QColor("black"))
    claro.setColor(QPalette.Base, QColor("white"))
    claro.setColor(QPalette.Text, QColor("black"))
    claro.setColor(QPalette.Button, QColor("#f0f0f0"))
    claro.setColor(QPalette.ButtonText, QColor("black"))
    # Si no se fijan, Windows en modo oscuro pone azul marino y negro en tablas y selección
    claro.setColor(QPalette.AlternateBase, QColor("white"))
    claro.setColor(QPalette.Highlight, QColor("#e6ff8c"))
    claro.setColor(QPalette.HighlightedText, QColor("black"))
    claro.setColor(QPalette.ToolTipBase, QColor("#ffffe1"))
    claro.setColor(QPalette.ToolTipText, QColor("black"))
    app.setPalette(claro)


def iniciar_sesion(odoo: OdooClient) -> dict | None:  # 🟠 LOGIN 2: ventana de login
    """Muestra el login hasta que los datos sean correctos o el usuario salga."""
    while True:
        login = LoginView(f"{odoo.url} ({odoo.db})")
        if login.exec() != QDialog.Accepted:
            return None
        try:
            return odoo.login(login.usuario.text().strip(), login.password.text())
        except OdooError as e:
            QMessageBox.warning(None, "Ingreso", str(e))


def main():  # 🟠 LOGIN 1: lee .env y revisa que Odoo responda
    app = QApplication(sys.argv)
    paleta_clara(app)
    try:
        odoo = OdooClient.desde_env(archivo_env())  # .env, o el de --env (ej. .env.odoo19)
        odoo.version()
    except OdooError as e:
        QMessageBox.critical(None, "Odoo", str(e))
        return 1

    sesion = iniciar_sesion(odoo)
    if not sesion:
        return 0

    ventana = Ventana(odoo, sesion)
    ventana.setMinimumHeight(460)  # el ancho mínimo lo pone la franja de totales, para que no se corte
    ventana.resize(1100, 600)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
