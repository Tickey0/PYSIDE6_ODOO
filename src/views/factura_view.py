import re
from datetime import datetime

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QVBoxLayout, QWidget,
)

from src.controllers.producto_controller import ProductoController
from src.models.producto import Producto
from src.services.odoo_client import OdooError
from src.views.articulos_dialog import ArticulosDialog

FILAS = 10

# (título, ancho, alineación). Solo "Código de Barras" se edita; lo demás lo llena Odoo.
COLUMNAS = [
    ("Nro.", 40, Qt.AlignCenter),
    ("Código de Barras", 150, Qt.AlignLeft),
    ("UM", 70, Qt.AlignCenter),
    ("Descripción", 300, Qt.AlignLeft),
    ("Cantidad", 80, Qt.AlignRight),
    ("Precio Unit.", 90, Qt.AlignRight),
    ("% Desc", 50, Qt.AlignRight),
    ("TOTAL", 100, Qt.AlignRight),
    ("IVA", 40, Qt.AlignCenter),
    ("ICE", 70, Qt.AlignRight),
]
C_COD, C_UM, C_DESC, C_CANT, C_PRECIO, C_PDESC, C_TOTAL, C_IVA, C_ICE = 1, 2, 3, 4, 5, 6, 7, 8, 9

# "3.CHOCOL" -> cantidad 3, busca "CHOCOL". Acepta decimales con coma: "1,5.18"
CANTIDAD_PREFIJO = re.compile(r"^(\d+(?:,\d+)?)\.(.+)$")

ESTILO = """
QWidget { background: white; color: black; font-size: 11px; }
QLineEdit { background: white; color: black; border: 1px solid #808080; padding: 1px 3px; }
QLineEdit:read-only { background: #eeeeee; }
QLineEdit[activa="true"] { background: #e6ff8c; }
QLineEdit:focus { background: #ffff80; }
QLineEdit[resumen="true"] { background: #c8f0c8; }
QLabel[cabecera="true"] { color: #000080; font-weight: bold; }
QFrame { background: white; }
"""


def separar_cantidad(texto: str) -> tuple[float, str]:
    m = CANTIDAD_PREFIJO.match(texto)
    if m:
        return float(m.group(1).replace(",", ".")), m.group(2).strip()
    return 1.0, texto


