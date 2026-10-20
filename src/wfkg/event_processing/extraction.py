"""PhoBERT-backed extraction interface."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Mapping

from .text_input import ExtractionInput, prepare_extraction_input


_BKEE_EVENT_ROLES = {
    # Role inventories come from actual event_mentions/arguments in the
    # official BKEE train split. In particular, Transfer-money uses Giver and
    # Recipient, while Transfer-ownership uses Buyer and Seller; treating
    # those as incompatible silently disconnected valid EAE predictions.
    "Appeal": {"Adjudicator", "Crime", "Defendant", "Prosecutor", "Time"},
    "Arquit": {"Adjudicator", "Crime", "Defendant", "Time"},
    "Arrest-jail": {"Agent", "Crime", "Person", "Place", "Time"},
    "Attack": {"Attacker", "Instrument", "Place", "Target", "Time"},
    "Be-born": {"Person", "Place", "Time"},
    "Charge-indict": {"Adjudicator", "Crime", "Defendant", "Place", "Prosecutor", "Time"},
    "Convict": {"Adjudicator", "Crime", "Defendant", "Place", "Time"},
    "Declare-bankruptcy": {"Org", "Place", "Time"},
    "Demonstrate": {"Entity", "Place", "Time"},
    "Die": {"Agent", "Instrument", "Place", "Time", "Victim"},
    "Divorce": {"Person", "Place", "Time"},
    "Elect": {"Entity", "Person", "Place", "Position", "Time"},
    "End-org": {"Org", "Place", "Time"},
    "End-position": {"Entity", "Person", "Place", "Position", "Time"},
    "Execute": {"Agent", "Crime", "Person", "Place", "Time"},
    "Extradite": {"Agent", "Destination", "Origin", "Person", "Time"},
    "Fine": {"Adjudicator", "Crime", "Entity", "Money", "Place", "Time"},
    "Injure": {"Agent", "Instrument", "Place", "Time", "Victim"},
    "Marry": {"Person", "Place", "Time"},
    "Meet": {"Entity", "Place", "Time"},
    "Merge-org": {"Org", "Time"},
    "Nominate": {"Agent", "Person", "Place", "Position", "Time"},
    "Pardon": {"Adjudicator", "Crime", "Defendant", "Place", "Time"},
    "Phone-write": {"Entity", "Time"},
    "Release-parole": {"Crime", "Entity", "Person", "Place", "Time"},
    "Sentence": {"Adjudicator", "Crime", "Defendant", "Place", "Sentence", "Time"},
    "Start-org": {"Agent", "Org", "Place", "Time"},
    "Start-position": {"Entity", "Person", "Place", "Position", "Time"},
    "Sue": {"Adjudicator", "Crime", "Defendant", "Place", "Plaintiff", "Time"},
    "Transfer-money": {"Beneficiary", "Giver", "Money", "Place", "Recipient", "Time"},
    "Transfer-ownership": {"Artifact", "Beneficiary", "Buyer", "Place", "Price", "Seller", "Time"},
    "Transport": {"Agent", "Artifact", "Destination", "Origin", "Time", "Vehicle"},
    "Trial-hearing": {"Adjudicator", "Crime", "Defendant", "Place", "Prosecutor", "Time"},
}


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = max(text.rfind(mark, 0, start) for mark in (".", "?", "!", ";", "\n"))
    right = [p for mark in (".", "?", "!", ";", "\n") if (p := text.find(mark, end)) >= 0]
    return left + 1, min(right) + 1 if right else len(text)


def _nearest_trigger_ids(text: str, start: int, end: int, triggers: list[dict]) -> list[str]:
    sentence = _sentence_bounds(text, start, end)
    eligible = [row for row in triggers if _sentence_bounds(text, row["startChar"], row["endChar"]) == sentence]
    distances = [(max(0, max(row["startChar"] - end, start - row["endChar"])), row["eventId"]) for row in eligible]
    closest = min((distance for distance, _ in distances), default=None)
    return [event_id for distance, event_id in distances if distance == closest] if closest is not None else []


def _argument_role_type_compatible(role: str, entity_type: str) -> bool:
    if role == "Person":
        return entity_type == "PER"
    if role in {"Entity", "Org", "Organization", "Beneficiary", "Buyer", "Seller", "Giver", "Recipient"}:
        return entity_type == "ORG"
    if role == "Position":
        return entity_type == "JOB"
    return role in {"Time", "Money", "Destination"}


@dataclass(frozen=True)
class ExtractorConfig:
    model_id: str
    checkpoint_path: Path | None
    label_mapping_path: Path | None
    model_version: str
    short_body_review_chars: int = 500
    device: str | None = None
    entity_checkpoint_path: Path | None = None
    argument_checkpoint_path: Path | None = None
    trigger_conditioned_argument_checkpoint_path: Path | None = None


class PhoBERTEventExtractor:
    """Load the configured fine-tuned checkpoint and extract Evidence/Event records.

    Event detection stays on the configured ED checkpoint. Optional BKEE EMD/EAE
    checkpoints add sentence-local mention and role spans without changing KG data.
    """

    def __init__(self, config: ExtractorConfig) -> None:
        self.config = config
        self._detector = None
        self._entity_detector = None
        self._argument_detector = None
        self._trigger_conditioned_argument_detector = None

    def prepare_input(
        self,
        article: Mapping[str, object],
        enriched_article: Mapping[str, object] | None = None,
    ) -> ExtractionInput:
        """Prepare auditable model input, preferring enriched full text."""

        return prepare_extraction_input(
            article,
            enriched_article,
            short_body_review_chars=self.config.short_body_review_chars,
        )

    def extract(
        self,
        article: dict[str, object],
        enriched_article: Mapping[str, object] | None = None,
    ) -> list[dict[str, object]]:
        """Run ED plus configured EMD/EAE and return auditable predictions."""

        prepared = self.prepare_input(article, enriched_article)
        if not self.config.checkpoint_path:
            raise ValueError(
                "extractor.checkpoint_path is required for PhoBERT inference; "
                "train the BKEE detector or configure an existing compatible checkpoint."
            )
        if self._detector is None:
            from .phobert_detector import PhoBERTEventDetector

            self._detector = PhoBERTEventDetector(
                self.config.checkpoint_path,
                label_mapping_path=self.config.label_mapping_path,
                device=self.config.device,
            )
        predictions = self._detector.predict(prepared.text)
        if self.config.entity_checkpoint_path:
            from .phobert_detector import PhoBERTEventDetector
            if self._entity_detector is None:
                self._entity_detector = PhoBERTEventDetector(self.config.entity_checkpoint_path, device=self.config.device)
            if hasattr(self._detector, "_segmenter"):
                self._entity_detector._segmenter = self._detector._segmenter
            entity_mentions = self._entity_detector.predict(prepared.text)
        else:
            entity_mentions = []
        if self.config.argument_checkpoint_path and not self.config.trigger_conditioned_argument_checkpoint_path:
            from .phobert_detector import PhoBERTEventDetector
            if self._argument_detector is None:
                self._argument_detector = PhoBERTEventDetector(self.config.argument_checkpoint_path, device=self.config.device)
            if hasattr(self._detector, "_segmenter"):
                self._argument_detector._segmenter = self._detector._segmenter
            argument_mentions = self._argument_detector.predict(prepared.text)
        else:
            argument_mentions = []
        article_id = prepared.article_id or str(article.get("articleId") or "UNKNOWN_ARTICLE")
        output = []
        for prediction in predictions:
            trigger_span = prediction["triggerSpan"]
            event_type = prediction["eventType"]
            stable_key = f"{article_id}|{event_type}|{trigger_span['startChar']}|{trigger_span['endChar']}"
            evidence = prediction["evidenceSpan"]
            matching_entities = [m for m in entity_mentions if evidence["startChar"] <= m["triggerSpan"]["startChar"] < m["triggerSpan"]["endChar"] <= evidence["endChar"]]
            matching_arguments = [m for m in argument_mentions if evidence["startChar"] <= m["triggerSpan"]["startChar"] < m["triggerSpan"]["endChar"] <= evidence["endChar"]]
            entity_records = [{"text": m["trigger"], "entityType": m["eventType"],
                               "startChar": m["triggerSpan"]["startChar"], "endChar": m["triggerSpan"]["endChar"],
                               "confidence": m["confidence"],
                               "mentionId": "PREDICTED_MENTION:" + hashlib.sha256(
                                   f"{article_id}|{m['triggerSpan']['startChar']}|{m['triggerSpan']['endChar']}|{m['eventType']}".encode("utf-8")
                               ).hexdigest()[:20]} for m in matching_entities]
            if self.config.trigger_conditioned_argument_checkpoint_path:
                from .trigger_conditioned_eae import TriggerConditionedEAE
                if self._trigger_conditioned_argument_detector is None:
                    self._trigger_conditioned_argument_detector = TriggerConditionedEAE(
                        self.config.trigger_conditioned_argument_checkpoint_path, device=self.config.device)
                trigger_start, trigger_end = int(trigger_span["startChar"]), int(trigger_span["endChar"])
                sentence_start, sentence_end = _sentence_bounds(prepared.text, trigger_start, trigger_end)
                pair_entities = [m for m in matching_entities
                                 if _sentence_bounds(prepared.text, m["triggerSpan"]["startChar"],
                                                     m["triggerSpan"]["endChar"]) == (sentence_start, sentence_end)]
                pair_inputs = [{"sentence": prepared.text[sentence_start:sentence_end],
                                "triggerSpan": (trigger_start - sentence_start, trigger_end - sentence_start),
                                "eventType": event_type,
                                "entitySpan": (m["triggerSpan"]["startChar"] - sentence_start,
                                               m["triggerSpan"]["endChar"] - sentence_start),
                                "entityType": m["eventType"]} for m in pair_entities]
                pair_outputs = self._trigger_conditioned_argument_detector.predict_pairs(pair_inputs)
                argument_records = []
                for mention, result in zip(pair_entities, pair_outputs):
                    if result.get("status") != "OK" or result.get("label") == "NONE":
                        continue
                    entity_span = mention["triggerSpan"]
                    exact_entity = next((entity for entity in entity_records
                                         if entity["startChar"] == entity_span["startChar"]
                                         and entity["endChar"] == entity_span["endChar"]), None)
                    argument_records.append({"text": mention["trigger"], "role": result["label"],
                                             "startChar": entity_span["startChar"], "endChar": entity_span["endChar"],
                                             "confidence": result["confidence"], "entityMention": exact_entity,
                                             "entityMentionId": exact_entity.get("mentionId") if exact_entity else None,
                                             "entityMatchStatus": "EXACT_SPAN" if exact_entity else "UNRESOLVED",
                                             "triggerConditioned": True, "conditionedOnEventId": "PREDICTED_EVENT:" + hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:20],
                                             "conditionedOnTriggerSpan": {"startChar": trigger_start, "endChar": trigger_end},
                                             "sourceMethod": "PHOBERT_TRIGGER_CONDITIONED_BKEE_EAE_V1",
                                             "reviewStatus": "REVIEW_REQUIRED"})
            else:
                argument_records = []
                for m in matching_arguments:
                    role_span = m["triggerSpan"]
                    exact_entity = next((entity for entity in entity_records
                                         if entity["startChar"] == role_span["startChar"]
                                         and entity["endChar"] == role_span["endChar"]), None)
                    argument_records.append({"text": m["trigger"], "role": m["eventType"],
                                             "startChar": role_span["startChar"], "endChar": role_span["endChar"],
                                             "confidence": m["confidence"],
                                             "entityMention": exact_entity, "entityMatchStatus": "EXACT_SPAN" if exact_entity else "UNRESOLVED"})
            output.append({
                "eventId": "PREDICTED_EVENT:" + hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:20],
                "eventType": event_type,
                "trigger": {
                    "text": prediction["trigger"],
                    **trigger_span,
                },
                "confidenceScore": prediction["confidence"],
                "evidenceSpan": prediction["evidenceSpan"],
                "entityMentions": entity_records,
                "argumentMentions": argument_records,
                "eventTypeSystem": "BKEE_33_TYPES",
                "extractionMethod": "PHOBERT_BKEE_BIO",
                "modelPrediction": True,
                "modelId": self.config.model_id,
                "modelVersion": self.config.model_version,
                "inputSource": prepared.source,
                "inputStatus": prepared.status,
                "inputSha256": prepared.sha256,
                "articleId": article_id,
            })
        trigger_rows = [{"eventId": row["eventId"], **row["trigger"]} for row in output]
        for event_row in output:
            event_type = str(event_row["eventType"])
            evidence_span = event_row["evidenceSpan"]
            for argument in event_row["argumentMentions"]:
                start, end = argument.get("startChar"), argument.get("endChar")
                span_ok = (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(prepared.text)
                           and prepared.text[start:end] == argument.get("text"))
                in_evidence = (span_ok and evidence_span["startChar"] <= start < end <= evidence_span["endChar"])
                argument["argumentSpanVerified"] = bool(span_ok)
                argument["inEventEvidence"] = bool(in_evidence)
                argument["eventRoleCompatible"] = argument.get("role") in _BKEE_EVENT_ROLES.get(event_type, set())
                mention = argument.get("entityMention") or {}
                role = str(argument.get("role", ""))
                entity_type = str(mention.get("entityType", ""))
                argument["entityRoleCompatible"] = _argument_role_type_compatible(role, entity_type)
                nearest = _nearest_trigger_ids(prepared.text, start, end, trigger_rows) if span_ok else []
                argument["nearestTriggerEventIds"] = nearest
                if not span_ok or not in_evidence:
                    argument["triggerLinkStatus"] = "SPAN_ERROR"
                elif not argument["eventRoleCompatible"] or not argument["entityRoleCompatible"]:
                    argument["triggerLinkStatus"] = "ROLE_TYPE_INCOMPATIBLE"
                elif nearest == [event_row["eventId"]]:
                    argument["triggerLinkStatus"] = "LINKED_TO_TRIGGER"
                else:
                    argument["triggerLinkStatus"] = "UNRESOLVED_TRIGGER"
        return output


def extractor_from_project_config(config: object) -> PhoBERTEventExtractor:
    """Build the extractor from the project's ``extractor`` YAML section."""

    values = getattr(config, "values", {})
    section = values.get("extractor", {}) if isinstance(values, dict) else {}
    config_path = getattr(config, "path", None)
    root = Path(config_path).resolve().parent.parent if config_path else Path.cwd()

    def configured_path(name: str) -> Path | None:
        value = section.get(name)
        if not value:
            return None
        path = Path(str(value))
        return path if path.is_absolute() else (root / path).resolve()

    return PhoBERTEventExtractor(ExtractorConfig(
        model_id=str(section.get("model_id", "vinai/phobert-base-v2")),
        checkpoint_path=configured_path("checkpoint_path"),
        label_mapping_path=configured_path("label_mapping_path"),
        model_version=str(section.get("model_version", "unversioned")),
        short_body_review_chars=int(section.get("short_body_review_chars", 500)),
        device=str(section["device"]) if section.get("device") else None,
        entity_checkpoint_path=configured_path("entity_checkpoint_path"),
        argument_checkpoint_path=configured_path("argument_checkpoint_path"),
        trigger_conditioned_argument_checkpoint_path=configured_path("trigger_conditioned_argument_checkpoint_path"),
    ))


class ReviewedAnnotationExtractor:
    """Expose analyst-reviewed extraction records without relabeling their origin.

    Each input record must identify ``articleIds`` and carries its original
    evidence/event annotation. This adapter does not infer spans or labels.
    """

    def __init__(self, reviewed_records: list[dict[str, object]]) -> None:
        self._by_article: dict[str, list[dict[str, object]]] = {}
        for record in reviewed_records:
            article_ids = record.get("articleIds", record.get("articles", []))
            if isinstance(article_ids, str):
                article_ids = [article_ids]
            for article_id in article_ids if isinstance(article_ids, list) else []:
                self._by_article.setdefault(str(article_id), []).append(dict(record))

    def extract(self, article_id: str) -> list[dict[str, object]]:
        """Return reviewed records with explicit provenance metadata."""
        return [
            {**record, "extractionMethod": "ANALYST_REVIEWED", "modelPrediction": False}
            for record in self._by_article.get(article_id, [])
        ]
