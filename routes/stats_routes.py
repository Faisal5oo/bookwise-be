from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from models.stats_models import ReadingStats, BookInteraction, ReadingHabits, InteractionType
from dataBase import db

router = APIRouter(tags=["statistics"])

@router.get("/users/{user_id}/stats", response_model=ReadingStats)
async def get_reading_statistics(user_id: str):
    try:
        stats = await db.reading_stats.find_one({"user_id": user_id})
        if not stats:
            # Initialize stats if not exists
            stats = ReadingStats(user_id=user_id)
            await db.reading_stats.insert_one(stats.dict())
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/{user_id}/stats/update")
async def update_reading_stats(user_id: str, stats: ReadingStats):
    try:
        stats_dict = stats.dict()
        stats_dict["updated_at"] = datetime.utcnow()
        
        result = await db.reading_stats.update_one(
            {"user_id": user_id},
            {"$set": stats_dict},
            upsert=True
        )
        
        return {"message": "Reading stats updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/reading-habits", response_model=ReadingHabits)
async def get_reading_habits(user_id: str):
    try:
        # Get all user's book interactions
        interactions = []
        async for interaction in db.book_interactions.find({"user_id": user_id}):
            interactions.append(interaction)
            
        # Calculate reading habits
        total_books = len(set(i["book_id"] for i in interactions))
        months_active = 1  # Calculate from first interaction
        if interactions:
            first_interaction = min(i["timestamp"] for i in interactions)
            months_active = max(1, (datetime.utcnow() - first_interaction).days / 30)
            
        # Group interactions by hour to find favorite reading time
        hour_counts = {}
        for interaction in interactions:
            hour = interaction["timestamp"].hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
        favorite_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else None
        favorite_time = f"{favorite_hour:02d}:00" if favorite_hour is not None else None
        
        # Get user's reading stats for additional data
        stats = await db.reading_stats.find_one({"user_id": user_id})
        
        habits = ReadingHabits(
            user_id=user_id,
            average_books_per_month=total_books / months_active,
            favorite_reading_time=favorite_time,
            preferred_genres=stats.get("top_genres", []) if stats else [],
            reading_streak=stats.get("current_streak", 0) if stats else 0,
            total_reading_time=stats.get("total_reading_time", 0) if stats else 0
        )
        
        return habits
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/books/{book_id}/interaction")
async def track_book_interaction(book_id: str, interaction: BookInteraction):
    try:
        # Verify book exists
        book = await db.books.find_one({"_id": ObjectId(book_id)})
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
            
        interaction_dict = interaction.dict()
        interaction_dict["book_id"] = book_id
        interaction_dict["timestamp"] = datetime.utcnow()
        
        await db.book_interactions.insert_one(interaction_dict)
        
        # Update book view count if interaction is a view
        if interaction.interaction_type == InteractionType.VIEW:
            await db.books.update_one(
                {"_id": ObjectId(book_id)},
                {"$inc": {"view_count": 1}}
            )
            
        return {"message": "Interaction tracked successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 