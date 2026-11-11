import re

import pytest

from src.notas.reglas import calcular_definitiva, clasificar_nota


# Semana 1: patrón AAA explícito
def test_nota_aprobatoria_exacta_es_aprobado():
    # Arrange
    nota = 3.0
    # Act
    resultado = clasificar_nota(nota)
    # Assert
    assert resultado == "APROBADO"


# Semana 2: Partición de Equivalencia + BVA con parametrize (8 fronteras del reto)
@pytest.mark.parametrize(
    "nota, esperado",
    [
        (0.0, "REPROBADO"),   # límite inferior válido
        (2.9, "REPROBADO"),   # justo debajo de aprobar
        (3.0, "APROBADO"),    # on point aprobar
        (4.5, "APROBADO"),    # borde superior de aprobado
        (4.6, "EXCELENTE"),   # on point excelente
        (5.0, "EXCELENTE"),   # límite superior válido
    ],
)
def test_clasificar_nota_fronteras(nota, esperado):
    assert clasificar_nota(nota) == esperado


@pytest.mark.parametrize(
    "entrada, excepcion, mensaje",
    [
        (-0.1, ValueError, "La nota debe estar entre 0.0 y 5.0."),
        (5.1, ValueError, "La nota debe estar entre 0.0 y 5.0."),
        ("3.0", TypeError, "La nota debe ser numérica."),
        (None, TypeError, "La nota debe ser numérica."),
        (True, TypeError, "La nota debe ser numérica."),
    ],
)
def test_clasificar_nota_entradas_destructivas(entrada, excepcion, mensaje):
    # match= con ^...$ verifica el mensaje COMPLETO: lo exige la prueba de mutación (Frente 1)
    with pytest.raises(excepcion, match=f"^{re.escape(mensaje)}$"):
        clasificar_nota(entrada)


# Ponderación 30/30/40 y redondeo institucional (el bug clásico de round() con floats)
@pytest.mark.parametrize(
    "c1, c2, c3, definitiva, estado",
    [
        (2.0, 2.6, 3.9, 2.9, "REPROBADO"),  # 2.94 -> 2.9 (off point)
        (2.0, 2.5, 4.0, 3.0, "APROBADO"),   # 2.95 -> 3.0 (on point)
        (0.4, 4.1, 4.0, 3.0, "APROBADO"),   # con float daría 2.9499... -> 2.9: reprobaría
        (4.0, 4.5, 5.0, 4.6, "EXCELENTE"),  # con float round(4.55, 1) -> 4.5: no sería excelente
        (5.0, 5.0, 5.0, 5.0, "EXCELENTE"),
        (0.0, 0.0, 0.0, 0.0, "REPROBADO"),
    ],
)
def test_calcular_definitiva_redondeo(c1, c2, c3, definitiva, estado):
    resultado = calcular_definitiva(c1, c2, c3)
    assert resultado == definitiva
    assert clasificar_nota(resultado) == estado
