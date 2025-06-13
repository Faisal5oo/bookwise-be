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
import json

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
        "authorName": book.get("authorName"),
        "genre": book.get("genre", ""),  # Added genre field
        "description": book.get("description"),
        "bookImages": book.get("bookImages", []),
        "created_at": book.get("created_at"),
        "user_id": book.get("user_id"),
        "bookCondition": book.get("bookCondition"),
        "is_taken": book.get("is_taken", False)
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
@app.post("/exchanges/request")
async def request_exchange(exchange: ExchangeRequest):
    try:
        book = await db.books.find_one({"_id": ObjectId(exchange.book_id)})
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        if book.get("is_taken", False):
            raise HTTPException(status_code=400, detail="Book is not available for exchange")

        exchange_dict = exchange.dict()
        exchange_dict["status"] = "pending"  # Ensure status is set
        exchange_dict["created_at"] = datetime.utcnow()
        result = await db.exchanges.insert_one(exchange_dict)
        
        # Get the created exchange with full details
        created_exchange = await db.exchanges.find_one({"_id": result.inserted_id})
        
        # Get book details
        book_info = {
            "book_name": book.get("bookName", "Unknown Book"),
            "book_author": book.get("authorName", "Unknown Author"),
            "book_genre": book.get("genre", ""),
            "book_condition": book.get("bookCondition", "")
        }
        
        # Get requester details
        requester = await db.users.find_one({"_id": ObjectId(exchange.requester_id)})
        requester_info = {
            "requester_name": f"{requester.get('fName', '')} {requester.get('lName', '')}".strip() if requester else "Unknown User",
            "requester_email": requester.get("email", "") if requester else ""
        }
        
        # Get owner details
        owner = await db.users.find_one({"_id": ObjectId(exchange.owner_id)})
        owner_info = {
            "owner_name": f"{owner.get('fName', '')} {owner.get('lName', '')}".strip() if owner else "Unknown User",
            "owner_email": owner.get("email", "") if owner else ""
        }
        
        exchange_response = {
            "id": str(created_exchange["_id"]),
            "requester_id": created_exchange["requester_id"],
            "book_id": created_exchange["book_id"],
            "owner_id": created_exchange["owner_id"],
            "message": created_exchange["message"],
            "status": created_exchange["status"],
            "created_at": created_exchange["created_at"],
            "response": created_exchange.get("response"),
            # Enhanced data
            "book_info": book_info,
            "requester_info": requester_info,
            "owner_info": owner_info
        }
        
        # Create notification for book owner with book name
        notification = Notification(
            user_id=exchange.owner_id,
            type=NotificationType.EXCHANGE_REQUEST,
            title="New Exchange Request",
            message=f"Someone wants to exchange your book '{book_info['book_name']}'",
            data={"exchange_id": exchange_response["id"], "book_name": book_info["book_name"]}
        )
        await db.notifications.insert_one(notification.dict())
        
        return {
            "message": "Exchange request created successfully",
            "exchange": exchange_response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/exchanges/user/{user_id}")
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
            # Get book details
            book = await db.books.find_one({"_id": ObjectId(exchange["book_id"])})
            book_info = {
                "book_name": book.get("bookName", "Unknown Book") if book else "Unknown Book",
                "book_author": book.get("authorName", "Unknown Author") if book else "Unknown Author",
                "book_genre": book.get("genre", "") if book else "",
                "book_condition": book.get("bookCondition", "") if book else ""
            }
            
            # Get requester details
            requester = await db.users.find_one({"_id": ObjectId(exchange["requester_id"])})
            requester_info = {
                "requester_name": f"{requester.get('fName', '')} {requester.get('lName', '')}".strip() if requester else "Unknown User",
                "requester_email": requester.get("email", "") if requester else ""
            }
            
            # Get owner details
            owner = await db.users.find_one({"_id": ObjectId(exchange["owner_id"])})
            owner_info = {
                "owner_name": f"{owner.get('fName', '')} {owner.get('lName', '')}".strip() if owner else "Unknown User",
                "owner_email": owner.get("email", "") if owner else ""
            }
            
            exchange_data = {
                "id": str(exchange["_id"]),
                "requester_id": exchange["requester_id"],
                "book_id": exchange["book_id"],
                "owner_id": exchange["owner_id"],
                "message": exchange["message"],
                "status": exchange["status"],
                "created_at": exchange["created_at"],
                "response": exchange.get("response"),
                # Enhanced data
                "book_info": book_info,
                "requester_info": requester_info,
                "owner_info": owner_info
            }
            exchanges.append(exchange_data)
        
        return {
            "message": f"Found {len(exchanges)} exchanges",
            "total_exchanges": len(exchanges),
            "exchanges": exchanges
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/exchanges/{exchange_id}/respond")
async def respond_to_exchange(exchange_id: str, response: ExchangeResponse):
    try:
        result = await db.exchanges.update_one(
            {"_id": ObjectId(exchange_id)},
            {"$set": {"status": response.response_type, "response": response.dict()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Exchange not found")
            
        updated_exchange = await db.exchanges.find_one({"_id": ObjectId(exchange_id)})
        
        # Get book details
        book = await db.books.find_one({"_id": ObjectId(updated_exchange["book_id"])})
        book_info = {
            "book_name": book.get("bookName", "Unknown Book") if book else "Unknown Book",
            "book_author": book.get("authorName", "Unknown Author") if book else "Unknown Author",
            "book_genre": book.get("genre", "") if book else "",
            "book_condition": book.get("bookCondition", "") if book else ""
        }
        
        exchange_response = {
            "id": str(updated_exchange["_id"]),
            "requester_id": updated_exchange["requester_id"],
            "book_id": updated_exchange["book_id"],
            "owner_id": updated_exchange["owner_id"],
            "message": updated_exchange["message"],
            "status": updated_exchange["status"],
            "created_at": updated_exchange["created_at"],
            "response": updated_exchange.get("response"),
            "book_info": book_info
        }
        
        if response.response_type == ExchangeStatus.ACCEPTED:
            await db.books.update_one(
                {"_id": ObjectId(updated_exchange["book_id"])},
                {"$set": {"is_taken": True}}
            )
            
            # Create notification for requester with book name
            notification = Notification(
                user_id=updated_exchange["requester_id"],
                type=NotificationType.EXCHANGE_RESPONSE,
                title="Exchange Request Accepted",
                message=f"Your request for '{book_info['book_name']}' has been accepted!",
                data={"exchange_id": exchange_id, "book_name": book_info["book_name"]}
            )
            await db.notifications.insert_one(notification.dict())
        elif response.response_type == ExchangeStatus.REJECTED:
            # Create notification for rejection
            notification = Notification(
                user_id=updated_exchange["requester_id"],
                type=NotificationType.EXCHANGE_RESPONSE,
                title="Exchange Request Declined",
                message=f"Your request for '{book_info['book_name']}' was declined.",
                data={"exchange_id": exchange_id, "book_name": book_info["book_name"]}
            )
            await db.notifications.insert_one(notification.dict())
        
        return {
            "message": f"Exchange request {response.response_type.lower()}",
            "exchange": exchange_response
        }
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

@app.post("/ai/chat/{user_id}")
async def ai_chatbot_recommendations(user_id: str, message: dict):
    """AI chatbot that considers user's posted books and preferences"""
    try:
        user_message = message.get("message", "")
        
        # Get user preferences
        preferences = await db.preferences.find_one({"user_id": user_id})
        if not preferences:
            preferences = {
                "favorite_genres": [], 
                "favorite_authors": [],
                "reading_preferences": {}
            }
        
        # Get user's posted books
        user_books = []
        async for book in db.books.find({"user_id": user_id}):
            user_books.append({
                "id": str(book["_id"]),
                "bookName": book.get("bookName", ""),
                "authorName": book.get("authorName", ""),
                "genre": book.get("genre", ""),
                "description": book.get("description", "")
            })
        
        # Get other available books (not user's own books)
        available_books = []
        async for book in db.books.find({
            "user_id": {"$ne": user_id}, 
            "is_taken": False
        }).limit(15):
            available_books.append({
                "id": str(book["_id"]),
                "bookName": book.get("bookName", ""),
                "authorName": book.get("authorName", ""),
                "genre": book.get("genre", ""),
                "description": book.get("description", "")
            })
        
        # AI chat response
        if not ai_service.is_available or not ai_service.model:
            return {
                "response": f"Hi! I can see you have {len(user_books)} books posted. I'm here to help you discover similar books or answer questions about your reading preferences!",
                "user_books_count": len(user_books)
            }
        
        # Create comprehensive chat prompt
        prompt = f"""
        You are a friendly AI book assistant for BookWise. The user has asked: "{user_message}"
        
        USER'S POSTED BOOKS ({len(user_books)} books):
        {json.dumps(user_books, indent=2)}
        
        USER'S PREFERENCES:
        - Favorite Genres: {preferences.get('favorite_genres', [])}
        - Favorite Authors: {preferences.get('favorite_authors', [])}
        - Reading Preferences: {preferences.get('reading_preferences', {})}
        
        AVAILABLE BOOKS TO RECOMMEND:
        {json.dumps(available_books[:10], indent=2)}
        
        Instructions:
        1. Reference their posted books to understand their taste
        2. Use their preferences to make relevant suggestions
        3. Give book name, author, and ONE line description for recommendations
        4. Be conversational and encouraging
        5. Keep response under 150 words
        6. If they ask about their books, mention specific titles
        """
        
        response = ai_service.model.generate_content(prompt)
        
        return {
            "response": response.text.strip(),
            "user_books_count": len(user_books),
            "available_books_count": len(available_books)
        }
        
    except Exception as e:
        return {
            "response": f"Hi! I can see you've posted some great books. I'm here to help you discover new reads and chat about your book preferences! What would you like to know?",
            "error": str(e)
        }

@app.get("/books/authors")
async def get_all_authors():
    """Get all unique authors from books"""
    try:
        # Get all unique authors from books collection
        authors = await db.books.distinct("authorName")
        authors = [author for author in authors if author and author.strip()]  # Remove empty/null authors
        authors.sort()  # Sort alphabetically
        
        return {
            "message": f"Found {len(authors)} unique authors",
            "total_authors": len(authors),
            "authors": authors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/books/genres")
async def get_all_genres():
    """Get all unique genres from books"""
    try:
        # Get all unique genres from books collection
        genres = await db.books.distinct("genre")
        genres = [genre for genre in genres if genre and genre.strip()]  # Remove empty/null genres
        genres.sort()  # Sort alphabetically
        
        return {
            "message": f"Found {len(genres)} unique genres",
            "total_genres": len(genres),
            "genres": genres
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ai/book-matches/{user_id}")
async def get_book_matches_by_preferences(user_id: str):
    """Get book matches based on user preferences with percentage - improved algorithm"""
    try:
        # Get user preferences
        preferences = await db.preferences.find_one({"user_id": user_id})
        if not preferences:
            return {
                "message": "Please set your preferences first to get personalized matches",
                "matches": []
            }
        
        # Get available books (excluding user's own books)
        available_books = []
        async for book in db.books.find({
            "user_id": {"$ne": user_id}, 
            "is_taken": False
        }):
            available_books.append({
                "id": str(book["_id"]),
                "bookName": book.get("bookName", ""),
                "authorName": book.get("authorName", ""),
                "genre": book.get("genre", ""),
                "description": book.get("description", ""),
                "bookCondition": book.get("bookCondition", ""),
                "user_id": book.get("user_id", "")
            })
        
        # Get user's favorite genres as strings
        user_genres = [str(genre) for genre in preferences.get("favorite_genres", [])]
        user_authors = preferences.get("favorite_authors", [])
        
        # Calculate match percentages with improved algorithm
        book_matches = []
        for book in available_books:
            match_percentage = 0
            match_reasons = []
            
            # Direct genre matching (50% weight)
            book_genre = book.get("genre", "").strip()
            if book_genre and book_genre in user_genres:
                match_percentage += 50
                match_reasons.append(f"Exact genre match: {book_genre}")
            
            # Description-based genre matching (30% weight)
            book_description = book.get("description", "").lower()
            book_title = book.get("bookName", "").lower()
            
            # Check if any preferred genre appears in description or title
            for genre in user_genres:
                genre_lower = genre.lower()
                if genre_lower in book_description or genre_lower in book_title:
                    match_percentage += 30
                    match_reasons.append(f"Genre '{genre}' found in description/title")
                    break  # Only count once
            
            # Author matching (40% weight)
            book_author = book.get("authorName", "").strip()
            if book_author and book_author in user_authors:
                match_percentage += 40
                match_reasons.append(f"Favorite author: {book_author}")
            
            # Keyword matching in description (20% weight)
            # Check for genre-related keywords
            genre_keywords = {
                "Fantasy": ["magic", "wizard", "dragon", "fantasy", "magical", "kingdom", "quest", "adventure"],
                "Science Fiction": ["space", "future", "robot", "alien", "technology", "sci-fi", "planet", "galaxy"],
                "Mystery": ["mystery", "detective", "crime", "murder", "investigation", "clue", "suspect"],
                "Thriller": ["thriller", "suspense", "action", "danger", "chase", "spy", "tension"],
                "Romance": ["love", "romance", "heart", "relationship", "passion", "wedding"],
                "History": ["history", "historical", "war", "ancient", "century", "past", "empire"],
                "Biography": ["biography", "life", "story", "memoir", "autobiography", "real", "true"],
                "Classic": ["classic", "literature", "timeless", "masterpiece", "acclaimed"],
                "Philosophy": ["philosophy", "wisdom", "thinking", "mind", "existence", "meaning"],
                "Adventure": ["adventure", "journey", "exploration", "travel", "expedition", "discover"]
            }
            
            for user_genre in user_genres:
                if user_genre in genre_keywords:
                    keywords = genre_keywords[user_genre]
                    for keyword in keywords:
                        if keyword in book_description:
                            match_percentage += 20
                            match_reasons.append(f"Found '{keyword}' related to {user_genre}")
                            break  # Only count once per genre
                    if match_percentage > 0:  # Found at least one keyword
                        break
            
            # Reading preferences bonus (10% weight)
            reading_prefs = preferences.get("reading_preferences", {})
            if reading_prefs:
                if book.get("bookCondition") in ["New", "Like New", "Good"]:
                    match_percentage += 10
                    match_reasons.append("Good condition book")
            
            # Base recommendation for books with no direct matches but good quality (20%)
            if match_percentage == 0 and book.get("bookCondition") in ["New", "Like New"]:
                match_percentage = 20
                match_reasons.append("High quality book for exploration")
            
            # Lower threshold to show more matches
            if match_percentage >= 20:
                book_matches.append({
                    "book_id": book["id"],
                    "book_name": book["bookName"],
                    "author_name": book["authorName"],
                    "genre": book["genre"],
                    "description": book["description"][:100] + "..." if len(book.get("description", "")) > 100 else book.get("description", ""),
                    "match_percentage": min(match_percentage, 100),  # Cap at 100%
                    "match_reasons": match_reasons,
                    "book_condition": book["bookCondition"]
                })
        
        # Sort by match percentage
        book_matches.sort(key=lambda x: x["match_percentage"], reverse=True)
        
        return {
            "message": f"Found {len(book_matches)} books matching your preferences",
            "total_matches": len(book_matches),
            "user_preferences": {
                "favorite_genres": preferences.get("favorite_genres", []),
                "favorite_authors": preferences.get("favorite_authors", []),
                "reading_preferences": preferences.get("reading_preferences", {})
            },
            "matches": book_matches[:20]  # Limit to top 20 matches
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
@app.get("/books/")
async def get_all_books(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    try:
        books_cursor = db.books.find().skip(skip).limit(limit).sort("created_at", -1)
        books = []
        async for book in books_cursor:
            books.append(serialize_book(book))

        total_books = await db.books.count_documents({})
        
        return {
            "message": "Books fetched successfully",
            "total_books": total_books,
            "returned_books": len(books),
            "skip": skip,
            "limit": limit,
            "books": books
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching books: {str(e)}")

@app.get("/users/{user_id}/books")
async def get_user_books(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    try:
        # Verify user exists
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Get user's books
        books_cursor = db.books.find({"user_id": user_id}).skip(skip).limit(limit).sort("created_at", -1)
        books = []
        async for book in books_cursor:
            books.append(serialize_book(book))

        total_user_books = await db.books.count_documents({"user_id": user_id})
        
        return {
            "message": f"Books for user {user['fName']} {user['lName']} fetched successfully",
            "user_id": user_id,
            "user_name": f"{user['fName']} {user['lName']}",
            "total_user_books": total_user_books,
            "returned_books": len(books),
            "skip": skip,
            "limit": limit,
            "books": books
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user books: {str(e)}")

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

@app.delete("/books/{book_id}")
async def delete_book(book_id: str):
    try:
        # Check if book exists
        book = await db.books.find_one({"_id": ObjectId(book_id)})
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
            
        # Delete the book
        result = await db.books.delete_one({"_id": ObjectId(book_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Book not found")
            
        return {"message": "Book deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting book: {str(e)}")

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
            "author_name": book.get("authorName"),  # Fixed: using authorName
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