import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTabWidget

from src.controllers.producto_controller import ProductoController
from src.services.odoo_client import OdooClient, OdooError
from src.views.factura_view import PantallaFactura
from src.views.login_view import LoginView


class Ventana(QTabWidget):
    def __init__(self, controller: ProductoController, sesion: dict):
        super().__init__()
        self.setWindowTitle(f"Empresa: {sesion['empresa']} /Opcion: FACTURA /Usuario: {sesion['nombre']}")
        self.addTab(PantallaFactura(controller), "Factura")


def paleta_clara(app: QApplication):
    app.setStyle("Fusion")
    claro = QPalette()
    claro.setColor(QPalette.Window, QColor("white"))
    claro.setColor(QPalette.WindowText, QColor("black"))
    claro.setColor(QPalette.Base, QColor("white"))
    claro.setColor(QPalette.Text, QColor("black"))
    claro.setColor(QPalette.Button, QColor("#f0f0f0"))
    claro.setColor(QPalette.ButtonText, QColor("black"))
    app.setPalette(claro)


def iniciar_sesion(odoo: OdooClient) -> dict | None:
    """Muestra el login hasta que los datos sean correctos o el usuario salga."""
    while True:
        login = LoginView(f"{odoo.url} ({odoo.db})")
        if login.exec() != QDialog.Accepted:
            return None
        try:
            return odoo.login(login.usuario.text().strip(), login.password.text())
        except OdooError as e:
            QMessageBox.warning(None, "Ingreso", str(e))


def main():
    app = QApplication(sys.argv)
    paleta_clara(app)
    try:
        odoo = OdooClient.desde_env()
        odoo.version()
    except OdooError as e:
        QMessageBox.critical(None, "Odoo", str(e))
        return 1

    sesion = iniciar_sesion(odoo)
    if not sesion:
        return 0

    ventana = Ventana(ProductoController(odoo), sesion)
    ventana.resize(1000, 520)
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
