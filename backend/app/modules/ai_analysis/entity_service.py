from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from loguru import logger
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.ai.entities.rule_based import BaselineArabicEntityDetector, EntityDetectionResult
from app.models.ai_analysis import AIAnalysisResult, PostEntity
from app.models.social import SocialPost

try:
    from app.models.competitor import Competitor, CompetitorAlias
except Exception:  # pragma: no cover
    Competitor = None
    CompetitorAlias = None


@dataclass
class EntityDetectionSummary:
    total_candidates: int
    processed: int
    inserted: int
    skipped: int
    errors: int
    dry_run: bool

    def to_dict(self) -> dict:
        return asdict(self)


class SocialPostEntityDetectionService:
    """
    Detects entities and saves them into post_entities.

    Business purpose:
    Enables executive reporting on which brands, competitors, products,
    services, hashtags, and campaign terms are being discussed.
    """

    PIPELINE_VERSION = "entity-baseline-ar-v1"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.post_entity_columns = {
            column.name for column in inspect(PostEntity).columns
        }
        self.analysis_columns = {
            column.name for column in inspect(AIAnalysisResult).columns
        }
        self.detector = BaselineArabicEntityDetector(
            competitor_aliases=self._load_competitor_aliases()
        )

    @staticmethod
    def _get_first_attr(obj: Any, candidates: list[str]) -> Any:
        for attr in candidates:
            if hasattr(obj, attr):
                value = getattr(obj, attr)
                if value not in (None, ""):
                    return value
        return None

    def _load_competitor_aliases(self) -> list[dict[str, Any]]:
        """
        Loads competitor aliases dynamically from DB models.
        Falls back safely if competitor models are unavailable.
        """
        aliases: list[dict[str, Any]] = []

        if Competitor is None or CompetitorAlias is None:
            return aliases

        try:
            competitors = self.db.query(Competitor).all()

            competitor_name_map: dict[str, str] = {}

            for competitor in competitors:
                competitor_id = str(getattr(competitor, "id"))
                competitor_name = self._get_first_attr(
                    competitor,
                    ["name", "display_name", "name_en", "name_ar", "slug"],
                )
                competitor_name_map[competitor_id] = str(competitor_name or competitor_id)

                aliases.append(
                    {
                        "competitor_id": competitor_id,
                        "competitor_name": competitor_name_map[competitor_id],
                        "alias": competitor_name_map[competitor_id],
                    }
                )

            competitor_aliases = self.db.query(CompetitorAlias).all()

            alias_columns = {
                column.name for column in inspect(CompetitorAlias).columns
            }

            ignored = {
                "id",
                "competitor_id",
                "created_at",
                "updated_at",
                "is_active",
            }

            for alias_row in competitor_aliases:
                competitor_id = str(getattr(alias_row, "competitor_id", ""))

                for column_name in alias_columns - ignored:
                    value = getattr(alias_row, column_name, None)

                    if isinstance(value, str) and value.strip():
                        aliases.append(
                            {
                                "competitor_id": competitor_id,
                                "competitor_name": competitor_name_map.get(
                                    competitor_id,
                                    competitor_id,
                                ),
                                "alias": value.strip(),
                            }
                        )

        except Exception as exc:
            logger.warning("Could not load competitor aliases | error={}", str(exc))

        # Hard fallback for main Saudi banking competitors.
        fallback_aliases = [
            ("مصرف الراجحي", "الراجحي"),
            ("البنك الأهلي", "الأهلي"),
            ("البنك الأهلي", "الاهلي"),
            ("بنك الإنماء", "الإنماء"),
            ("بنك الإنماء", "الانماء"),
            ("بنك الرياض", "بنك الرياض"),
            ("ساب", "ساب"),
        ]

        for competitor_name, alias in fallback_aliases:
            aliases.append(
                {
                    "competitor_id": None,
                    "competitor_name": competitor_name,
                    "alias": alias,
                }
            )

        return aliases

    def _latest_analysis_result(self, post_id) -> Optional[AIAnalysisResult]:
        query = self.db.query(AIAnalysisResult).filter(
            AIAnalysisResult.post_id == post_id
        )

        if "is_current" in self.analysis_columns:
            current = query.filter(AIAnalysisResult.is_current.is_(True)).first()
            if current:
                return current

        if "analyzed_at" in self.analysis_columns:
            return query.order_by(AIAnalysisResult.analyzed_at.desc()).first()

        return query.first()

    def build_query(
        self,
        platform: Optional[str] = "x",
        only_without_entities: bool = True,
    ):
        query = self.db.query(SocialPost).filter(SocialPost.clean_text.isnot(None))

        if platform:
            query = query.filter(SocialPost.platform == platform)

        if only_without_entities:
            entity_post_ids_query = self.db.query(PostEntity.post_id)
            query = query.filter(~SocialPost.id.in_(entity_post_ids_query))

        return query

    def _delete_existing_entities(self, post_id) -> None:
        self.db.query(PostEntity).filter(PostEntity.post_id == post_id).delete(
            synchronize_session=False
        )

    def _filtered_payload(self, payload: dict) -> dict:
        return {
            key: value
            for key, value in payload.items()
            if key in self.post_entity_columns
        }

    def _build_entity_payload(
        self,
        post: SocialPost,
        analysis_result: AIAnalysisResult,
        entity: EntityDetectionResult,
    ) -> dict:
        metadata = {
            **entity.metadata,
            "source": entity.source,
            "pipeline_version": self.PIPELINE_VERSION,
        }

        candidate_payload = {
            "analysis_result_id": analysis_result.id,
            "post_id": post.id,

            "entity_type": entity.entity_type,
            "type": entity.entity_type,
            "category": entity.entity_type,

            "entity_text": entity.entity_value,
            "entity_value": entity.entity_value,
            "entity_name": entity.entity_value,
            "text": entity.entity_value,
            "value": entity.entity_value,
            "name": entity.entity_value,

            "normalized_text": entity.normalized_value,
            "normalized_value": entity.normalized_value,
            "normalized_name": entity.normalized_value,

            "confidence": entity.confidence,
            "confidence_score": entity.confidence,

            "source": entity.source,
            "metadata": metadata,
            "analysis_payload": metadata,
            "extra_data": metadata,
        }

        if entity.entity_type == "competitor":
            candidate_payload["competitor_id"] = entity.metadata.get("competitor_id")

        return self._filtered_payload(candidate_payload)

    def detect_for_post(
        self,
        post: SocialPost,
        dry_run: bool = False,
    ) -> int:
        text_for_detection = post.clean_text or post.raw_text or ""
        entities = self.detector.detect(text_for_detection)

        if dry_run:
            logger.info(
                "Dry run entity detection | post_id={} | entities={} | text={}",
                post.id,
                [entity.to_dict() for entity in entities],
                text_for_detection[:120],
            )
            return len(entities)

        analysis_result = self._latest_analysis_result(post.id)

        if not analysis_result:
            logger.warning(
                "Skipping entity detection because no AIAnalysisResult exists | post_id={}",
                post.id,
            )
            return 0

        self._delete_existing_entities(post.id)

        inserted = 0

        for entity in entities:
            payload = self._build_entity_payload(
                post=post,
                analysis_result=analysis_result,
                entity=entity,
            )

            self.db.add(PostEntity(**payload))
            inserted += 1

        return inserted

    def detect_entities(
        self,
        platform: Optional[str] = "x",
        limit: int = 100,
        only_without_entities: bool = True,
        dry_run: bool = False,
    ) -> EntityDetectionSummary:
        query = self.build_query(
            platform=platform,
            only_without_entities=only_without_entities,
        )

        total_candidates = query.count()

        posts = (
            query.order_by(SocialPost.collected_at.desc())
            .limit(limit)
            .all()
        )

        processed = 0
        inserted = 0
        skipped = 0
        errors = 0

        for post in posts:
            processed += 1

            try:
                inserted_for_post = self.detect_for_post(
                    post=post,
                    dry_run=dry_run,
                )

                if inserted_for_post:
                    inserted += inserted_for_post
                else:
                    skipped += 1

            except Exception as exc:
                errors += 1
                logger.exception(
                    "Failed entity detection | post_id={} | error={}",
                    post.id,
                    str(exc),
                )

        if not dry_run:
            self.db.commit()

        summary = EntityDetectionSummary(
            total_candidates=total_candidates,
            processed=processed,
            inserted=inserted,
            skipped=skipped,
            errors=errors,
            dry_run=dry_run,
        )

        logger.info("Entity detection completed | summary={}", summary.to_dict())

        return summary
