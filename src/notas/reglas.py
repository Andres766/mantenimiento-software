"""Reglas de negocio de NotasQA (escala colombiana 0.0 - 5.0).

Reglas del proyecto (ajustables al reglamento estudiantil vigente):
  - Definitiva = 30 % corte 1 + 30 % corte 2 + 40 % corte 3, redondeo a 1 decimal mitad hacia arriba.
  - REPROBADO < 3.0 <= APROBADO < 4.6 <= EXCELENTE.
  - Habilitación: solo si la definitiva está entre 2.0 y 2.9. Si la nota de habilitación es >= 3.0
    la definitiva queda en 3.0; si no, queda la mayor de las dos (sigue reprobado).
  - Promedio del semestre ponderado por créditos (1 a 10), redondeado a 2 decimales.
"""
from decimal import Decimal, ROUND_HALF_UP

NOTA_MIN = Decimal("0.0")
NOTA_MAX = Decimal("5.0")
NOTA_APROBATORIA = Decimal("3.0")
NOTA_EXCELENTE = Decimal("4.6")
NOTA_MIN_HABILITACION = Decimal("2.0")
PESOS = (Decimal("0.30"), Decimal("0.30"), Decimal("0.40"))  # corte 1, 2, 3
CREDITOS_MIN = 1
CREDITOS_MAX = 10


def _a_decimal(nota) -> Decimal:
    """Valida tipo y rango; devuelve la nota como Decimal (evita errores de float)."""
    if isinstance(nota, bool) or not isinstance(nota, (int, float)):
        raise TypeError("La nota debe ser numérica.")
    valor = Decimal(str(nota))
    if valor < NOTA_MIN or valor > NOTA_MAX:
        raise ValueError("La nota debe estar entre 0.0 y 5.0.")
    return valor


def redondear(valor: Decimal, decimales: str = "0.1") -> Decimal:
    """Redondeo institucional mitad hacia arriba (2.95 -> 3.0)."""
    return valor.quantize(Decimal(decimales), rounding=ROUND_HALF_UP)


def clasificar_nota(nota) -> str:
    valor = redondear(_a_decimal(nota))
    if valor < NOTA_APROBATORIA:
        return "REPROBADO"
    if valor < NOTA_EXCELENTE:
        return "APROBADO"
    return "EXCELENTE"


def calcular_definitiva(corte1, corte2, corte3) -> float:
    cortes = [_a_decimal(c) for c in (corte1, corte2, corte3)]
    total = sum(c * p for c, p in zip(cortes, PESOS))
    return float(redondear(total))


def puede_habilitar(definitiva) -> bool:
    valor = redondear(_a_decimal(definitiva))
    return NOTA_MIN_HABILITACION <= valor < NOTA_APROBATORIA


def aplicar_habilitacion(definitiva, nota_habilitacion) -> float:
    if not puede_habilitar(definitiva):
        raise PermissionError("Solo se habilita con definitiva entre 2.0 y 2.9.")
    habilitacion = redondear(_a_decimal(nota_habilitacion))
    # Mutante equivalente: con '>' el resultado es idéntico (max(def, 3.0) = 3.0), por eso se excluye.
    if habilitacion >= NOTA_APROBATORIA:  # pragma: no mutate
        return float(NOTA_APROBATORIA)
    return float(max(redondear(_a_decimal(definitiva)), habilitacion))


def validar_creditos(creditos) -> int:
    if isinstance(creditos, bool) or not isinstance(creditos, int):
        raise TypeError("Los créditos deben ser un número entero.")
    if creditos < CREDITOS_MIN or creditos > CREDITOS_MAX:
        raise ValueError("Los créditos deben estar entre 1 y 10.")
    return creditos


def promedio_ponderado(materias) -> float:
    """materias: lista de tuplas (nota_definitiva, creditos)."""
    if not materias:
        raise ValueError("No hay materias para promediar.")
    suma = Decimal("0")
    total_creditos = 0
    for nota, creditos in materias:
        suma += _a_decimal(nota) * validar_creditos(creditos)
        total_creditos += creditos
    return float(redondear(suma / total_creditos, "0.01"))
