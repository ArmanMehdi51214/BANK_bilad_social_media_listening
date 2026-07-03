from app.integrations.social.base.collector import SocialCollectorInterface
from app.integrations.social.base.schemas import CollectionRequest, CollectionResult
from app.integrations.social.x.providers.apify_client import ApifyXClient


class XCollector(SocialCollectorInterface):
    """
    X collector wrapper.

    Current provider:
    - Apify

    Future providers can be swapped without changing database or API layers.
    """

    def __init__(self) -> None:
        self.provider = ApifyXClient()

    async def collect(self, request: CollectionRequest) -> CollectionResult:
        return await self.provider.collect(request)
