from typing import Optional, Dict, Any, List
import math


class CoherenceMetrics:
    """Metriche per valutare la coerenza dell'organismo."""

    @staticmethod
    def compute_functional_integration(
        region_outputs: Dict[str, float],
        connectivity_matrix: Optional[Dict[str, List[str]]] = None,
    ) -> float:
        """Misura quanto le regioni lavorano in modo integrato.

        Se connectivity_matrix è fornito, pesa le connessioni.
        Altrimenti usa solo la varianza dei outputs.
        """
        if not region_outputs:
            return 0.0

        values = list(region_outputs.values())
        mean = sum(values) / len(values)

        # Coesione: quanto i valori sono vicini alla media
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        cohesion = max(0.0, 1.0 - math.sqrt(variance) * 2)

        if connectivity_matrix:
            # Se abbiamo la matrice, valutiamo anche la sincronia
            sync_score = 0.0
            pairs = 0
            for source, targets in connectivity_matrix.items():
                if source not in region_outputs:
                    continue
                source_val = region_outputs[source]
                for target in targets:
                    if target in region_outputs:
                        # Due regioni sincronizzate hanno valori simili
                        diff = abs(source_val - region_outputs[target])
                        sync_score += max(0.0, 1.0 - diff)
                        pairs += 1
            if pairs > 0:
                sync_score /= pairs
            return (cohesion + sync_score) / 2

        return cohesion

    @staticmethod
    def compute_internal_diversity(
        cell_states: Dict[str, float],
        cell_types: Optional[Dict[str, str]] = None,
    ) -> float:
        """Misura la diversità interna dell'organismo.

        Se cell_types è fornito, normalizza per tipo per evitare
        bias verso tipi con più cellule.
        """
        if not cell_states:
            return 0.0

        if not cell_types:
            # Diversità naive: entropia dei valori
            values = sorted(cell_states.values())
            if len(values) < 2:
                return 0.0
            range_val = max(values) - min(values)
            return min(1.0, range_val)

        # Raggruppa per tipo e calcola diversità media
        by_type: Dict[str, List[float]] = {}
        for cid, state in cell_states.items():
            ctype = cell_types.get(cid, "unknown")
            by_type.setdefault(ctype, []).append(state)

        if len(by_type) < 2:
            return 0.0

        diversities = []
        for ctype, states in by_type.items():
            if len(states) >= 2:
                mean = sum(states) / len(states)
                variance = sum((s - mean) ** 2 for s in states) / len(states)
                diversity = min(1.0, math.sqrt(variance) * 2)
                diversities.append(diversity)

        return sum(diversities) / len(diversities) if diversities else 0.0

    @staticmethod
    def compute_cognitive_stability(
        ilf_history: List[float], window: int = 10
    ) -> float:
        """Misura la stabilità cognitiva tramite la volatilità dell'ILF.

        Usa una finestra mobile per calcolare la variazione percentuale.
        """
        if len(ilf_history) < 2:
            return 1.0  # Nessuna storia = stabile per default

        # Usa gli ultimi `window` valori
        recent = ilf_history[-window:]

        if len(recent) < 2:
            return 1.0

        # Variazione percentuale media
        variations = []
        for i in range(1, len(recent)):
            prev = max(recent[i - 1], 0.001)  # Evita divisione per zero
            variation = abs(recent[i] - recent[i - 1]) / prev
            variations.append(variation)

        avg_variation = sum(variations) / len(variations)
        stability = max(0.0, 1.0 - avg_variation * 5)  # Scala: 20% variazione = 0 stab
        return stability

    @staticmethod
    def compute_homeostatic_balance(
        energy_levels: Dict[str, float],
        target_energy: float = 0.7,
    ) -> float:
        """Misura quanto l'energia è bilanciata tra le regioni."""
        if not energy_levels:
            return 0.0

        values = list(energy_levels.values())
        mean = sum(values) / len(values)

        # Deviazione dalla target
        deviation = abs(mean - target_energy)

        # Bilanciamento: quanto sono uniformi
        if len(values) >= 2:
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            balance = max(0.0, 1.0 - math.sqrt(variance) * 2)
        else:
            balance = 1.0

        # Combina deviazione e bilanciamento
        target_score = max(0.0, 1.0 - deviation * 2)
        return (balance + target_score) / 2

    @staticmethod
    def compute_signal_synchrony(
        signal_trains: Dict[str, List[float]], window_ms: float = 10.0
    ) -> float:
        """Misura la sincronia tra treni di segnali.

        Approccio semplificato: conta quante coppie di segnali
        hanno picchi nello stesso intervallo.
        """
        if len(signal_trains) < 2:
            return 1.0

        # Estrai i picchi (valori > soglia locale)
        def extract_peaks(values: List[float], threshold: float = 0.5) -> List[int]:
            peaks = []
            for i, v in enumerate(values):
                if v > threshold:
                    prev = values[i - 1] if i > 0 else v
                    next_v = values[i + 1] if i < len(values) - 1 else v
                    if v >= prev and v >= next_v:
                        peaks.append(i)
            return peaks

        peak_lists = {}
        for name, train in signal_trains.items():
            peak_lists[name] = extract_peaks(train)

        # Calcola sincronia pairwise
        names = list(peak_lists.keys())
        sync_score = 0.0
        pairs = 0

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                peaks_i = set(peak_lists[names[i]])
                peaks_j = set(peak_lists[names[j]])

                if not peaks_i or not peaks_j:
                    continue

                # Conta picchi sincronizzati (distanza < window)
                sync = 0
                for p_i in peaks_i:
                    for p_j in peaks_j:
                        if abs(p_i - p_j) <= window_ms:
                            sync += 1

                # Normalizza per il minimo dei picchi
                min_peaks = min(len(peaks_i), len(peaks_j))
                if min_peaks > 0:
                    sync_score += sync / min_peaks
                    pairs += 1

        return sync_score / pairs if pairs > 0 else 0.0