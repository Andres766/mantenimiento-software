"""Reglas de negocio de NotasQA (escala colombiana 0.0 - 5.0)."""
from decimal import Decimal, ROUND_HALF_UP

NOTA_MIN = Decimal("0.0")
NOTA_MAX = Decimal("5.0")
NOTA_APROBATORIA = Decimal("3.0")
NOTA_EXCELENTE = Decimal("4.6")
PESOS = (Decimal("0.30"), Decimal("0.30"), Decimal("0.40"))  # corte 1, 2, 3


def _a_decimal(nota) -> Decimal:
    """Valida tipo y rango; devuelve la nota como Decimal (evita errores de float)."""
    if isinstance(nota, bool) or not isinstance(nota, (int, float)):
        raise TypeError("La nota debe ser numérica.")
    valor = Decimal(str(nota))
    if valor < NOTA_MIN or valor > NOTA_MAX:
        raise ValueError("La nota debe estar entre 0.0 y 5.0.")
    return valor


def redondear(valor: Decimal) -> Decimal:
    """Redondeo institucional a 1 decimal, mitad hacia arriba (2.95 -> 3.0)."""
    return valor.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


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
