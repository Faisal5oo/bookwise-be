from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from models.notification_models import Notification, NotificationType, NotificationPreferences
from dataBase import db

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/users/{user_id}", response_model=List[Notification])
async def get_user_notifications(
    user_id: str,
    unread_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    try:
        query = {"user_id": user_id}
        if unread_only:
            query["read"] = False
            
        notifications = []
        cursor = db.notifications.find(query) \
            .sort("created_at", -1) \
            .skip(skip).limit(limit)
            
        async for notif in cursor:
            notifications.append(notif)
            
        return notifications
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    try:
        result = await db.notifications.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"read": True}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
            
        return {"message": "Notification marked as read"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send")
async def send_notification(notification: Notification):
    try:
        # Verify user exists
        user = await db.users.find_one({"_id": ObjectId(notification.user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Get user's notification preferences
        preferences = await db.notification_preferences.find_one({"user_id": notification.user_id})
        if preferences and not preferences.get("notification_types", {}).get(notification.type, True):
            return {"message": "Notification type disabled by user"}
            
        notification_dict = notification.dict()
        notification_dict["created_at"] = datetime.utcnow()
        
        result = await db.notifications.insert_one(notification_dict)
        
        # TODO: Implement email/push notification sending based on user preferences
        
        return {
            "message": "Notification sent successfully",
            "notification_id": str(result.inserted_id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{notification_id}")
async def delete_notification(notification_id: str):
    try:
        result = await db.notifications.delete_one({"_id": ObjectId(notification_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
            
        return {"message": "Notification deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/users/{user_id}/preferences")
async def update_notification_preferences(user_id: str, preferences: NotificationPreferences):
    try:
        preferences_dict = preferences.dict()
        preferences_dict["updated_at"] = datetime.utcnow()
        
        result = await db.notification_preferences.update_one(
            {"user_id": user_id},
            {"$set": preferences_dict},
            upsert=True
        )
        
        return {"message": "Notification preferences updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(user_id: str):
    try:
        preferences = await db.notification_preferences.find_one({"user_id": user_id})
        if not preferences:
            # Return default preferences
            preferences = NotificationPreferences(user_id=user_id)
            await db.notification_preferences.insert_one(preferences.dict())
        return preferences
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 