class PantallaFactura(QWidget):
    def __init__(self, controller: ProductoController):
        super().__init__()
        self.controller = controller
        self.lineas: list[tuple[Producto, float] | None] = [None] * FILAS
        self.fila_activa = 0
        self.setStyleSheet(ESTILO)
        raiz = QVBoxLayout(self)

        # ---- Cabecera: cliente y fecha ----
        cab = QHBoxLayout()
        lbl = QLabel("Cliente")
        lbl.setProperty("cabecera", True)
        self.cli_cod = QLineEdit("99")
        self.cli_cod.setFixedWidth(60)
        self.cli_cod.setReadOnly(True)
        self.cli_cod.setFocusPolicy(Qt.NoFocus)
        self.cli_nombre = QLineEdit("CONSUMIDOR FINAL")
        self.cli_nombre.setReadOnly(True)
        self.cli_nombre.setFocusPolicy(Qt.NoFocus)
        lbl_f = QLabel("Fecha")
        lbl_f.setProperty("cabecera", True)
        self.fecha = QLineEdit(datetime.now().strftime("%d-%m-%Y %H:%M"))
        self.fecha.setReadOnly(True)
        self.fecha.setFocusPolicy(Qt.NoFocus)
        self.fecha.setFixedWidth(130)
        cab.addWidget(lbl)
        cab.addWidget(self.cli_cod)
        cab.addWidget(self.cli_nombre, 1)
        cab.addSpacing(30)
        cab.addWidget(lbl_f)
        cab.addWidget(self.fecha)
        raiz.addLayout(cab)

        # ---- Grilla de detalle ----
        grid = QGridLayout()
        grid.setSpacing(1)
        for c, (titulo, ancho, _) in enumerate(COLUMNAS):
            t = QLabel(titulo)
            t.setProperty("cabecera", True)
            t.setAlignment(Qt.AlignCenter)
            grid.addWidget(t, 0, c)
            grid.setColumnMinimumWidth(c, ancho)
        grid.setColumnStretch(C_DESC, 1)

        self.campos = []  # self.campos[fila][col]
        self.fila_de = {}  # campo de código -> fila
        for f in range(FILAS):
            renglon = []
            for c, (_, _, alin) in enumerate(COLUMNAS):
                campo = QLineEdit()
                campo.setAlignment(alin | Qt.AlignVCenter)
                if c == C_COD:
                    campo.installEventFilter(self)
                    self.fila_de[campo] = f
                else:
                    campo.setReadOnly(True)
                    campo.setFocusPolicy(Qt.NoFocus)
                grid.addWidget(campo, f + 1, c)
                renglon.append(campo)
            renglon[0].setText(str(f + 1))
            self.campos.append(renglon)
        raiz.addLayout(grid)

        ayuda = QLabel("Enter: buscar   F9: inventario   ↑ ↓: cambiar de línea   "
                       "3.CODIGO: cantidad 3")
        ayuda.setStyleSheet("color: #606060;")
        raiz.addWidget(ayuda)
        raiz.addStretch(1)

        # ---- Resumen inferior ----
        pie = QHBoxLayout()
        caja = QFrame()
        caja.setFrameShape(QFrame.StyledPanel)
        g = QGridLayout(caja)
        self.res = {}
        for clave, texto, fila, col in (
            ("t0", "Tarifa 0%", 0, 0), ("tiva", "Tarifa IVA", 0, 2), ("iva", "IVA", 0, 4),
            ("desc", "Descuentos", 1, 0), ("ice", "ICE", 1, 4),
        ):
            g.addWidget(QLabel(texto), fila, col)
            e = QLineEdit("0.00")
            e.setReadOnly(True)
            e.setFocusPolicy(Qt.NoFocus)
            e.setAlignment(Qt.AlignRight)
            e.setProperty("resumen", True)
            e.setFixedWidth(90)
            g.addWidget(e, fila, col + 1)
            self.res[clave] = e
        pie.addWidget(caja)
        pie.addStretch(1)

        pie.addWidget(QLabel("Total"))
        self.total = QLabel("0.00")
        self.total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.total.setFrameShape(QFrame.StyledPanel)
        self.total.setStyleSheet(
            "background:#c8f0c8; color:black; padding:8px 14px;"
            "font-size:28px; font-weight:bold;")
        self.total.setMinimumWidth(180)
        pie.addWidget(self.total)
        raiz.addLayout(pie)

        self.ir_a_fila(0)

    # ---- Navegación: solo por la columna "Código de Barras" ----
    def ir_a_fila(self, fila: int):
        fila = max(0, min(fila, FILAS - 1))
        for f in (self.fila_activa, fila):
            for campo in self.campos[f]:
                campo.setProperty("activa", f == fila)
                campo.style().unpolish(campo)
                campo.style().polish(campo)
        self.fila_activa = fila
        destino = self.campos[fila][C_COD]
        destino.setFocus()
        destino.selectAll()

    def eventFilter(self, campo, event):
        if event.type() != QEvent.KeyPress or campo not in self.fila_de:
            return False
        fila = self.fila_de[campo]
        tecla = event.key()
        if tecla in (Qt.Key_Return, Qt.Key_Enter):
            self.procesar(fila)
        elif tecla == Qt.Key_F9:
            self.abrir_inventario(fila)
        elif tecla == Qt.Key_Down:
            self.ir_a_fila(fila + 1)
        elif tecla == Qt.Key_Up:
            self.ir_a_fila(fila - 1)
        else:
            return False
        return True

    # ---- Búsqueda en Odoo ----
    def procesar(self, fila: int):
        texto = self.campos[fila][C_COD].text().strip()
        if not texto:
            if self.lineas[fila]:
                self.ir_a_fila(fila + 1)
            return
        cantidad, termino = separar_cantidad(texto)
        try:
            exactos = self.controller.por_codigo(termino)
            if len(exactos) == 1:
                self.poner_linea(fila, exactos[0], cantidad)
                return
            # No es un código exacto: buscar por "empieza con" y luego "contiene"
            patron = f"{termino}%"
            resultados = self.controller.buscar(patron)
            if not resultados:
                patron = f"%{termino}%"
                resultados = self.controller.buscar(patron)
        except OdooError as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        if not resultados:
            QMessageBox.warning(self, "Artículo", f"No existe ningún artículo con «{termino}».")
            self.ir_a_fila(fila)
        elif len(resultados) == 1:
            self.poner_linea(fila, resultados[0], cantidad)
        else:
            self.elegir(fila, cantidad, patron, resultados)

    def abrir_inventario(self, fila: int):
        cantidad, termino = separar_cantidad(self.campos[fila][C_COD].text().strip())
        patron = termino if "%" in termino else f"{termino}%"
        self.elegir(fila, cantidad, patron)

    def elegir(self, fila: int, cantidad: float, patron: str, resultados=None):
        dialogo = ArticulosDialog(self.controller, patron, resultados, self)
        if dialogo.exec() and dialogo.seleccionado:
            self.poner_linea(fila, dialogo.seleccionado, cantidad)
        else:
            self.ir_a_fila(fila)

    # ---- Llenar la línea y calcular ----
    def poner_linea(self, fila: int, p: Producto, cantidad: float):
        self.lineas[fila] = (p, cantidad)
        r = self.campos[fila]
        r[C_COD].setText(p.codigo)
        r[C_UM].setText(p.unidad)
        r[C_DESC].setText(p.nombre)
        r[C_CANT].setText(f"{cantidad:.2f}")
        r[C_PRECIO].setText(f"{p.precio:.4f}")
        r[C_PDESC].setText("0.00")
        r[C_TOTAL].setText(f"{cantidad * p.precio:.2f}")
        r[C_IVA].setText(f"{p.iva:g}")
        r[C_ICE].setText("0.00")
        self.recalcular()
        self.ir_a_fila(fila + 1)

    def recalcular(self):
        t0 = tiva = iva = 0.0
        for linea in self.lineas:
            if not linea:
                continue
            p, cantidad = linea
            neto = cantidad * p.precio
            if p.iva:
                tiva += neto
                iva += neto * p.iva / 100
            else:
                t0 += neto
        for k, v in (("t0", t0), ("tiva", tiva), ("iva", iva), ("desc", 0.0), ("ice", 0.0)):
            self.res[k].setText(f"{v:.2f}")
        self.total.setText(f"{t0 + tiva + iva:.2f}")
