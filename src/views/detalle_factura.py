"""Detalle de la factura hecho con DataTable (pyside6-datatable-widget).

Siempre hay una fila en blanco al final para escribir o escanear. Solo se edita
la columna "Código de Barras"; el resto lo llena Odoo.

Teclas en el código:  Enter buscar · F9 inventario · Shift+F6 vaciar la línea
(queda en blanco para volver a escribir) · ↑ ↓ cambiar de línea · "5.CODIGO" = cantidad 5
"""
import re

from datatable import DataTable, DataType
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLineEdit, QMessageBox, QStyledItemDelegate,
    QTableView, QVBoxLayout, QWidget,
)

from src.controllers.producto_controller import ProductoController
from src.models.producto import Producto
from src.services.odoo_client import OdooError
from src.views.articulos_dialog import ArticulosDialog

# (clave, título, ancho mínimo, alineación). Si sobra espacio se reparte en proporción
# a estos anchos, así la tabla se ve bien en una ventana chica o grande.
COLUMNAS = [
    ("nro", "Nro.", 40, Qt.AlignCenter),
    ("codigo", "Código de Barras", 115, Qt.AlignLeft),
    ("um", "UM", 70, Qt.AlignCenter),
    ("descripcion", "Descripción", 170, Qt.AlignLeft),
    ("cantidad", "Cantidad", 70, Qt.AlignRight),
    ("precio", "Precio Unit.", 80, Qt.AlignRight),
    ("pdesc", "% Desc", 55, Qt.AlignRight),
    ("total", "TOTAL", 80, Qt.AlignRight),
    ("iva", "IVA", 40, Qt.AlignCenter),
    ("ice", "ICE", 55, Qt.AlignRight),
]
# Cuánto del espacio sobrante se lleva cada columna (la descripción, la mayor parte)
PESOS = {"codigo": 2, "descripcion": 6, "cantidad": 1, "precio": 1, "total": 1}
C_COD = 1
C_DESC = 3

# "5.CODIGO" -> cantidad 5, busca "CODIGO". Acepta decimales con coma: "1,5.18"
CANTIDAD_PREFIJO = re.compile(r"^(\d+(?:,\d+)?)\.(.+)$")

ESTILO = """
QTableView { background: white; alternate-background-color: white; color: black;
             gridline-color: #dcdcdc; border: 1px solid #b0b0b0; font-size: 12px; }
QTableView::item { padding: 0 4px; }
QTableView::item:selected { background: #e6ff8c; color: black; }
QHeaderView::section { background: #f4f6fb; color: #000080; font-weight: bold;
                       border: none; border-bottom: 2px solid #000080; padding: 5px 4px; }
QLineEdit { background: #ffff80; color: black; border: none; font-size: 12px; }
"""


def separar_cantidad(texto: str) -> tuple[float, str]:
    m = CANTIDAD_PREFIJO.match(texto)
    if m:
        return float(m.group(1).replace(",", ".")), m.group(2).strip()
    return 1.0, texto


class AlineadoDelegate(QStyledItemDelegate):
    def __init__(self, alineacion, parent=None):
        super().__init__(parent)
        self.alineacion = alineacion

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = self.alineacion | Qt.AlignVCenter


