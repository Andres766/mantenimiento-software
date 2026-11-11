"""Frente 1: habilitación y promedio por créditos (EP + BVA)."""
import re

import pytest

from src.notas.reglas import aplicar_habilitacion, promedio_ponderado, puede_habilitar, validar_creditos


def exacto(mensaje: str) -> str:
    """Patrón que exige el mensaje completo (mata los mutantes que alteran el texto)."""
    return f"^{re.escape(mensaje)}$"


@pytest.mark.parametrize(
    "definitiva, esperado",
    [
        (1.9, False),  # off point inferior
        (2.0, True),   # on point inferior
        (2.5, True),   # clase válida
        (2.9, True),   # borde superior
        (3.0, False),  # ya aprobó: no habilita
        (0.0, False),
    ],
)
def test_puede_habilitar_fronteras(definitiva, esperado):
    assert puede_habilitar(definitiva) is esperado


@pytest.mark.parametrize(
    "definitiva, habilitacion, final",
    [
        (2.5, 3.0, 3.0),   # on point: aprueba y queda en 3.0
        # Nota: cambiar ">=" por ">" en esta regla produce un MUTANTE EQUIVALENTE
        # (con 3.0 ambas versiones devuelven 3.0); ninguna prueba puede distinguirlos.
        (2.5, 5.0, 3.0),   # la habilitación nunca sube por encima de 3.0
        (2.5, 2.9, 2.9),   # off point: reprueba, queda la mayor
        (2.8, 2.1, 2.8),   # habilitación peor: se conserva la definitiva
    ],
)
def test_aplicar_habilitacion(definitiva, habilitacion, final):
    assert aplicar_habilitacion(definitiva, habilitacion) == final


@pytest.mark.parametrize("definitiva", [1.9, 3.0, 4.6])
def test_habilitacion_no_permitida(definitiva):
    with pytest.raises(PermissionError, match=exacto("Solo se habilita con definitiva entre 2.0 y 2.9.")):
        aplicar_habilitacion(definitiva, 4.0)


def test_habilitacion_con_nota_invalida():
    with pytest.raises(ValueError):
        aplicar_habilitacion(2.5, 5.1)


@pytest.mark.parametrize("creditos", [1, 3, 10])
def test_creditos_validos(creditos):
    assert validar_creditos(creditos) == creditos


@pytest.mark.parametrize("creditos, excepcion, mensaje", [
    (0, ValueError, "Los créditos deben estar entre 1 y 10."),
    (11, ValueError, "Los créditos deben estar entre 1 y 10."),
    (2.5, TypeError, "Los créditos deben ser un número entero."),
    (True, TypeError, "Los créditos deben ser un número entero.")])
def test_creditos_invalidos(creditos, excepcion, mensaje):
    with pytest.raises(excepcion, match=exacto(mensaje)):
        validar_creditos(creditos)


def test_promedio_ponderado_por_creditos():
    # (4.0*4 + 3.0*3 + 2.0*1) / 8 = 27/8 = 3.375 -> 3.38 (mitad hacia arriba)
    assert promedio_ponderado([(4.0, 4), (3.0, 3), (2.0, 1)]) == 3.38


def test_promedio_una_materia():
    assert promedio_ponderado([(3.5, 2)]) == 3.5


def test_promedio_sin_materias():
    with pytest.raises(ValueError, match=exacto("No hay materias para promediar.")):
        promedio_ponderado([])
