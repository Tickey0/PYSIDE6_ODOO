"""Pantalla de factura (contenedor): buscador + fecha, DetalleFactura, franja de totales.

Atajos: Ctrl+F buscar una línea en la factura · Alt+G (o soltar Alt y luego G) guardar.
La versión anterior, con la grilla de 10 filas, sigue en factura_view.py.
"""
from collections import defaultdict
from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QStyle, QVBoxLayout, QWidget,
)

from src.controllers.producto_controller import ProductoController
from src.controllers.venta_controller import VentaController, VentaError
from src.views.detalle_factura import DetalleFactura

ESTILO = """
QWidget { background: white; color: black; font-size: 12px; }
QLineEdit { background: white; color: black; border: 1px solid #b0b0b0; padding: 2px 4px; }
QLineEdit:read-only { background: #f2f2f2; }
QLineEdit[resumen="true"] { background: #e3f5e3; border-color: #9ccc9c; }
QLabel[cabecera="true"] { color: #000080; font-weight: bold; }
QLabel#ayuda { color: #707070; font-size: 11px; }
QLabel#no_encontrado { color: #b00020; }
QLineEdit#buscar { border-radius: 4px; padding: 4px 6px; }
QFrame#franja { border: 1px solid #c8c8c8; border-radius: 4px; background: #fafafa; }
QFrame#franja QLabel { background: transparent; }
QLabel#total { background: #e3f5e3; border: 1px solid #9ccc9c; border-radius: 4px; color: black;
               padding: 2px 14px; font-size: 24px; font-weight: bold; }
QPushButton#guardar { background: #f4f6fb; color: #000080; border: 1px solid #000080;
                      border-radius: 4px; padding: 6px 14px; font-size: 13px; font-weight: bold; }
QPushButton#guardar:hover, QPushButton#guardar[atajo="true"] { background: #e6ff8c; }
QPushButton#guardar:pressed { background: #d4ef70; }
"""


