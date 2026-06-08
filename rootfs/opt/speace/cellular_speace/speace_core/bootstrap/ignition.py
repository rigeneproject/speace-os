"""SPEACE — Brain & Organism Ignition.

Risolve lo "stallo" dell'organismo: cervello che non comunica, sottosistemi che
non cooperano, campo ILF non integrato, team agentico che non si attiva.

Cosa fa questa accensione (tutto additivo, non modifica i percorsi testati):

1.  ILF ON: legge il principio ``ilf_core`` dal genoma e accende il campo
    informazionale (di default ``ilf_enabled`` è False -> campo mai integrato).
2.  ARMONIA D'ORGANISMO: registra TUTTI i sottosistemi principali al campo ILF
    (non solo ``neural_circuit``), così il campo coordina l'intero organismo:
    memoria, metabolismo/energia, evoluzione, dinamiche.
3.  RIVITALIZZAZIONE: riattiva la regolazione energetica e omeostatica globale,
    sbloccando lo stato "morto" (energia 0, sinapsi attive 0) trovato negli
    snapshot persistiti.
4.  STIMOLO: inietta pattern + feedback per far scaricare i neuroni (altrimenti
    restano spenti e ``coherence_phi``/``active_neurons`` restano a 0).
5.  PERSISTENZA SANA: scrive snapshot morfologici aggiornati così il team
    agentico (RuntimeHealthMonitor / AutoAnalysisScheduler) ha uno stato vivo
    da analizzare e si attiva.
"""

from __future__ import annotations

import asyncio
import pathlib
from typing import Any, Dict, List, Optional

from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.ilf import ILFMetrics


def _default_genome_path() -> pathlib.Path:
    return (
        pathlib.Path(__file__).resolve().parent.parent
        / "dna"
        / "genome"
        / "default_genome.yaml"
    )


