from abc import ABC, abstractmethod

from app.integrations.social.base.schemas import CollectionRequest, CollectionResult


class SocialCollectorInterface(ABC):
    """
    Base interface for social media collectors.

    Current implementation:
    - X via Apify

    Future implementations:
    - Instagram
    - Facebook
    - TikTok
    - Official X API
    - Other X reseller APIs
    """

    @abstractmethod
    async def collect(self, request: CollectionRequest) -> CollectionResult:
        raise NotImplementedError