class PantallaFactura(QWidget):
    def __init__(self, productos: ProductoController, ventas: VentaController):
        super().__init__()
        self.ventas = ventas
        self.setStyleSheet(ESTILO)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(12, 10, 12, 10)
        raiz.setSpacing(8)

        # ---- Cabecera: buscar una línea en la factura (no filtra: lleva el cursor) y fecha ----
        cab = QHBoxLayout()
        self.buscar = QLineEdit()
        self.buscar.setObjectName("buscar")
        self.buscar.setPlaceholderText("Buscar en la factura (Ctrl+F): código o descripción, Enter = siguiente")
        self.buscar.addAction(self.style().standardIcon(QStyle.SP_FileDialogContentsView),
                              QLineEdit.LeadingPosition)
        self.buscar.setClearButtonEnabled(True)
        self.buscar.setMaximumWidth(420)
        self.buscar.returnPressed.connect(self.buscar_linea)
        self.buscar.textChanged.connect(lambda: self.no_encontrado.clear())
        self.buscar.installEventFilter(self)
        cab.addWidget(self.buscar, 1)
        self.no_encontrado = QLabel()
        self.no_encontrado.setObjectName("no_encontrado")
        cab.addWidget(self.no_encontrado)
        cab.addStretch(1)
        lbl_f = QLabel("Fecha")
        lbl_f.setProperty("cabecera", True)
        self.fecha = QLineEdit(datetime.now().strftime("%d-%m-%Y %H:%M"))
        self.fecha.setFixedWidth(130)
        self.fecha.setReadOnly(True)
        self.fecha.setFocusPolicy(Qt.NoFocus)
        cab.addWidget(lbl_f)
        cab.addWidget(self.fecha)
        raiz.addLayout(cab)

        # ---- Detalle: la tabla es una pieza aparte ----
        self.detalle = DetalleFactura(productos)
        self.detalle.cambio.connect(self.recalcular)
        raiz.addWidget(self.detalle, 1)

        ayuda = QLabel("Enter: buscar    F9: inventario    ↑ ↓: cambiar de línea    "
                       "5.CODIGO: cantidad 5    Shift+F6: vaciar la línea    "
                       "Ctrl+F: buscar en la factura    Alt+G: guardar")
        ayuda.setObjectName("ayuda")
        raiz.addWidget(ayuda)

        # ---- Franja de abajo, en una sola fila: totales · Guardar · Total ----
        franja = QFrame()
        franja.setObjectName("franja")
        fila = QHBoxLayout(franja)
        fila.setContentsMargins(10, 6, 10, 6)
        fila.setSpacing(6)
        self.res = {}
        for clave, texto in (("t0", "Tarifa 0%"), ("tiva", "Tarifa IVA"), ("iva", "IVA"),
                             ("desc", "Desc."), ("ice", "ICE")):
            fila.addWidget(QLabel(texto))
            e = QLineEdit("0.00")
            e.setReadOnly(True)
            e.setFocusPolicy(Qt.NoFocus)
            e.setAlignment(Qt.AlignRight)
            e.setProperty("resumen", True)
            e.setFixedWidth(78)
            fila.addWidget(e)
            fila.addSpacing(8)
            self.res[clave] = e
        fila.addStretch(1)

        # "&G": la G sale subrayada y Alt+G presiona el botón, como en el sistema anterior
        self.btn_guardar = QPushButton(" &Guardar")
        self.btn_guardar.setObjectName("guardar")
        self.btn_guardar.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))  # disquete
        self.btn_guardar.setToolTip("Guardar la factura en Odoo: Alt+G, o soltar Alt y luego G")
        self.btn_guardar.setFocusPolicy(Qt.NoFocus)  # el cursor se queda en la tabla
        self.btn_guardar.setCursor(Qt.PointingHandCursor)
        self.btn_guardar.clicked.connect(self.guardar)
        fila.addWidget(self.btn_guardar)
        fila.addSpacing(12)

        lbl_total = QLabel("TOTAL")
        lbl_total.setProperty("cabecera", True)
        fila.addWidget(lbl_total)
        self.total = QLabel("0.00")
        self.total.setObjectName("total")
        self.total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.total.setMinimumWidth(150)
        fila.addWidget(self.total)
        raiz.addWidget(franja)

        QShortcut(QKeySequence("Ctrl+F"), self, self.ir_a_buscar)
        # Soltar Alt y después presionar la letra (como los menús del sistema anterior)
        self._alt_solo = False
        self._modo_alt = False
        QApplication.instance().installEventFilter(self)

        self.recalcular()

    # ---- Buscar una línea dentro de la factura ----
    def ir_a_buscar(self):
        self.buscar.setFocus()
        self.buscar.selectAll()

    def buscar_linea(self):
        texto = self.buscar.text()
        if not texto.strip():
            self.detalle.enfocar()
        elif not self.detalle.buscar_en_lineas(texto):
            self.no_encontrado.setText(f"«{texto.strip()}» no está en la factura")

    # ---- Teclado de toda la pantalla ----
    def eventFilter(self, obj, event):
        tipo = event.type()
        if tipo in (QEvent.KeyPress, QEvent.KeyRelease) and self._es_de_esta_ventana(obj):
            if self._atajo_alt(tipo, event):
                return True
            # Esc en el buscador: volver a la tabla
            if obj is self.buscar and tipo == QEvent.KeyPress and event.key() == Qt.Key_Escape:
                self.detalle.enfocar()
                return True
        return super().eventFilter(obj, event)

    def _es_de_esta_ventana(self, obj) -> bool:
        # Los diálogos (F9, mensajes) son otras ventanas: ahí no se interceptan teclas
        return obj.isWidgetType() and self.isVisible() and obj.window() is self.window()

    def _atajo_alt(self, tipo, event) -> bool:
        """Soltar Alt deja la pantalla esperando una letra; G guarda. Devuelve True si la usó."""
        tecla = event.key()
        if tipo == QEvent.KeyRelease:
            if tecla == Qt.Key_Alt and self._alt_solo:
                self._alt_solo = False
                self._marcar_modo_alt(True)
            return False
        if tecla == Qt.Key_Alt:
            self._alt_solo = True  # todavía no se sabe si viene Alt+letra o Alt solo
            return False
        self._alt_solo = False
        if not self._modo_alt:
            return False
        self._marcar_modo_alt(False)
        if tecla == Qt.Key_G:
            QTimer.singleShot(0, self.guardar)  # fuera del evento de teclado
            return True
        return tecla == Qt.Key_Escape  # Esc solo cancela el modo Alt

    def _marcar_modo_alt(self, activo: bool):
        self._modo_alt = activo
        self.btn_guardar.setProperty("atajo", activo)
        self.btn_guardar.style().unpolish(self.btn_guardar)
        self.btn_guardar.style().polish(self.btn_guardar)

    def recalcular(self):
        t0 = tiva = iva = 0.0
        for p, cantidad in self.detalle.productos():
            neto = cantidad * p.precio
            if p.iva:
                tiva += neto
                iva += neto * p.iva / 100
            else:
                t0 += neto
        for k, v in (("t0", t0), ("tiva", tiva), ("iva", iva), ("desc", 0.0), ("ice", 0.0)):
            self.res[k].setText(f"{v:.2f}")
        self.total.setText(f"{t0 + tiva + iva:.2f}")

    def guardar(self):  # 🟠 VENTA 0: Alt+G o botón Guardar
        lineas = self.detalle.productos()
        if not lineas:
            QMessageBox.information(self, "Guardar", "La factura no tiene productos.")
            self.detalle.enfocar()
            return

        # Avisar si se vende más de lo que hay en bodega (Odoo lo permite: queda en negativo)
        pedido = defaultdict(float)
        for p, cantidad in lineas:
            pedido[p.id] += cantidad
        faltan = {p.nombre: (pedido[p.id], p.stock) for p, _ in lineas if pedido[p.id] > p.stock}
        if faltan:
            detalle = "\n".join(f"• {n}: pide {q:g}, hay {s:g}" for n, (q, s) in faltan.items())
            if QMessageBox.question(self, "Stock insuficiente",
                                    f"No alcanza el stock de:\n\n{detalle}\n\n¿Guardar de todas formas?"
                                    ) != QMessageBox.Yes:
                self.detalle.enfocar()
                return

        if QMessageBox.question(self, "Guardar",
                                f"¿Guardar la factura por ${self.total.text()}?") != QMessageBox.Yes:
            self.detalle.enfocar()
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            r = self.ventas.guardar(lineas)  # 🟠 VENTA 0: pasa al controlador
        except VentaError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "No se guardó completa", str(e))
            self.detalle.enfocar()
            return
        QApplication.restoreOverrideCursor()

        QMessageBox.information(self, "Factura guardada",
                                f"Factura {r['factura']} guardada.\n\n"
                                f"Total: ${r['total']:.2f}\nEstado: {r['estado']}\n"
                                f"Pedido: {r['pedido']}")
        self.fecha.setText(datetime.now().strftime("%d-%m-%Y %H:%M"))
        self.detalle.limpiar()
