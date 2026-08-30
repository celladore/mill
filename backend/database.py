import logging
import os

from config import DB_NAME, MONGO_URL
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)


class Database:
    """
    Database connection manager with connection pooling.

    TODO: Production enhancements:
    - Add connection health checks
    - Implement connection retry logic with exponential backoff
    - Add connection pool monitoring and metrics
    - Implement read preference configuration for replica sets
    - Add connection timeout configuration
    """

    client = None
    db = None

    @classmethod
    async def connect(cls):
        """
        Connect to MongoDB database with connection pooling.

        Connection pool configuration:
        - maxPoolSize: Maximum number of connections (default: 100)
        - minPoolSize: Minimum number of connections (default: 0)
        - maxIdleTimeMS: Close connections after idle time
        """
        if cls.client is not None:
            logger.warning("Database already connected")
            return cls.db

        try:
            # Get pool size from environment or use defaults
            max_pool = int(os.environ.get("MONGODB_MAX_POOL_SIZE", 100))
            min_pool = int(os.environ.get("MONGODB_MIN_POOL_SIZE", 0))
            idle_time = int(os.environ.get("MONGODB_MAX_IDLE_TIME_MS", 0))
            max_idle_time_ms = idle_time or None

            # Create client with connection pooling
            cls.client = AsyncIOMotorClient(
                MONGO_URL,
                maxPoolSize=max_pool,
                minPoolSize=min_pool,
                maxIdleTimeMS=max_idle_time_ms,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
            )

            # Test connection
            await cls.client.admin.command("ping")

            cls.db = cls.client[DB_NAME]

            # Create indexes for better performance
            # TODO: Move index creation to migration script for production
            await cls._create_indexes()

            logger.info(
                f"Connected to MongoDB database '{DB_NAME}' "
                f"(pool: {min_pool}-{max_pool} connections)"
            )
            return cls.db

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
            raise

    @classmethod
    async def _create_indexes(cls):
        """Create database indexes for performance optimization.

        Indexes are created automatically on startup.
        """
        try:
            # Indexes for conversions collection
            conversions = cls.db.conversions
            await conversions.create_index("id", unique=True)
            await conversions.create_index("timestamp")
            # Descending for recent first
            await conversions.create_index([("timestamp", -1)])
            await conversions.create_index([("user_id", 1), ("timestamp", -1)])
            await conversions.create_index(
                [("artifact_available", 1), ("artifact_expires_at", 1)]
            )

            # Indexes for audio_conversions collection
            audio_conversions = cls.db.audio_conversions
            await audio_conversions.create_index("id", unique=True)
            await audio_conversions.create_index("timestamp")
            await audio_conversions.create_index([("timestamp", -1)])
            await audio_conversions.create_index([("user_id", 1), ("timestamp", -1)])
            await audio_conversions.create_index(
                [("artifact_available", 1), ("artifact_expires_at", 1)]
            )

            video_conversions = cls.db.video_conversions
            await video_conversions.create_index("id", unique=True)
            await video_conversions.create_index([("user_id", 1), ("timestamp", -1)])
            await video_conversions.create_index(
                [("artifact_available", 1), ("artifact_expires_at", 1)]
            )

            # Indexes for image_conversions collection
            image_conversions = cls.db.image_conversions
            await image_conversions.create_index("id", unique=True)
            await image_conversions.create_index("timestamp")
            await image_conversions.create_index([("timestamp", -1)])
            # Supports the user-scoped download/result lookups in
            # ConversionBusinessLogic.get_image_conversion_result /
            # get_image_file_path.
            await image_conversions.create_index("user_id")
            # Supports RetentionService.expire_image_conversions.
            await image_conversions.create_index(
                [("artifact_available", 1), ("artifact_expires_at", 1)]
            )
            await image_conversions.create_index([("user_id", 1), ("timestamp", -1)])

            # Retained transcription history. Ephemeral transcriptions never
            # enter this collection.
            transcriptions = cls.db.transcriptions
            await transcriptions.create_index("id", unique=True)
            await transcriptions.create_index([("user_id", 1), ("timestamp", -1)])

            text_conversions = cls.db.text_conversions
            await text_conversions.create_index("id", unique=True)
            await text_conversions.create_index(
                [("artifact_available", 1), ("artifact_expires_at", 1)]
            )
            await text_conversions.create_index([("user_id", 1), ("timestamp", -1)])

            generated_texts = cls.db.generated_texts
            await generated_texts.create_index("id", unique=True)
            await generated_texts.create_index(
                [("artifact_available", 1), ("artifact_expires_at", 1)]
            )
            await generated_texts.create_index([("user_id", 1), ("timestamp", -1)])

            # Indexes for documents collection
            documents = cls.db.documents
            await documents.create_index("id", unique=True)
            await documents.create_index("uploaded_by")
            await documents.create_index("timestamp")
            await documents.create_index([("uploaded_by", 1), ("timestamp", -1)])

            batches = cls.db.batches
            await batches.create_index("id", unique=True)
            await batches.create_index([("user_id", 1), ("created_at", -1)])
            await batches.create_index(
                [("user_id", 1), ("idempotency_hash", 1)], unique=True
            )
            await batches.create_index("expires_at", expireAfterSeconds=0)

            batch_items = cls.db.batch_items
            await batch_items.create_index("id", unique=True)
            await batch_items.create_index([("batch_id", 1), ("position", 1)])
            await batch_items.create_index([("user_id", 1), ("batch_id", 1)])
            await batch_items.create_index("expires_at", expireAfterSeconds=0)

            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Failed to create indexes (may already exist): {e}")

    @classmethod
    async def close(cls):
        """Close database connection"""
        if cls.client:
            cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("Database connection closed")

    @classmethod
    def get_db(cls):
        """Get database instance.

        Raises RuntimeError if database is not connected.
        """
        if cls.db is None:
            raise RuntimeError("Database not connected. Call Database.connect() first.")
        return cls.db
