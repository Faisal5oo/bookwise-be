from fastapi import FastAPI, HTTPException, Query
from pydantic import HttpUrl
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from models.register_model import RegisterUser 
from models.login_model import LoginUser
from models.profile_model import UserProfile
from models.update_profile_model import UpdateUserProfile
from models.post_book_model import PostBookModel
from models.update_book_model import UpdateBookModel
from models.exchange_models import ExchangeRequest, ExchangeResponse, ExchangeDetails, ExchangeStatus
from models.preference_models import UserPreferences, AIRecommendation, BookTrending
from models.stats_models import ReadingStats, BookInteraction, ReadingHabits, InteractionType
from models.notification_models import Notification, NotificationType, NotificationPreferences
from dataBase import db 
from datetime import datetime, timedelta
from bson import ObjectId
from utils import hash_password, verify_password, create_access_token
from ai_service import ai_service

app = FastAPI(title="BookWise API", version="2.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return RedirectResponse(url="/docs")

#get books serialization method
def serialize_book(book) -> dict:
    return {
        "id": str(book["_id"]),
        "bookName": book.get("bookName"),
        "description": book.get("description"),
        "bookImages": book.get("bookImages", []),
        "created_at": book.get("created_at"),
        "user_id": book.get("user_id"),
        "genre": book.get("genre"),
        "author": book.get("author"),
        "bookCondition": book.get("bookCondition")
    }

# Existing Authentication Routes
@app.post("/register")
async def register_user(user: RegisterUser):
    try:
        await db.command("ping")
        existing_user = await db.users.find_one({"email": user.email})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")
        
        user_dict = user.dict()
        user_dict['password'] = hash_password(user_dict['password'])
        user_dict['created_at'] = datetime.utcnow()

        result = await db.users.insert_one(user_dict)
        created_user = await db.users.find_one({"_id": result.inserted_id})
        created_user["id"] = str(created_user["_id"])
        del created_user["_id"]
        return created_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
async def login_user(user: LoginUser):
    try:
        existing_user = await db.users.find_one({'email': user.email})
        if not existing_user:
            raise HTTPException(status_code=404, detail="Email Not found")
        if not verify_password(user.password, existing_user["password"]):
            raise HTTPException(status_code=404, detail="Password Not Match")
        
        # Create JWT access token
        token_data = {
            "user_id": str(existing_user["_id"]),
            "email": existing_user["email"],
            "fname": existing_user["fName"],
            "lname": existing_user["lName"]
        }
        access_token = create_access_token(data=token_data)
        
        return {
            "message": "Login successful",
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": str(existing_user["_id"]),
            "fname": existing_user["fName"],
            "lname": existing_user["lName"],
            "email": existing_user["email"],
            "expires_in": 60 * 24 * 7 * 60  # 7 days in seconds
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: str):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User Not Found")
    user["id"] = str(user["_id"])
    del user["_id"]
    return user

@app.put("/users/{user_id}")
async def update_user_profile(user_id: str, updated_data: UpdateUserProfile):
    update_dict = {
        k: str(v) if isinstance(v, HttpUrl) else v
        for k, v in updated_data.dict(exclude_unset=True).items()
    }

    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    updated_user["id"] = str(updated_user["_id"])
    del updated_user["_id"]

    return updated_user

# Exchange System Routes
@app.post("/exchanges/request", response_model=ExchangeDetails)
async def request_exchange(exchange: ExchangeRequest):
    try:
        book = await db.books.find_one({"_id": ObjectId(exchange.book_id)})
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        if book.get("is_taken", False):
            raise HTTPException(status_code=400, detail="Book is not available for exchange")

        exchange_dict = exchange.dict()
        exchange_dict["created_at"] = datetime.utcnow()
        result = await db.exchanges.insert_one(exchange_dict)
        
        created_exchange = await db.exchanges.find_one({"_id": result.inserted_id})
        created_exchange["id"] = str(created_exchange["_id"])
        del created_exchange["_id"]
        
        # Create notification for book owner
        notification = Notification(
            user_id=exchange.owner_id,
            type=NotificationType.EXCHANGE_REQUEST,
            title="New Exchange Request",
            message=f"Someone wants to exchange your book",
            data={"exchange_id": created_exchange["id"]}
        )
        await db.notifications.insert_one(notification.dict())
        
        return created_exchange
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/exchanges/user/{user_id}", response_model=List[ExchangeDetails])
async def get_user_exchanges(
    user_id: str,
    status: Optional[ExchangeStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    try:
        query = {"$or": [{"requester_id": user_id}, {"owner_id": user_id}]}
        if status:
            query["status"] = status

        exchanges = []
        cursor = db.exchanges.find(query).skip(skip).limit(limit).sort("created_at", -1)
        async for exchange in cursor:
            exchange["id"] = str(exchange["_id"])
            del exchange["_id"]
            exchanges.append(exchange)
        return exchanges
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/exchanges/{exchange_id}/respond", response_model=ExchangeDetails)
async def respond_to_exchange(exchange_id: str, response: ExchangeResponse):
    try:
        result = await db.exchanges.update_one(
            {"_id": ObjectId(exchange_id)},
            {"$set": {"status": response.response_type, "response": response.dict()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Exchange not found")
            
        updated_exchange = await db.exchanges.find_one({"_id": ObjectId(exchange_id)})
        updated_exchange["id"] = str(updated_exchange["_id"])
        del updated_exchange["_id"]
        
        if response.response_type == ExchangeStatus.ACCEPTED:
            await db.books.update_one(
                {"_id": ObjectId(updated_exchange["book_id"])},
                {"$set": {"is_taken": True}}
            )
            
            # Create notification for requester
            notification = Notification(
                user_id=updated_exchange["requester_id"],
                type=NotificationType.EXCHANGE_RESPONSE,
                title="Exchange Request Accepted",
                message="Your exchange request has been accepted!",
                data={"exchange_id": exchange_id}
            )
            await db.notifications.insert_one(notification.dict())
        
        return updated_exchange
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# User Preferences Routes
@app.post("/users/{user_id}/preferences", response_model=UserPreferences)
async def set_user_preferences(user_id: str, preferences: UserPreferences):
    try:
        preferences_dict = preferences.dict()
        preferences_dict["updated_at"] = datetime.utcnow()
        
        await db.preferences.update_one(
            {"user_id": user_id},
            {"$set": preferences_dict},
            upsert=True
        )
        
        updated_preferences = await db.preferences.find_one({"user_id": user_id})
        return updated_preferences
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/preferences", response_model=UserPreferences)
async def get_user_preferences(user_id: str):
    try:
        preferences = await db.preferences.find_one({"user_id": user_id})
        if not preferences:
            raise HTTPException(status_code=404, detail="Preferences not found")
        return preferences
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ai/generate-recommendations/{user_id}")
async def generate_ai_recommendations(user_id: str):
    try:
        # Get user preferences
        preferences = await db.preferences.find_one({"user_id": user_id})
        if not preferences:
            # Create default preferences if not found
            default_preferences = UserPreferences(user_id=user_id)
            await db.preferences.insert_one(default_preferences.dict())
            preferences = default_preferences.dict()
            
        # Get user's reading history
        reading_history = await db.reading_stats.find_one({"user_id": user_id})
        
        # Get available books
        available_books = []
        async for book in db.books.find({"is_taken": False}):
            book["id"] = str(book["_id"])
            available_books.append(book)
            
        if not available_books:
            return {"message": "No available books for recommendations"}
            
        # Generate AI recommendations
        ai_recommendations = await ai_service.generate_book_recommendations(
            user_id=user_id,
            user_preferences=preferences,
            reading_history=reading_history,
            available_books=available_books
        )
        
        # Store new recommendations
        if ai_recommendations:
            await db.recommendations.delete_many({"user_id": user_id})
            recommendations_dicts = [rec.dict() for rec in ai_recommendations]
            await db.recommendations.insert_many(recommendations_dicts)
            
        return {
            "message": f"Generated {len(ai_recommendations)} AI-powered recommendations",
            "recommendations_count": len(ai_recommendations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/ai-recommendations", response_model=List[AIRecommendation])
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

# Reading Stats Routes
@app.get("/users/{user_id}/stats", response_model=ReadingStats)
async def get_reading_statistics(user_id: str):
    try:
        stats = await db.reading_stats.find_one({"user_id": user_id})
        if not stats:
            stats = ReadingStats(user_id=user_id)
            await db.reading_stats.insert_one(stats.dict())
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/reading-habits", response_model=ReadingHabits)
async def get_reading_habits(user_id: str):
    try:
        interactions = []
        async for interaction in db.book_interactions.find({"user_id": user_id}):
            interactions.append(interaction)
            
        total_books = len(set(i["book_id"] for i in interactions))
        months_active = 1
        if interactions:
            first_interaction = min(i["timestamp"] for i in interactions)
            months_active = max(1, (datetime.utcnow() - first_interaction).days / 30)
            
        hour_counts = {}
        for interaction in interactions:
            hour = interaction["timestamp"].hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
        favorite_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else None
        favorite_time = f"{favorite_hour:02d}:00" if favorite_hour is not None else None
        
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

@app.get("/users/{user_id}/ai-insights")
async def get_ai_reading_insights(user_id: str):
    try:
        # Get reading stats
        reading_stats = await db.reading_stats.find_one({"user_id": user_id})
        if not reading_stats:
            reading_stats = {}
            
        # Get recent interactions
        interactions = []
        async for interaction in db.book_interactions.find({"user_id": user_id}).sort("timestamp", -1).limit(20):
            interactions.append(interaction)
            
        # Generate AI insights
        insights = await ai_service.generate_reading_insights(
            user_id=user_id,
            reading_stats=reading_stats,
            interactions=interactions
        )
        
        return {
            "user_id": user_id,
            "insights": insights,
            "generated_at": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Notification Routes
@app.get("/notifications/users/{user_id}", response_model=List[Notification])
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

@app.put("/notifications/{notification_id}/read")
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

# Book Interaction Routes
@app.post("/books/{book_id}/interaction")
async def track_book_interaction(book_id: str, interaction: BookInteraction):
    try:
        book = await db.books.find_one({"_id": ObjectId(book_id)})
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
            
        interaction_dict = interaction.dict()
        interaction_dict["book_id"] = book_id
        interaction_dict["timestamp"] = datetime.utcnow()
        
        await db.book_interactions.insert_one(interaction_dict)
        
        if interaction.interaction_type == InteractionType.VIEW:
            await db.books.update_one(
                {"_id": ObjectId(book_id)},
                {"$inc": {"view_count": 1}}
            )
        return {"message": "Interaction tracked successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Existing Book Routes
@app.post("/books/")
async def add_new_book(book: PostBookModel):
    try:
        book_data = book.dict()
        if "bookImages" in book_data:
            book_data["bookImages"] = [str(url) for url in book_data["bookImages"]]
        book_data["created_at"] = datetime.utcnow()
        result = await db.books.insert_one(book_data)
        return {
            "message": "Book added successfully",
            "book_id": str(result.inserted_id)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding book: {str(e)}")

@app.put("/updateBook/{book_id}")
async def update_book(book_id: str, updated_data: UpdateBookModel):
    try:
        update_fields = {
            k: [str(url) for url in v] if isinstance(v, list) else v
            for k, v in updated_data.dict().items()
            if v is not None
        }

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields provided to update.")

        result = await db.books.update_one(
            {"_id": ObjectId(book_id)},
            {"$set": update_fields}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Book not found.")

        updated_book = await db.books.find_one({"_id": ObjectId(book_id)})
        updated_book["book_id"] = str(updated_book["_id"])
        del updated_book["_id"]

        return {
            "message": "Book updated successfully.",
            "book": updated_book
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating book: {str(e)}")

@app.get("/getBooks")
async def get_featured_books():
    try:
        books_cursor = db.books.find()
        books = []
        async for book in books_cursor:
            books.append(serialize_book(book))

        return {
            "message": "Books fetched successfully",
            "total_books": len(books),
            "books": books
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching books: {str(e)}")

@app.get("/books/{book_id}")
async def get_book_details(book_id: str):
    try:
        book = await db.books.find_one({"_id": ObjectId(book_id)})
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")

        user = await db.users.find_one({"_id": ObjectId(book["owner_id"])}) if "owner_id" in book else None

        posted_date = book.get("created_at", datetime.utcnow())
        expiry_date = posted_date + timedelta(days=30)

        book_detail = {
            "book_id": str(book["_id"]),
            "book_name": book.get("bookName"),
            "author": book.get("author"),
            "book_owner": {
                "user_id": str(user["_id"]) if user else None,
                "name": f"{user.get('fName', '')} {user.get('lName', '')}".strip() if user else "Unknown",
                "profile_picture_url": user.get("profile_picture_url") if user else None,
            },
            "description": book.get("description"),
            "posted_date": posted_date,
            "expiry_date": expiry_date,
            "pictures": book.get("bookImages", []),
            "book_condition": book.get("bookCondition"),
            "status": "available" if not book.get("is_taken", False) else "not available"
        }

        return book_detail
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching book detail: {str(e)}")

@app.get("/books/trending", response_model=List[BookTrending])
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