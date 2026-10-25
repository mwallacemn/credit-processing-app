import logging
from app.infrastructure.celery_app import celery_app
from app.infrastructure.db.database import get_sync_database

logger = logging.getLogger(__name__)


@celery_app.task(name="app.infrastructure.tasks.process_credit", bind=True, max_retries=3)
def process_credit(self, user_id: str, amount: float) -> dict:
    """
    Celery task to credit a user's account asynchronously.
    Updates the user's balance and sets status to 'processed'.
    """
    logger.info(f"Processing credit for user {user_id}: +{amount}")
    db = get_sync_database()
    users_collection = db["users"]

    try:
        # Increment balance (creates field if not present) and set status to 'processed'
        result = users_collection.find_one_and_update(
            {"user_id": user_id},
            {
                "$inc": {"balance": amount},
                "$set": {"status": "processed"},
            },
            return_document=True,
            upsert=True,
        )

        logger.info(f"Credit processed successfully for {user_id}. New balance: {result.get('balance')}")
        return {
            "user_id": user_id,
            "balance": result.get("balance"),
            "status": "processed",
        }
    except Exception as exc:
        logger.error(f"Error processing credit for {user_id}: {exc}")
        # Retry with exponential backoff if failed
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
