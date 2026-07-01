"""Reglas de validacion y alertas sobre las filas del reporte.

Una regla es un texto tipo "errors>5" o "downtime_min>=10". Se evalua
fila a fila; cada fila que la cumple genera una alerta. Determinista.
"""
from __future__ import annotations

from dataclasses import dataclass

from .reader import _to_number

_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


@dataclass
class Rule:
    metric: str
    op: str
    value: float
    raw: str


def parse_rule(text: str) -> Rule:
    """Parsea 'columna OP valor' (ej. 'errors>5'). OP: > >= < <= == !=."""
    s = str(text).strip()
    for op in (">=", "<=", "==", "!=", ">", "<"):
        if op in s:
            left, right = s.split(op, 1)
            metric = left.strip()
            num = _to_number(right.strip())
            if not metric or num is None:
                raise ValueError(
                    f"Regla invalida: '{text}'. Formato: 'columna>valor' (ej. 'errors>5')."
                )
            return Rule(metric, op, num, s)
    raise ValueError(
        f"Regla invalida: '{text}'. Falta operador (>, >=, <, <=, ==, !=)."
    )


def evaluate_alerts(headers: list[str], rows: list[dict], rules) -> list[dict]:
    """Devuelve la lista de alertas: filas que cumplen alguna regla."""
    parsed = [r if isinstance(r, Rule) else parse_rule(r) for r in rules]
    for r in parsed:
        if r.metric not in headers:
            raise ValueError(
                f"La columna de la regla '{r.metric}' no existe. Disponibles: {headers}"
            )
    alerts: list[dict] = []
    for i, row in enumerate(rows):
        for r in parsed:
            actual = _to_number(row.get(r.metric))
            if actual is None:
                continue
            if _OPS[r.op](actual, r.value):
                alerts.append({
                    "index": i,
                    "metric": r.metric,
                    "op": r.op,
                    "threshold": r.value,
                    "value": actual,
                    "row": row,
                    "rule": r.raw,
                })
    return alerts
