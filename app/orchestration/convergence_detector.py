from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from app.orchestration.models import DiscussionPhase, PhaseTurnRecord

logger = logging.getLogger(__name__)


class ConvergenceSignal(BaseModel):
    information_gain: float
    repetition_ratio: float
    all_participants_spoken: bool
    recommendation: str  # "continue" | "suggest_wrap_up" | "force_complete"


class ConvergenceDetector:
    def __init__(
        self,
        *,
        force_threshold: float = 0.85,
        suggest_threshold: float = 0.7,
    ) -> None:
        self._force_threshold = force_threshold
        self._suggest_threshold = suggest_threshold

    def evaluate(
        self, turn_records: list[PhaseTurnRecord], phase: DiscussionPhase
    ) -> ConvergenceSignal:
        if len(turn_records) < 2:
            return ConvergenceSignal(
                information_gain=1.0,
                repetition_ratio=0.0,
                all_participants_spoken=False,
                recommendation="continue",
            )

        latest = turn_records[-1].reply_text
        prior_texts = [r.reply_text for r in turn_records[:-1]]

        latest_tokens = self._tokenize(latest)
        prior_tokens: set[str] = set()
        for text in prior_texts:
            prior_tokens.update(self._tokenize(text))

        if not latest_tokens and not prior_tokens:
            return ConvergenceSignal(
                information_gain=0.0,
                repetition_ratio=1.0,
                all_participants_spoken=self._all_spoken(turn_records, phase),
                recommendation="force_complete",
            )

        intersection = latest_tokens & prior_tokens
        union = latest_tokens | prior_tokens
        jaccard = len(intersection) / len(union) if union else 0.0

        length_decay_boost = self._length_decay_boost(turn_records)
        repetition_ratio = min(1.0, jaccard + length_decay_boost)
        information_gain = 1.0 - repetition_ratio

        all_spoken = self._all_spoken(turn_records, phase)

        if repetition_ratio >= self._force_threshold and all_spoken:
            recommendation = "force_complete"
        elif repetition_ratio >= self._suggest_threshold:
            recommendation = "suggest_wrap_up"
        else:
            recommendation = "continue"

        return ConvergenceSignal(
            information_gain=information_gain,
            repetition_ratio=repetition_ratio,
            all_participants_spoken=all_spoken,
            recommendation=recommendation,
        )

    def _tokenize(self, text: str) -> set[str]:
        cleaned = re.sub(r"[^\w]", " ", text)
        tokens: set[str] = set()
        for word in cleaned.split():
            if len(word) >= 2:
                tokens.add(word.lower())
        for i in range(len(text) - 1):
            bigram = text[i : i + 2].strip()
            if len(bigram) == 2 and not bigram.isspace():
                tokens.add(bigram)
        return tokens

    def _length_decay_boost(self, turn_records: list[PhaseTurnRecord]) -> float:
        if len(turn_records) < 3:
            return 0.0
        lengths = [len(r.reply_text) for r in turn_records[-3:]]
        if lengths[0] == 0:
            return 0.0
        decay_1 = (lengths[0] - lengths[1]) / lengths[0] if lengths[0] > 0 else 0
        decay_2 = (lengths[1] - lengths[2]) / lengths[1] if lengths[1] > 0 else 0
        if decay_1 > 0.4 and decay_2 > 0.4:
            return 0.15
        if decay_1 > 0.4 or decay_2 > 0.4:
            return 0.08
        return 0.0

    def _all_spoken(
        self, turn_records: list[PhaseTurnRecord], phase: DiscussionPhase
    ) -> bool:
        required = {p.employee_id for p in phase.participants}
        spoken = {r.speaker_id for r in turn_records}
        return required.issubset(spoken)