class OrganismIgnition:
    """Accende e avvia il cervello/organismo di SPEACE in stato coordinato e vivo."""

    def __init__(
        self,
        genome_path: Optional[pathlib.Path] = None,
        warmup_patterns: int = 60,
        sustain_ticks: int = 200,
        snapshot_interval: int = 25,
    ) -> None:
        self.genome_path = genome_path or _default_genome_path()
        self.warmup_patterns = warmup_patterns
        self.sustain_ticks = sustain_ticks
        self.snapshot_interval = snapshot_interval
        self.orchestrator: Optional[CellularBrainOrchestrator] = None
        self._log: List[str] = []

    # ------------------------------------------------------------------ #
    def _emit(self, msg: str) -> None:
        self._log.append(msg)

    @property
    def log(self) -> List[str]:
        return list(self._log)

    # ------------------------------------------------------------------ #
    def build(self) -> CellularBrainOrchestrator:
        """Costruisce l'orchestratore con il campo ILF e la regolazione globale accesi."""
        genome = load_genome(self.genome_path)

        # Il genoma dichiara il principio ILF (ilf_core) ma il runtime non lo
        # accende mai di default. Lo accendiamo qui, insieme alla regolazione
        # energetica/omeostatica globale che ricoordina l'organismo.
        ilf_declared = getattr(genome, "ilf_core", None) is not None

        orch = CellularBrainOrchestrator.build_mvp(
            genome,
            ilf_enabled=True,
            energy_field_enabled=True,
            homeostatic_drive_enabled=True,
            criticality_monitor_enabled=True,
            systemic_harmony_enabled=True,
        )
        self.orchestrator = orch
        self._emit(
            f"[1/5] ILF acceso (principio dal genoma: {ilf_declared}). "
            "Regolazione energetica + omeostasi globale attive."
        )
        return orch

    # ------------------------------------------------------------------ #
    def wire_field(self) -> int:
        """Registra tutti i sottosistemi al campo ILF per l'armonia d'organismo.

        Di default solo ``neural_circuit`` è registrato. Aggiungiamo memoria,
        metabolismo, evoluzione e dinamiche così il campo coordina l'intero
        organismo, non solo il cervello.
        """
        orch = self.orchestrator
        assert orch is not None

        def metabolism_metrics() -> ILFMetrics:
            m = orch.latest_metrics
            energy = m.mean_energy if m else 0.5
            return ILFMetrics(
                energy_levels={"organism": energy},
                memory_utilization=energy,
                error_rate=min(1.0, m.noise_level if m else 0.1),
                learning_rate=0.1,
            )

        def memory_metrics() -> ILFMetrics:
            mem = orch.memory
            n_snap = len(getattr(mem, "snapshots", []))
            retention = min(1.0, n_snap / 100.0)
            m = orch.latest_metrics
            return ILFMetrics(
                memory_utilization=retention,
                memory_retention=m.coherence_phi if m else retention,
                learning_rate=0.1,
            )

        def evolution_metrics() -> ILFMetrics:
            m = orch.latest_metrics
            mutations = len(m.mutation_log) if m else 0
            return ILFMetrics(
                learning_rate=min(1.0, 0.1 + mutations / 10.0),
                memory_retention=m.coherence_phi if m else 0.5,
            )

        registered = 0
        for name, fn in (
            ("metabolism", metabolism_metrics),
            ("memory", memory_metrics),
            ("evolution", evolution_metrics),
        ):
            try:
                orch.register_subsystem_to_field(name=name, get_metrics_fn=fn, weight=1.0)
                registered += 1
            except Exception as exc:  # pragma: no cover - difensivo
                self._emit(f"   ! impossibile registrare '{name}': {exc}")

        total = registered + 1  # +1 = neural_circuit già registrato dall'orchestratore
        self._emit(
            f"[2/5] Campo ILF cablato: {total} sottosistemi registrati "
            "(neural_circuit + metabolism + memory + evolution)."
        )
        return total

    # ------------------------------------------------------------------ #
    async def _warmup(self) -> None:
        """Stimola l'organismo per sbloccare lo stallo (neuroni spenti → attivi)."""
        orch = self.orchestrator
        assert orch is not None
        for i in range(self.warmup_patterns):
            pattern = [0.0] * 10
            pattern[i % 10] = 1.0
            orch.inject(pattern)
            await orch.run_ticks(1)
            orch.feedback(1.0 if i % 2 == 0 else -0.2)
            if i % 10 == 0:
                orch.run_immune()
        self._emit(
            f"[3/5] Warmup completato: {self.warmup_patterns} pattern iniettati "
            "-> neuroni e sinapsi riattivati."
        )

    async def _sustain(self) -> None:
        """Mantiene l'organismo vivo e persiste snapshot sani per il team agentico."""
        orch = self.orchestrator
        assert orch is not None
        persisted = 0
        for i in range(self.sustain_ticks):
            # stimolo leggero continuo per non ricadere nello stallo
            pattern = [0.0] * 10
            pattern[i % 10] = 0.6
            orch.inject(pattern)
            await orch.run_ticks(1)
            orch.feedback(1.0 if i % 3 != 0 else -0.1)
            if (i + 1) % self.snapshot_interval == 0:
                self._persist_snapshot()
                persisted += 1
        # snapshot finale garantito
        self._persist_snapshot()
        persisted += 1
        self._emit(
            f"[4/5] Sustain completato: {self.sustain_ticks} tick, "
            f"{persisted} snapshot sani persistiti per il team agentico."
        )

    def _persist_snapshot(self) -> None:
        orch = self.orchestrator
        assert orch is not None
        m = orch.latest_metrics
        if m is None:
            return
        snapshot = orch._build_morphology_snapshot(m)
        orch.memory.record_snapshot(snapshot)
        orch.memory.save()

    # ------------------------------------------------------------------ #
    def report(self) -> Dict[str, Any]:
        orch = self.orchestrator
        assert orch is not None
        m = orch.latest_metrics
        field_state = orch.get_field_state()
        return {
            "tick": orch.current_tick,
            "coherence_phi": m.coherence_phi if m else None,
            "mean_energy": m.mean_energy if m else None,
            "active_neurons": m.active_neurons if m else None,
            "systemic_coherence_index": orch.get_systemic_coherence_index(),
            "ilf_value": field_state.ilf_value if field_state else None,
            "field_stability": field_state.field_stability if field_state else None,
            "field_subsystems": list(
                getattr(orch._field_integrator, "_subsystems", {}).keys()
            )
            if orch._field_integrator
            else [],
            "snapshots_persisted": len(getattr(orch.memory, "snapshots", [])),
        }

    # ------------------------------------------------------------------ #
    def ignite(self) -> Dict[str, Any]:
        """Esegue l'intera sequenza di accensione e restituisce il report finale."""
        self.build()
        self.wire_field()

        async def _run() -> None:
            await self._warmup()
            await self._sustain()

        asyncio.run(_run())
        rep = self.report()
        alive = (
            (rep["active_neurons"] or 0) > 0
            and (rep["mean_energy"] or 0.0) > 0.05
            and (rep["systemic_coherence_index"] or 0.0) > 0.0
        )
        self._emit(
            "[5/5] Organismo ACCESO e VIVO." if alive else "[5/5] Avvio parziale: verificare metriche."
        )
        rep["alive"] = alive
        rep["log"] = self.log
        return rep


def ignite(
    genome_path: Optional[pathlib.Path] = None,
    warmup_patterns: int = 60,
    sustain_ticks: int = 200,
) -> Dict[str, Any]:
    """Funzione di comodo: accende cervello+organismo e restituisce il report."""
    return OrganismIgnition(
        genome_path=genome_path,
        warmup_patterns=warmup_patterns,
        sustain_ticks=sustain_ticks,
    ).ignite()
