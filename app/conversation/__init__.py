def get_conversation_service():
    from app.conversation.services import get_conversation_service as _get_conversation_service

    return _get_conversation_service()


__all__ = ["get_conversation_service"]
