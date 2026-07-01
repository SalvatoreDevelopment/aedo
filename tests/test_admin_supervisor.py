"""Test del supervisore di processi.

Non avviamo bot o server veri: usiamo brevi processi Python "finti" come cavie,
così la logica (avvio, cattura output, stop, distinzione crash/arresto) è
verificabile in modo rapido e deterministico.
"""

from __future__ import annotations

import sys
import time

from aedo.admin.supervisor import ManagedService, ServiceSpec, ServiceState, Supervisor


def _wait(predicate, timeout=8.0, interval=0.05):
    """Aspetta che una condizione diventi vera (o scade il timeout)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _spec_long(key="cavia"):
    # Stampa una riga (flush!) e resta vivo finché non viene fermato.
    code = "import time,sys; print('ciao dal processo', flush=True); time.sleep(60)"
    return ServiceSpec(
        key=key, label="Cavia", description="processo di prova",
        command=lambda: [sys.executable, "-c", code],
    )


def test_start_captures_output_then_stop():
    svc = ManagedService(_spec_long())
    svc.start()
    assert svc.state is ServiceState.RUNNING
    snap = svc.snapshot()
    assert snap["pid"] is not None

    # L'output del processo finisce nel ring-buffer.
    assert _wait(lambda: any("ciao dal processo" in ln for ln in svc.tail()))

    svc.stop()
    assert _wait(lambda: svc.state is ServiceState.STOPPED)
    assert svc.snapshot()["pid"] is None


def test_crash_is_reported_as_errored():
    spec = ServiceSpec(
        key="crash", label="Crash", description="esce subito con errore",
        command=lambda: [sys.executable, "-c", "import sys; sys.exit(3)"],
    )
    svc = ManagedService(spec)
    svc.start()
    # Muore da solo con codice != 0 → stato 'errored', non 'stopped'.
    assert _wait(lambda: svc.state is ServiceState.ERRORED)
    assert svc.snapshot()["exit_code"] == 3


def test_clean_exit_is_stopped_not_errored():
    spec = ServiceSpec(
        key="ok", label="Ok", description="esce subito con successo",
        command=lambda: [sys.executable, "-c", "pass"],
    )
    svc = ManagedService(spec)
    svc.start()
    assert _wait(lambda: svc.state is ServiceState.STOPPED)
    assert svc.snapshot()["exit_code"] == 0


def test_ansi_escape_codes_are_stripped_from_logs():
    # Vite & co. emettono colori ANSI: nel log devono sparire, non incollarsi.
    code = (
        r"import sys; sys.stdout.write('\x1b[32m\x1b[1mVITE\x1b[0m pronto\n'); "
        r"sys.stdout.flush()"
    )
    spec = ServiceSpec(
        key="ansi", label="Ansi", description="stampa colori",
        command=lambda: [sys.executable, "-c", code],
    )
    svc = ManagedService(spec)
    svc.start()
    assert _wait(lambda: any("VITE pronto" in ln for ln in svc.tail()))
    joined = "\n".join(svc.tail())
    assert "\x1b[" not in joined  # nessuna sequenza di escape residua
    svc.stop()


def test_unavailable_service_reports_hint():
    spec = ServiceSpec(
        key="web", label="Web", description="non avviabile",
        command=lambda: None, unavailable_hint="manca npm",
    )
    svc = ManagedService(spec)
    r = svc.start()
    assert svc.state is ServiceState.UNAVAILABLE
    assert "npm" in r["message"]


def test_supervisor_stop_all():
    sup = Supervisor([_spec_long("a"), _spec_long("b")])
    sup.get("a").start()
    sup.get("b").start()
    assert all(s["state"] == "running" for s in sup.snapshot_all())
    sup.stop_all()
    assert _wait(lambda: all(
        svc.state is ServiceState.STOPPED for svc in (sup.get("a"), sup.get("b"))
    ))
