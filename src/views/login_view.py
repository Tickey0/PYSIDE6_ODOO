from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)


class LoginView(QDialog):
    def __init__(self, servidor: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ingreso a Odoo")
        self.setMinimumWidth(320)
        raiz = QVBoxLayout(self)
        raiz.addWidget(QLabel(f"Servidor: {servidor}"))

        form = QFormLayout()
        self.usuario = QLineEdit("admin")
        self.password = QLineEdit("admin")
        self.password.setEchoMode(QLineEdit.Password)
        form.addRow("Usuario", self.usuario)
        form.addRow("Contraseña", self.password)
        raiz.addLayout(form)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Ok).setText("Ingresar")
        botones.button(QDialogButtonBox.Cancel).setText("Salir")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        raiz.addWidget(botones)
        self.password.setFocus()
        self.password.selectAll()
