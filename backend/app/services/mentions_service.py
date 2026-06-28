import re
from sqlalchemy.orm import Session
from app.models import User, Notification

def process_admin_mentions(db: Session, sender: User, message_content: str, message_link: str = None):
    """
    Scans message_content for @FullName mentions of ANY active user.
    Creates a Notification for each mentioned user and returns their IDs
    so the caller can send them a real-time WS notification event.
    """
    if not message_content or not sender:
        return []

    # Fetch all active users (not just admins)
    all_users = db.query(User).filter(User.is_active == True).all()
    notified_ids = []

    for user in all_users:
        if user.id == sender.id:
            continue

        mention_str = f"@{user.full_name}"
        if mention_str.lower() in message_content.lower():
            notification = Notification(
                user_id=user.id,
                title="🔔 New Mention in Chat",
                body=f"{sender.full_name} mentioned you in the community chat.",
                type="mention",
                link=message_link or "chat.html",
                is_read=False
            )
            db.add(notification)
            notified_ids.append(user.id)

    # Check for @all mention if sender is admin
    if sender.is_admin and "@all" in message_content.lower():
        all_users = db.query(User).filter(User.is_active == True).all()
        for u in all_users:
            if u.id == sender.id or u.id in notified_ids:
                continue
            notification = Notification(
                user_id=u.id,
                title="Important Announcement",
                body=f"Admin {sender.full_name} sent a message to everyone in the chat.",
                type="mention",
                link=message_link or "chat.html",
                is_read=False
            )
            db.add(notification)
            notified_ids.append(u.id)
            
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving mention notifications: {e}")
        
    return notified_ids
