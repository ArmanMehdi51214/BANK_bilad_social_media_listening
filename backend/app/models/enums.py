from enum import Enum


class PlatformType(str, Enum):
    X = "x"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    OTHER = "other"


class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class MonitoringRuleType(str, Enum):
    KEYWORD = "keyword"
    HASHTAG = "hashtag"
    MENTION = "mention"
    ACCOUNT = "account"
    ADVANCED_QUERY = "advanced_query"


class MonitoringTargetType(str, Enum):
    BRAND = "brand"
    COMPETITOR = "competitor"
    PRODUCT = "product"
    SERVICE = "service"
    CAMPAIGN = "campaign"
    GENERAL = "general"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    BANK = "bank"
    COMPETITOR = "competitor"
    PRODUCT = "product"
    SERVICE = "service"
    CAMPAIGN = "campaign"
    HASHTAG = "hashtag"
    MENTION = "mention"
    LOCATION = "location"
    OTHER = "other"


class CollectionJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class AIAnalysisStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
