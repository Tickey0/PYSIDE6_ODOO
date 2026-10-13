from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from src.controllers.producto_controller import ProductoController
from src.models.producto import Producto
from src.services.odoo_client import OdooError

COLUMNAS = ["Nombre Artículo", "Precio Venta", "Código Barras", "Stock"]


class ArticulosDialog(QDialog):
    """Maestro de Artículos: busca en el inventario de Odoo y devuelve el elegido.

    Enter en "Buscar" busca; flechas recorren la lista; Enter en la lista acepta;
    Esc cancela.
    """

    def __init__(self, controller: ProductoController, patron: str,
                 resultados: list[Producto] | None = None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.productos: list[Producto] = []
        self.seleccionado: Producto | None = None
        self.setWindowTitle("Maestro de Artículos")
        self.resize(760, 380)

        raiz = QVBoxLayout(self)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Buscar"))
        self.buscar_txt = QLineEdit(patron)
        self.buscar_txt.installEventFilter(self)
        fila.addWidget(self.buscar_txt, 1)
        raiz.addLayout(fila)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3):
            self.tabla.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.tabla.installEventFilter(self)
        self.tabla.doubleClicked.connect(self.aceptar)
        raiz.addWidget(self.tabla, 1)

        self.estado = QLabel()
        raiz.addWidget(self.estado)

        botones = QHBoxLayout()
        for texto, accion in (("Buscar", self.buscar), ("Aceptar", self.aceptar),
                              ("Cancelar", self.reject)):
            b = QPushButton(texto)
            b.setAutoDefault(False)  # Enter lo manejamos nosotros, no el boton
            b.clicked.connect(accion)
            botones.addStretch(1)
            botones.addWidget(b)
        botones.addStretch(1)
        raiz.addLayout(botones)

        if resultados is None:
            self.buscar()
        else:
            self.mostrar(resultados)

    def buscar(self):  # 🟠 CONSULTA F9: busca en el inventario
        patron = self.buscar_txt.text().strip() or "%"
        try:
            self.mostrar(self.controller.buscar(patron))
        except OdooError as e:
            QMessageBox.critical(self, "Error", str(e))

    def mostrar(self, productos: list[Producto]):
        self.productos = productos
        self.tabla.setRowCount(0)
        for p in productos:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)
            for c, (texto, alin) in enumerate((
                (p.nombre, Qt.AlignLeft),
                (f"{p.precio:.2f}", Qt.AlignRight),
                (p.codigo, Qt.AlignLeft),
                (f"{p.stock:g}", Qt.AlignRight),
            )):
                item = QTableWidgetItem(texto)
                item.setTextAlignment(alin | Qt.AlignVCenter)
                self.tabla.setItem(fila, c, item)
        self.estado.setText(f"{len(productos)} artículo(s)" if productos else "No hay artículos con ese texto")
        if productos:
            self.tabla.selectRow(0)
            self.tabla.setFocus()
        else:
            self.buscar_txt.setFocus()
            self.buscar_txt.selectAll()

    def aceptar(self):
        fila = self.tabla.currentRow()
        if 0 <= fila < len(self.productos):
            self.seleccionado = self.productos[fila]
            self.accept()

    def eventFilter(self, obj, event):
        if event.type() != QEvent.KeyPress:
            return False
        tecla = event.key()
        if obj is self.buscar_txt:
            if tecla in (Qt.Key_Return, Qt.Key_Enter):
                self.buscar()
                return True
            if tecla == Qt.Key_Down and self.productos:
                self.tabla.setFocus()
                return True
        elif obj is self.tabla and tecla in (Qt.Key_Return, Qt.Key_Enter):
            self.aceptar()
            return True
        return False
