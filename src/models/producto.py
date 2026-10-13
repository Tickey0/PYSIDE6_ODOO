from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Producto(BaseModel):
    """Un registro de product.product tal como lo devuelve search_read."""
    model_config = ConfigDict(populate_by_name=True)

    # Campos que se le piden a Odoo (product.product hereda los de product.template)
    CAMPOS: ClassVar[tuple] = ("id", "display_name", "barcode", "default_code",
                     "lst_price", "uom_id", "qty_available", "taxes_id")

    id: int
    nombre: str = Field(alias="display_name")
    codigo_barras: str = Field("", alias="barcode")
    referencia: str = Field("", alias="default_code")
    precio: float = Field(0.0, alias="lst_price")
    unidad: str = Field("", alias="uom_id")
    stock: float = Field(0.0, alias="qty_available")
    impuestos: list[int] = Field(default_factory=list, alias="taxes_id")
    iva: float = 0.0  # porcentaje; lo calcula el controlador a partir de impuestos

    @field_validator("codigo_barras", "referencia", mode="before")
    @classmethod
    def vacio_si_false(cls, v):
        # Odoo devuelve False cuando un campo de texto esta vacio
        return "" if v is False else v

    @field_validator("unidad", mode="before")
    @classmethod
    def nombre_many2one(cls, v):
        # Los many2one llegan como [id, "Nombre"] o False
        return v[1] if isinstance(v, (list, tuple)) else ""

    @property
    def codigo(self) -> str:
        return self.codigo_barras or self.referencia
