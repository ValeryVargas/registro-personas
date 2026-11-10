"""Validaciones de entrada (campos obligatorios, formatos, reglas de negocio)."""
import re
from datetime import date
from .models import Persona, SEVERIDADES

RE_CEDULA = re.compile(r"^\d{9}$")
RE_TEL = re.compile(r"^(\+506)?\d{8}$")


class ValidacionError(Exception):
    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__("; ".join(self.errores))


def limpiar_cedula(c: str) -> str:
    return re.sub(r"[\s-]", "", c or "")


def limpiar_telefono(t: str) -> str:
    return re.sub(r"[\s-]", "", t or "")


def validar_persona(p: Persona, hoy: date | None = None) -> list:
    hoy = hoy or date.today()
    e = []
    if not RE_CEDULA.match(limpiar_cedula(p.cedula)):
        e.append("La cédula debe tener 9 dígitos.")
    if not p.nombre.strip():
        e.append("El nombre es obligatorio.")
    if not p.apellidos.strip():
        e.append("Los apellidos son obligatorios.")
    try:
        nac = date.fromisoformat(p.fecha_nacimiento)
        if nac > hoy:
            e.append("La fecha de nacimiento no puede ser futura.")
        elif p.edad(hoy) < 18:
            e.append("La persona debe ser mayor de edad (18 años o más).")
    except ValueError:
        e.append("Fecha de nacimiento inválida (use AAAA-MM-DD).")
    if p.telefono and not RE_TEL.match(limpiar_telefono(p.telefono)):
        e.append("Teléfono inválido (8 dígitos, opcional +506).")
    if len(p.contactos) == 0:
        e.append("Debe registrar al menos un contacto de emergencia.")
    for i, c in enumerate(p.contactos, 1):
        if not c.nombre.strip() or not c.parentesco.strip():
            e.append(f"Contacto {i}: nombre y parentesco son obligatorios.")
        if not RE_TEL.match(limpiar_telefono(c.telefono)):
            e.append(f"Contacto {i}: teléfono inválido.")
        if c.prioridad < 1:
            e.append(f"Contacto {i}: la prioridad debe ser 1 o mayor.")
    for i, c in enumerate(p.condiciones, 1):
        if not c.descripcion.strip():
            e.append(f"Condición {i}: la descripción es obligatoria.")
        if c.severidad not in SEVERIDADES:
            e.append(f"Condición {i}: severidad no válida.")
    for i, m in enumerate(p.medicamentos, 1):
        if not m.nombre.strip() or not m.dosis.strip():
            e.append(f"Medicamento {i}: nombre y dosis son obligatorios.")
    return e