class CodigoDelegate(QStyledItemDelegate):
    """Editor de la celda de código: atrapa las teclas de la factura."""
    tecla = Signal(str, str)  # (acción, texto escrito)

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        return editor

    def setEditorData(self, editor, index):
        editor.setText(str(index.data(Qt.EditRole) or ""))
        editor.selectAll()

    def eventFilter(self, editor, event):  # 🟠 CONSULTA 1: Enter / F9 / Shift+F6 en la celda del código
        if event.type() == QEvent.KeyPress:
            tecla, shift = event.key(), bool(event.modifiers() & Qt.ShiftModifier)
            if tecla in (Qt.Key_Return, Qt.Key_Enter):
                accion = "buscar"
            elif tecla == Qt.Key_F9:
                accion = "inventario"
            elif tecla == Qt.Key_F6 and shift:
                accion = "borrar"
            elif tecla == Qt.Key_Up:
                accion = "arriba"
            elif tecla == Qt.Key_Down:
                accion = "abajo"
            elif tecla == Qt.Key_Escape:
                editor.clear()
                return True
            elif tecla in (Qt.Key_Tab, Qt.Key_Backtab):
                return True  # el cursor no sale de la columna de código
            else:
                return super().eventFilter(editor, event)
            texto = editor.text()
            # Se procesa después de soltar el evento: la tabla se redibuja y este editor se destruye
            QTimer.singleShot(0, lambda: self.tecla.emit(accion, texto))
            return True
        return super().eventFilter(editor, event)


