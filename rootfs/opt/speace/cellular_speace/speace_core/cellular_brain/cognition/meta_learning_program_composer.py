"""Meta-Learning Program Composer (MLPC).

Learns a primitive transition model from solved tasks and uses it to guide
search in program-induction space.  Replaces blind BFS with an A*-style
priority queue informed by past successes.
"""

import heapq
import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from speace_core.cellular_brain.cognition.program_models import (
    GridTransformation,
    TransformationProgram,
    ProgramCandidate,
)

Grid = List[List[int]]


class MetaLearningProgramComposer:
    """Learns a Markov transition model over primitives and task embeddings."""

    def __init__(self) -> None:
        # Transition counts: prev -> {next: count}
        self._transition_counts: Dict[str, Counter] = defaultdict(Counter)
        self._total_from: Dict[str, int] = defaultdict(int)
        # Task feature -> list of successful programs (as list of primitive names)
        self._success_history: List[Tuple[np.ndarray, List[str]]] = []

    # ------------------------------------------------------------------ #
    # Learning from successes
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_task_features(task_pairs: List[Dict[str, Any]]) -> np.ndarray:
        """Simple feature vector describing a task."""
        if not task_pairs:
            return np.zeros(6, dtype=float)
        inp = task_pairs[0]["input"]
        if not inp:
            return np.zeros(6, dtype=float)
        h, w = len(inp), len(inp[0])
        flat = [c for row in inp for c in row]
        colors = set(flat)
        # Approximate object count via connected-component heuristic (non-zero blobs)
        visited = [[False] * w for _ in range(h)]
        objects = 0
        for y in range(h):
            for x in range(w):
                if inp[y][x] != 0 and not visited[y][x]:
                    objects += 1
                    stack = [(x, y)]
                    visited[y][x] = True
                    while stack:
                        cx, cy = stack.pop()
                        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and inp[ny][nx] != 0:
                                visited[ny][nx] = True
                                stack.append((nx, ny))
        mean_c = sum(flat) / len(flat) / 9.0
        var_c = sum((c / 9.0 - mean_c) ** 2 for c in flat) / len(flat)
        return np.array([h / 30.0, w / 30.0, len(colors) / 10.0, objects / 10.0, mean_c, var_c], dtype=float)

    def update_from_success(self, task_pairs: List[Dict[str, Any]], program: TransformationProgram) -> None:
        """Record a successful program to improve the transition model."""
        steps = [s.name for s in program.steps]
        features = self._extract_task_features(task_pairs)
        self._success_history.append((features, steps))
        for i in range(len(steps) - 1):
            prev, nxt = steps[i], steps[i + 1]
            self._transition_counts[prev][nxt] += 1
            self._total_from[prev] += 1

    def transition_probability(self, prev: str, nxt: str) -> float:
        """P(nxt | prev) with Laplace smoothing."""
        total = self._total_from.get(prev, 0)
        vocab_size = len(self._transition_counts)
        count = self._transition_counts[prev].get(nxt, 0)
        return (count + 1) / (total + vocab_size + 1) if vocab_size > 0 else 1.0

    def _task_similarity(self, task_pairs: List[Dict[str, Any]], program: TransformationProgram) -> float:
        """Cosine similarity between current task features and historical successes."""
        if not self._success_history:
            return 0.0
        feats = self._extract_task_features(task_pairs)
        steps = [s.name for s in program.steps]
        best = 0.0
        for hist_feats, hist_steps in self._success_history:
            # Feature cosine similarity
            norm_p = np.linalg.norm(feats)
            norm_h = np.linalg.norm(hist_feats)
            if norm_p > 0 and norm_h > 0:
                sim = float(np.dot(feats, hist_feats) / (norm_p * norm_h))
            else:
                sim = 0.0
            # Sequence overlap bonus
            overlap = len(set(steps) & set(hist_steps)) / max(len(set(steps) | set(hist_steps)), 1)
            best = max(best, sim + overlap)
        return best

    # ------------------------------------------------------------------ #
    # Guided search
    # ------------------------------------------------------------------ #

    def guided_search(
        self,
        train_pairs: List[Dict[str, Any]],
        primitives: List[GridTransformation],
        engine: Any,
        max_depth: int = 3,
        max_candidates: int = 100,
    ) -> List[ProgramCandidate]:
        """A* search over program space informed by transition probabilities.

        Cost = depth - log(transition_probability) - task_similarity_bonus.
        Lower cost = higher priority.
        """
        candidates: List[ProgramCandidate] = []
        seen: set = set()
        # Priority queue: (cost, tie_breaker, program)
        counter = 0
        queue: List[Tuple[float, int, TransformationProgram]] = []

        # Seed with single-step programs
        for prim in primitives:
            prog = TransformationProgram(steps=[prim])
            key = engine._program_key(prog)
            if key in seen:
                continue
            seen.add(key)
            # Cost = depth (1) - no transition bonus yet
            cost = 1.0
            heapq.heappush(queue, (cost, counter, prog))
            counter += 1

        while queue and len(candidates) < max_candidates:
            cost, _, prog = heapq.heappop(queue)
            matches = engine._validate_program(prog, train_pairs)
            if matches == len(train_pairs):
                candidates.append(
                    ProgramCandidate(program=prog, train_matches=matches, confidence=1.0)
                )
                # Record success immediately to improve future searches
                self.update_from_success(train_pairs, prog)
                continue

            if prog.complexity_score >= max_depth:
                continue

            # Expand with all primitives, scoring by transition probability
            last_name = prog.steps[-1].name if prog.steps else ""
            for prim in primitives:
                new_prog = TransformationProgram(steps=prog.steps + [prim])
                if new_prog.complexity_score > max_depth:
                    continue
                key = engine._program_key(new_prog)
                if key in seen:
                    continue
                seen.add(key)
                trans_p = self.transition_probability(last_name, prim.name)
                # Task similarity bonus for longer programs
                sim_bonus = self._task_similarity(train_pairs, new_prog) * 0.5
                new_cost = new_prog.complexity_score - math.log(trans_p + 1e-12) - sim_bonus
                heapq.heappush(queue, (new_cost, counter, new_prog))
                counter += 1

        return candidates

    # ------------------------------------------------------------------ #
    # Checkpointing
    # ------------------------------------------------------------------ #

    def save(self, path: str) -> None:
        """Persist transition model and success history to JSON."""
        import json
        payload = {
            "transition_counts": {k: dict(v) for k, v in self._transition_counts.items()},
            "total_from": dict(self._total_from),
            "success_history": [
                (feats.tolist(), steps) for feats, steps in self._success_history
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load(self, path: str) -> None:
        """Restore transition model and success history from JSON."""
        import json
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        self._transition_counts = defaultdict(Counter)
        for k, v in payload.get("transition_counts", {}).items():
            self._transition_counts[k] = Counter(v)
        self._total_from = defaultdict(int, payload.get("total_from", {}))
        self._success_history = [
            (np.array(feats, dtype=float), steps)
            for feats, steps in payload.get("success_history", [])
        ]
