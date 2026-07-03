from typing import Any

import httpx
from loguru import logger

from app.core.config import settings
from app.integrations.social.base.schemas import CollectionRequest, CollectionResult
from app.integrations.social.x.providers.apify_mapper import ApifyTweetMapper


class ApifyXClient:
    def __init__(self) -> None:
        self.api_token = settings.APIFY_API_TOKEN
        self.base_url = settings.APIFY_BASE_URL.rstrip("/")
        self.actor_path = settings.apify_actor_path
        self.timeout_seconds = settings.APIFY_RUN_TIMEOUT_SECONDS
        self.mapper = ApifyTweetMapper()

    def is_configured(self) -> bool:
        return bool(self.api_token and self.api_token.strip())

    def build_actor_url(self) -> str:
        return (
            f"{self.base_url}/acts/{self.actor_path}"
            f"/run-sync-get-dataset-items"
            f"?token={self.api_token}&format=json"
        )

    def build_payload(self, request: CollectionRequest) -> dict[str, Any]:
        max_items = min(request.max_items, settings.APIFY_MAX_TWEETS_PER_RUN)

        payload = {
            "searchTerms": request.query_values,
            "maxItems": max_items,
            "sort": request.sort,
        }

        if request.language:
            payload["tweetLanguage"] = request.language

        return payload

    async def collect(self, request: CollectionRequest) -> CollectionResult:
        if not self.is_configured():
            raise RuntimeError("APIFY_API_TOKEN is not configured.")

        url = self.build_actor_url()
        payload = self.build_payload(request)

        logger.info(
            "Starting Apify X collection | queries={} | max_items={}",
            request.query_values,
            payload.get("maxItems"),
        )

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError("Unexpected Apify response format. Expected list.")

        posts = self.mapper.map_items(data, request.query_values)

        logger.info(
            "Apify X collection completed | returned_items={} | mapped_posts={}",
            len(data),
            len(posts),
        )

        return CollectionResult(
            platform=request.platform,
            query_values=request.query_values,
            total_fetched=len(data),
            posts=posts,
            raw_response=data,
        )
