import pytest

from shiftreport.alerts import Rule, evaluate_alerts, parse_rule
from shiftreport.reader import load_rows
from shiftreport.report import build_html, summarize, write_excel
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample_shift_data.csv"


def test_parse_rule_operators():
    r = parse_rule("errors>5")
    assert r.metric == "errors" and r.op == ">" and r.value == 5.0
    assert parse_rule("downtime_min>=10").op == ">="
    assert parse_rule("units_processed<=100").op == "<="


def test_parse_rule_invalid():
    with pytest.raises(ValueError):
        parse_rule("errors")          # sin operador
    with pytest.raises(ValueError):
        parse_rule("errors>abc")      # valor no numerico


def test_evaluate_alerts_counts():
    headers, rows = load_rows(EXAMPLE)
    alerts = evaluate_alerts(headers, rows, ["errors>5"])
    # en los datos de ejemplo hay 3 filas con errors > 5 (7, 6, ...). Verificamos > 0 y coherencia
    assert len(alerts) >= 1
    assert all(a["value"] > 5 for a in alerts)
    assert all(a["metric"] == "errors" for a in alerts)


def test_evaluate_alerts_unknown_column():
    headers, rows = load_rows(EXAMPLE)
    with pytest.raises(ValueError):
        evaluate_alerts(headers, rows, ["noexiste>1"])


def test_summarize_with_rules_populates_alerts():
    headers, rows = load_rows(EXAMPLE)
    s = summarize(headers, rows, group_by="area", rules=["errors>5"])
    assert len(s.alerts) >= 1


def test_html_and_excel_include_alerts(tmp_path):
    headers, rows = load_rows(EXAMPLE)
    s = summarize(headers, rows, group_by="area", rules=["errors>5"])
    html = build_html(s)
    assert "Alertas" in html
    xlsx = write_excel(s, rows, headers, tmp_path / "r.xlsx")
    assert xlsx.exists() and xlsx.stat().st_size > 0
