from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from models.preference_models import UserPreferences, AIRecommendation, BookTrending
from dataBase import db

router = APIRouter(tags=["preferences"])

@router.post("/users/{user_id}/preferences", response_model=UserPreferences)
async def set_user_preferences(user_id: str, preferences: UserPreferences):
    try:
        preferences_dict = preferences.dict()
        preferences_dict["updated_at"] = datetime.utcnow()
        
        result = await db.preferences.update_one(
            {"user_id": user_id},
            {"$set": preferences_dict},
            upsert=True
        )
        
        updated_preferences = await db.preferences.find_one({"user_id": user_id})
        return updated_preferences
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/preferences", response_model=UserPreferences)
async def get_user_preferences(user_id: str):
    try:
        preferences = await db.preferences.find_one({"user_id": user_id})
        if not preferences:
            raise HTTPException(status_code=404, detail="Preferences not found")
        return preferences
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/ai-recommendations", response_model=List[AIRecommendation])
async def get_ai_recommendations(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50)
):
    try:
        recommendations = []
        cursor = db.recommendations.find({"user_id": user_id}) \
            .sort("match_percentage", -1) \
            .skip(skip).limit(limit)
        
        async for rec in cursor:
            recommendations.append(rec)
        
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ai/generate-recommendations/{user_id}")
async def generate_ai_recommendations(user_id: str):
    try:
        # Get user preferences
        preferences = await db.preferences.find_one({"user_id": user_id})
        if not preferences:
            raise HTTPException(status_code=404, detail="User preferences not found")
            
        # Get user's reading history
        reading_history = await db.reading_stats.find_one({"user_id": user_id})
        
        # Get available books
        available_books = []
        async for book in db.books.find({"is_taken": False}):
            book["id"] = str(book["_id"])
            available_books.append(book)
            
        # Simple recommendation algorithm (to be enhanced with AI)
        recommendations = []
        for book in available_books:
            match_percentage = 0
            reason = []
            
            # Match by genre
            if book.get("genre") in preferences.get("favorite_genres", []):
                match_percentage += 40
                reason.append(f"Matches your favorite genre: {book['genre']}")
                
            # Match by author
            if book.get("author") in preferences.get("favorite_authors", []):
                match_percentage += 30
                reason.append(f"By one of your favorite authors: {book['author']}")
                
            # Only include books with good matches
            if match_percentage > 30:
                recommendation = AIRecommendation(
                    user_id=user_id,
                    book_id=book["id"],
                    match_percentage=match_percentage,
                    reason=", ".join(reason),
                    created_at=datetime.utcnow()
                )
                recommendations.append(recommendation.dict())
        
        # Store new recommendations
        if recommendations:
            await db.recommendations.delete_many({"user_id": user_id})
            await db.recommendations.insert_many(recommendations)
            
        return {"message": f"Generated {len(recommendations)} recommendations"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/books/trending", response_model=List[BookTrending])
async def get_trending_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50)
):
    try:
        trending_books = []
        cursor = db.books.aggregate([
            {
                "$lookup": {
                    "from": "book_interactions",
                    "localField": "_id",
                    "foreignField": "book_id",
                    "as": "interactions"
                }
            },
            {
                "$addFields": {
                    "views_count": {
                        "$size": {
                            "$filter": {
                                "input": "$interactions",
                                "as": "interaction",
                                "cond": {"$eq": ["$$interaction.interaction_type", "view"]}
                            }
                        }
                    },
                    "exchange_requests_count": {
                        "$size": {
                            "$filter": {
                                "input": "$interactions",
                                "as": "interaction",
                                "cond": {"$eq": ["$$interaction.interaction_type", "exchange_request"]}
                            }
                        }
                    }
                }
            },
            {
                "$addFields": {
                    "trend_score": {
                        "$add": [
                            {"$multiply": ["$views_count", 1]},
                            {"$multiply": ["$exchange_requests_count", 3]}
                        ]
                    }
                }
            },
            {"$sort": {"trend_score": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ])
        
        async for book in cursor:
            book["book_id"] = str(book["_id"])
            trending_books.append(BookTrending(**book))
            
        return trending_books
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 