class DetalleFactura(QWidget):
    """Líneas de la factura. La pantalla que lo contiene escucha `cambio`."""
    cambio = Signal()

    def __init__(self, controller: ProductoController, parent=None):
        super().__init__(parent)
        self.controller = controller
        # Una entrada por fila; None = fila vaciada con Shift+F6 (sigue ahí para reescribirla)
        self.lineas: list[tuple[Producto, float] | None] = []
        self.fila = 0                # fila del cursor (len(lineas) = fila en blanco del final)
        self._borrador = (0, "")     # (fila, texto) escrito en una fila vacía, sin buscar aún

        self.tabla = DataTable()  # 🟠 TABLA del jefe (table/app.py)
        # La DataTable exige 640x480 como mínimo; en una ventana más baja la parte de abajo
        # de la factura se montaba encima de la tabla y tapaba la fila del cursor
        self.tabla.setMinimumSize(0, 0)
        self.tabla.getFilterStateInstance().itemsPerPage = 100_000  # sin paginación
        self.tabla.setColumns([(clave, titulo, DataType.STRING) for clave, titulo, _, _ in COLUMNAS])
        self.tabla.getModelInstance().setEditableColumns({"codigo": True})
        self._preparar_vista()

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.addWidget(self.tabla)
        self._refrescar()

    def _esconder_controles(self):
        # De la DataTable solo se usa la tabla: sin buscador, sin paginación.
        # Se repite en cada refresco porque la DataTable vuelve a mostrar la paginación.
        for hijo in self.tabla.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            if hijo is not self.tabla.tableView:
                hijo.hide()

    def _preparar_vista(self):  # 🟠 TABLA: ajustes a la librería DataTable
        vista = self.tabla.tableView
        vista.setStyleSheet(ESTILO)
        vista.setAlternatingRowColors(False)  # la DataTable trae filas alternadas (azul en Windows oscuro)
        # La DataTable arranca ordenando por la 1ra columna (de mayor a menor): se quita,
        # las líneas van en el orden en que se escanean
        vista.setSortingEnabled(False)
        self.tabla.getProxyModelInstance().sort(-1)
        vista.setEditTriggers(QAbstractItemView.NoEditTriggers)  # solo editamos nosotros
        vista.setSelectionMode(QTableView.SingleSelection)
        vista.setSelectionBehavior(QTableView.SelectRows)
        vista.setContextMenuPolicy(Qt.NoContextMenu)
        vista.verticalHeader().setDefaultSectionSize(24)
        cabecera = vista.horizontalHeader()
        cabecera.setSectionsClickable(False)
        cabecera.setSectionsMovable(False)
        cabecera.setSortIndicatorShown(False)
        cabecera.setStretchLastSection(False)
        cabecera.setContextMenuPolicy(Qt.NoContextMenu)

        self.delegado = CodigoDelegate(vista)
        self.delegado.tecla.connect(self._tecla)
        for c, (_, _, _, alineacion) in enumerate(COLUMNAS):
            if c != C_COD:
                vista.setItemDelegateForColumn(c, AlineadoDelegate(alineacion, vista))
        vista.setItemDelegateForColumn(C_COD, self.delegado)
        cabecera.setSectionResizeMode(QHeaderView.Fixed)
        cabecera.setMinimumSectionSize(30)  # la DataTable pone 45 y Nro./IVA se pasaban del ancho
        vista.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        vista.clicked.connect(self._clic)

    def _ajustar_columnas(self):
        """Reparte el ancho de la tabla entre las columnas (responsivo)."""
        vista = self.tabla.tableView
        disponible = vista.viewport().width()
        minimo = sum(ancho for _, _, ancho, _ in COLUMNAS)
        sobra = max(0, disponible - minimo)
        total_pesos = sum(PESOS.values())
        anchos = [ancho + sobra * PESOS.get(clave, 0) // total_pesos for clave, _, ancho, _ in COLUMNAS]
        anchos[C_DESC] += disponible - sum(anchos) if sobra else 0  # lo que queda por redondeo
        for c, ancho in enumerate(anchos):
            vista.setColumnWidth(c, ancho)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Cuando la tabla ya tomó su nuevo tamaño
        QTimer.singleShot(0, self._ajustar_columnas)

    # ---- Dibujar ----
    def productos(self) -> list[tuple[Producto, float]]:
        """Las líneas con producto (sin las filas vaciadas)."""
        return [linea for linea in self.lineas if linea]

    def _refrescar(self):
        posicion = self.tabla.tableView.verticalScrollBar().value()  # para que la vista no salte
        # Filas vaciadas al final sobran: la última pasa a ser la fila en blanco
        while self.lineas and self.lineas[-1] is None:
            self.lineas.pop()
        vacia = {clave: "" for clave, _, _, _ in COLUMNAS}
        fila_borrador, texto_borrador = self._borrador
        filas = []
        for i, linea in enumerate(self.lineas + [None]):
            if linea is None:
                filas.append({**vacia, "id": i, "nro": str(i + 1),
                              "codigo": texto_borrador if i == fila_borrador else ""})
                continue
            p, cantidad = linea
            filas.append({
                "id": i, "nro": str(i + 1), "codigo": p.codigo, "um": p.unidad,
                "descripcion": p.nombre, "cantidad": f"{cantidad:.2f}",
                "precio": f"{p.precio:.4f}", "pdesc": "0.00",
                "total": f"{cantidad * p.precio:.2f}", "iva": f"{p.iva:g}", "ice": "0.00",
            })
        # Directo al modelo y no con DataTable.setData(): esa devuelve el scroll a donde estaba
        self.tabla.getModelInstance().setModelData(filas)  # 🟠 TABLA: carga las filas en la DataTable
        self._esconder_controles()
        QTimer.singleShot(0, self._ajustar_columnas)  # por si apareció la barra de scroll vertical
        self.cambio.emit()
        self._ir_a(self.fila, posicion)

    def _indice(self, fila: int):
        """Índice de la vista para una fila de self.lineas (la vista pasa por un proxy)."""
        modelo = self.tabla.getModelInstance()
        return self.tabla.getProxyModelInstance().mapFromSource(modelo.index(fila, C_COD))

    def _clic(self, indice):
        self._ir_a(self.tabla.getProxyModelInstance().mapToSource(indice).row())

    def _ir_a(self, fila: int, posicion: int | None = None):
        """Pone el cursor en la celda de código de esa fila.

        `posicion` es el scroll que tenía la tabla antes de recargarla: se devuelve igual,
        y solo se mueve lo justo si la fila del cursor quedó fuera de la vista.
        """
        self.fila = max(0, min(fila, len(self.lineas)))
        vista = self.tabla.tableView
        indice = self._indice(self.fila)
        vista.setCurrentIndex(indice)
        vista.setFocus()
        vista.edit(indice)

        def acomodar():
            if posicion is not None:
                vista.verticalScrollBar().setValue(posicion)
            vista.scrollTo(self._indice(self.fila))  # EnsureVisible: no mueve si ya se ve

        acomodar()
        QTimer.singleShot(0, acomodar)  # otra vez cuando la tabla termine de acomodar las filas

    def buscar_en_lineas(self, texto: str) -> bool:
        """Lleva el cursor a la siguiente línea cuyo código o descripción contiene `texto`."""
        texto = texto.strip().lower()
        if not texto:
            return False
        total = len(self.lineas)
        for paso in range(1, total + 1):
            i = (self.fila + paso) % total  # empieza después de la fila actual y da la vuelta
            linea = self.lineas[i]
            if linea and (texto in linea[0].codigo.lower() or texto in linea[0].nombre.lower()):
                self._ir_a(i)
                return True
        return False

    def enfocar(self):
        self._ir_a(self.fila)

    def limpiar(self):
        self.lineas.clear()
        self.fila = 0
        self._borrador = (0, "")
        self._refrescar()

    # ---- Teclas ----
    def _vacia(self, fila: int) -> bool:
        return fila >= len(self.lineas) or self.lineas[fila] is None

    def _tecla(self, accion: str, texto: str):  # 🟠 CONSULTA 2: decide qué hacer con la tecla
        if self._vacia(self.fila):
            self._borrador = (self.fila, texto)
        if accion == "buscar":
            self._buscar(texto.strip())
        elif accion == "inventario":
            cantidad, termino = separar_cantidad(texto.strip())
            patron = termino if "%" in termino else f"{termino}%"
            self._elegir(cantidad, patron)
        elif accion == "borrar":
            # Vacía la fila (no la quita): el cursor se queda ahí para escribir otro código
            if not self._vacia(self.fila):
                self.lineas[self.fila] = None  # 🟠 Shift+F6: vacía la fila
            self._borrador = (self.fila, "")
            self._refrescar()
        elif accion in ("arriba", "abajo"):
            self.fila += -1 if accion == "arriba" else 1
            self._refrescar()

    def _buscar(self, texto: str):  # 🟠 CONSULTA 3: separa cantidad y código
        if not texto:
            if self.fila < len(self.lineas):
                self.fila += 1
            self._refrescar()
            return
        cantidad, termino = separar_cantidad(texto)
        try:
            exactos = self.controller.por_codigo(termino)  # 🟠 CONSULTA 3a: código exacto
            if len(exactos) == 1:
                self._poner(exactos[0], cantidad)
                return
            # No es un código exacto: buscar por "empieza con" y luego "contiene"
            patron = f"{termino}%"
            resultados = self.controller.buscar(patron)  # 🟠 CONSULTA 3b: por nombre
            if not resultados:
                patron = f"%{termino}%"
                resultados = self.controller.buscar(patron)
        except OdooError as e:
            QMessageBox.critical(self, "Error", str(e))
            self._refrescar()
            return

        if not resultados:
            QMessageBox.warning(self, "Artículo", f"No existe ningún artículo con «{termino}».")
            self._refrescar()
        elif len(resultados) == 1:
            self._poner(resultados[0], cantidad)
        else:
            self._elegir(cantidad, patron, resultados)

    def _elegir(self, cantidad: float, patron: str, resultados=None):
        dialogo = ArticulosDialog(self.controller, patron, resultados, self)
        if dialogo.exec() and dialogo.seleccionado:
            self._poner(dialogo.seleccionado, cantidad)
        else:
            self._refrescar()

    def _poner(self, p: Producto, cantidad: float):  # 🟠 CONSULTA 8: llena la fila
        if self.fila < len(self.lineas):
            self.lineas[self.fila] = (p, cantidad)
        else:
            self.lineas.append((p, cantidad))
        self._borrador = (0, "")
        self.fila = len(self.lineas)  # salta a la fila en blanco del final
        self._refrescar()
