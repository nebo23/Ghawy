import re
from sqlalchemy.orm import Session
from app.models import User, Notification

def process_admin_mentions(db: Session, sender: User, message_content: str, message_link: str = None):
    """
    Scans the message_content for mentions of any active admin's full_name
    (e.g., '@Admin Name'). If found, creates a Notification for that admin.
    """
    if not message_content or not sender:
        return []

    # Fetch all active admins
    admins = db.query(User).filter(User.is_admin == True, User.is_active == True).all()
    notified_ids = []

    for admin in admins:
        # Don't notify the sender if they mention themselves
        if admin.id == sender.id:
            continue
        
        # Check if @Admin Name exists in the text. 
        # Using a simple string match or regex to ensure word boundaries
        mention_str = f"@{admin.full_name}"
        
        # We use re.escape to handle any special regex characters in the name
        # \b doesn't work well with Arabic names or trailing spaces, so we check using string 'in' operator
        # or a simple regex boundary. Let's do simple 'in' check which is reliable enough for names.
        if mention_str.lower() in message_content.lower():
            # Create a notification
            notification = Notification(
                user_id=admin.id,
                title="New Mention in Chat",
                body=f"{sender.full_name} mentioned you in the community chat.",
                type="mention",
                link=message_link or "chat.html",
                is_read=False
            )
            db.add(notification)
            notified_ids.append(admin.id)
            
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
