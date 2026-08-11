"""
MongoDB connection management using Motor (async driver).

Connection lifecycle is tied to the FastAPI application lifespan:
- on startup: connect, ping, create indexes
- on shutdown: close the client cleanly

get_database() is used by repositories to obtain the active database handle.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MongoManager:
    client: AsyncIOMotorClient | None = None
    database: AsyncIOMotorDatabase | None = None


mongo_manager = MongoManager()


async def connect_to_mongo() -> None:
    settings = get_settings()
    logger.info("Connecting to MongoDB", extra={"db_name": settings.mongodb_db_name})

    mongo_manager.client = AsyncIOMotorClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=5000,
    )
    mongo_manager.database = mongo_manager.client[settings.mongodb_db_name]

    try:
        await mongo_manager.client.admin.command("ping")
        logger.info("MongoDB connection established")
    except PyMongoError as exc:
        logger.error("Failed to connect to MongoDB", extra={"error": str(exc)})
        raise RuntimeError(f"Could not connect to MongoDB: {exc}") from exc

    await create_indexes()


async def close_mongo_connection() -> None:
    if mongo_manager.client is not None:
        mongo_manager.client.close()
        logger.info("MongoDB connection closed")


async def create_indexes() -> None:
    """Create all required indexes. Safe to call repeatedly (idempotent)."""
    db = mongo_manager.database
    assert db is not None

    # risks collection
    await db.risks.create_index("riskId", unique=True)
    await db.risks.create_index("accountId")
    await db.risks.create_index("severity")
    await db.risks.create_index("status")
    await db.risks.create_index("createdAt")

    # teams_destinations collection
    await db.teams_destinations.create_index("accountId", unique=True)

    # tenant_mappings collection
    await db.tenant_mappings.create_index("tenantId", unique=True)
    await db.tenant_mappings.create_index("accountId")

    # teams_installations collection. Partial indexes support both logical
    # keys: account+tenant+team, or account+tenant+conversation without a team.
    await db.teams_installations.create_index("accountId")
    await db.teams_installations.create_index(
        [("accountId", 1), ("tenantId", 1), ("teamId", 1)],
        unique=True,
        partialFilterExpression={"teamId": {"$type": "string"}},
    )
    await db.teams_installations.create_index(
        [("accountId", 1), ("tenantId", 1), ("conversationId", 1)],
        unique=True,
        partialFilterExpression={"teamId": None},
    )

    # notification_logs collection
    await db.notification_logs.create_index("riskId")
    await db.notification_logs.create_index("eventId", unique=True)
    await db.notification_logs.create_index("status")
    await db.notification_logs.create_index("eventType")
    await db.notification_logs.create_index("createdAt")

    # idempotency_keys collection (used for Send-to-Teams deduplication)
    await db.idempotency_keys.create_index([("key", 1), ("scope", 1)], unique=True)

    logger.info("MongoDB indexes ensured")


def get_database() -> AsyncIOMotorDatabase:
    """Dependency-friendly accessor for the active database handle."""
    if mongo_manager.database is None:
        raise RuntimeError("Database is not initialized. Did the app start correctly?")
    return mongo_manager.database
