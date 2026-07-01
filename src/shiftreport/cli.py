"""Interfaz de linea de comandos del ShiftReport Generator."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import __version__
from .reader import load_rows
from .report import summarize, write_excel, write_html


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="shiftreport",
        description="Convierte un CSV/Excel de turno en un reporte (Excel + HTML) y lo envia.",
    )
    p.add_argument("input", help="Ruta al archivo de entrada (.csv o .xlsx)")
    p.add_argument("-o", "--output", default="outputs", help="Carpeta de salida (def: outputs)")
    p.add_argument("-t", "--title", default="Reporte de turno", help="Titulo del reporte")
    p.add_argument("-g", "--group-by", default=None, help="Columna por la que agrupar")
    p.add_argument("-m", "--metric", action="append", dest="metrics",
                   help="Columna numerica a sumar (repetible). Si se omite, se autodetectan.")
    p.add_argument("-a", "--alert", action="append", dest="alerts",
                   help="Regla de alerta 'columna>valor' (repetible). Ej: -a \"errors>5\".")
    p.add_argument("--no-html", action="store_true", help="No generar HTML")
    p.add_argument("--no-excel", action="store_true", help="No generar Excel")
    p.add_argument("--email-to", action="append", dest="email_to",
                   help="Destinatario del correo (repetible). Requiere config SMTP en entorno.")
    p.add_argument("--at", default=None, metavar="HH:MM",
                   help="Programa el envio para esa hora de hoy (espera y ejecuta una vez).")
    p.add_argument("--version", action="version", version=f"shiftreport {__version__}")
    return p


def _wait_until(hhmm: str) -> None:
    try:
        target_t = datetime.strptime(hhmm, "%H:%M").time()
    except ValueError:
        raise SystemExit(f"Hora invalida '{hhmm}'. Usa formato HH:MM (ej. 14:30).")
    now = datetime.now()
    target = now.replace(hour=target_t.hour, minute=target_t.minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    wait_s = (target - now).total_seconds()
    print(f"[shiftreport] Esperando hasta {target:%Y-%m-%d %H:%M} ({int(wait_s)}s)...")
    time.sleep(wait_s)


def run(args: argparse.Namespace) -> int:
    if args.at:
        _wait_until(args.at)

    headers, rows = load_rows(args.input)
    if not rows:
        print("[shiftreport] El archivo no tiene filas de datos.", file=sys.stderr)
        return 2

    summary = summarize(
        headers, rows,
        title=args.title,
        group_by=args.group_by,
        metrics=args.metrics,
        rules=args.alerts,
    )

    out_dir = Path(args.output)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    slug = args.title.lower().replace(" ", "_")
    generated: list[Path] = []

    if not args.no_html:
        html_path = write_html(summary, out_dir / f"{slug}_{stamp}.html")
        generated.append(html_path)
        print(f"[shiftreport] HTML  -> {html_path}")

    if not args.no_excel:
        xlsx_path = write_excel(summary, rows, headers, out_dir / f"{slug}_{stamp}.xlsx")
        generated.append(xlsx_path)
        print(f"[shiftreport] Excel -> {xlsx_path}")

    n_alerts = len(summary.alerts)
    if n_alerts:
        print(f"[shiftreport] ATENCION: {n_alerts} alerta(s) detectada(s).")

    if args.email_to:
        from .emailer import EmailConfigError, send_report
        from .report import build_html
        prefix = f"[{n_alerts} alertas] " if n_alerts else ""
        try:
            send_report(
                to=args.email_to,
                subject=f"{prefix}{args.title} - {summary.generated_at}",
                html_body=build_html(summary),
                attachments=generated,
            )
            print(f"[shiftreport] Correo enviado a {', '.join(args.email_to)}")
        except EmailConfigError as e:
            print(f"[shiftreport] No se envio el correo: {e}", file=sys.stderr)
            return 3

    print(f"[shiftreport] Listo. {summary.row_count} registros procesados.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"[shiftreport] Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
