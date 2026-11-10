"""Clases del dominio (POO): Persona, Contacto, Condicion, Medicamento."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from .structures import ListaDoble, normalizar

SEVERIDADES = ("leve", "moderada", "grave")


@dataclass
class Contacto:
    nombre: str
    parentesco: str
    telefono: str
    prioridad: int = 1


@dataclass
class Condicion:
    descripcion: str
    severidad: str = "leve"


@dataclass
class Medicamento:
    nombre: str
    dosis: str
    frecuencia: str = ""


@dataclass
class Persona:
    cedula: str
    nombre: str
    apellidos: str
    fecha_nacimiento: str
    telefono: str = ""
    direccion: str = ""
    activo: bool = True
    id: int | None = None
    contactos: ListaDoble = field(default_factory=ListaDoble)
    condiciones: list = field(default_factory=list)
    medicamentos: list = field(default_factory=list)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellidos}"

    @property
    def clave_orden(self) -> str:
        return normalizar(f"{self.apellidos} {self.nombre}")

    def edad(self, hoy: date | None = None) -> int:
        hoy = hoy or date.today()
        n = date.fromisoformat(self.fecha_nacimiento)
        return hoy.year - n.year - ((hoy.month, hoy.day) < (n.month, n.day))

    def agregar_contacto(self, c: Contacto):
        self.contactos.insertar_ordenado(c, clave=lambda x: x.prioridad)

    def to_dict(self) -> dict:
        return {
            "cedula": self.cedula, "nombre": self.nombre, "apellidos": self.apellidos,
            "fecha_nacimiento": self.fecha_nacimiento, "telefono": self.telefono,
            "direccion": self.direccion, "activo": self.activo,
            "contactos": [vars(c).copy() for c in self.contactos],
            "condiciones": [vars(c).copy() for c in self.condiciones],
            "medicamentos": [vars(m).copy() for m in self.medicamentos],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Persona":
        p = cls(d["cedula"], d["nombre"], d["apellidos"], d["fecha_nacimiento"],
                d.get("telefono", ""), d.get("direccion", ""), d.get("activo", True),
                d.get("id"))
        for c in d.get("contactos", []):
            p.agregar_contacto(Contacto(**c))
        p.condiciones = [Condicion(**c) for c in d.get("condiciones", [])]
        p.medicamentos = [Medicamento(**m) for m in d.get("medicamentos", [])]
        return p
