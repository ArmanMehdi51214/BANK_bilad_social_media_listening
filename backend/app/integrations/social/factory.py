from app.core.config import settings
from app.integrations.social.base.collector import SocialCollectorInterface
from app.integrations.social.x.collector import XCollector


def get_x_collector() -> SocialCollectorInterface:
    if settings.X_DATA_PROVIDER == "apify":
        return XCollector()

    raise ValueError(f"Unsupported X data provider: {settings.X_DATA_PROVIDER}")
