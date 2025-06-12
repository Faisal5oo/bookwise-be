import google.generativeai as genai
import json
from typing import List, Dict, Any
from models.preference_models import AIRecommendation
from datetime import datetime

# Configure Gemini AI
GEMINI_API_KEY = "AIzaSyARpf8-ge_UkDa4s4b3ANhVMCywqjp9WW4"
# genai.configure(api_key=GEMINI_API_KEY)

class AIRecommendationService:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-pro')
    
    async def generate_book_recommendations(
        self, 
        user_id: str, 
        user_preferences: Dict[str, Any], 
        reading_history: Dict[str, Any], 
        available_books: List[Dict[str, Any]]
    ) -> List[AIRecommendation]:
        """Generate AI-powered book recommendations using Gemini"""
        
        try:
            # Prepare context for AI
            context = self._prepare_recommendation_context(
                user_preferences, reading_history, available_books
            )
            
            # Generate recommendations using Gemini
            prompt = self._create_recommendation_prompt(context)
            response = self.model.generate_content(prompt)
            
            # Parse AI response
            recommendations = self._parse_ai_response(user_id, response.text, available_books)
            
            return recommendations
            
        except Exception as e:
            print(f"AI Recommendation Error: {str(e)}")
            # Fallback to simple recommendations if AI fails
            return self._fallback_recommendations(user_id, user_preferences, available_books)
    
    def _prepare_recommendation_context(
        self, 
        preferences: Dict[str, Any], 
        reading_history: Dict[str, Any], 
        books: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare context data for AI recommendation"""
        
        return {
            "user_preferences": {
                "favorite_genres": preferences.get("favorite_genres", []),
                "favorite_authors": preferences.get("favorite_authors", []),
                "reading_habits": preferences.get("reading_preferences", {})
            },
            "reading_stats": {
                "books_read": reading_history.get("books_read", 0) if reading_history else 0,
                "top_genres": reading_history.get("top_genres", []) if reading_history else [],
                "pages_read": reading_history.get("pages_read", 0) if reading_history else 0
            },
            "available_books": [
                {
                    "id": book["id"],
                    "title": book.get("bookName", ""),
                    "author": book.get("author", ""),
                    "genre": book.get("genre", ""),
                    "description": book.get("description", ""),
                    "condition": book.get("bookCondition", "")
                }
                for book in books[:50]  # Limit to avoid token limits
            ]
        }
    
    def _create_recommendation_prompt(self, context: Dict[str, Any]) -> str:
        """Create a detailed prompt for Gemini AI"""
        
        prompt = f"""
        You are an expert book recommendation system for a book exchange platform called BookWise.
        
        USER PROFILE:
        - Favorite Genres: {', '.join(context['user_preferences']['favorite_genres']) if context['user_preferences']['favorite_genres'] else 'Not specified'}
        - Favorite Authors: {', '.join(context['user_preferences']['favorite_authors']) if context['user_preferences']['favorite_authors'] else 'Not specified'}
        - Books Read: {context['reading_stats']['books_read']}
        - Top Genres: {', '.join(context['reading_stats']['top_genres']) if context['reading_stats']['top_genres'] else 'Not specified'}
        - Pages Read: {context['reading_stats']['pages_read']}
        
        AVAILABLE BOOKS:
        {json.dumps(context['available_books'], indent=2)}
        
        INSTRUCTIONS:
        1. Analyze the user's preferences and reading history
        2. Match them with the most suitable books from the available list
        3. Consider genre preferences, author preferences, and reading patterns
        4. Provide a match percentage (0-100) for each recommended book
        5. Give a clear, personalized reason for each recommendation
        6. Only recommend books that truly match the user's interests
        7. Prioritize diversity in recommendations while staying true to preferences
        
        RESPONSE FORMAT (JSON only, no other text):
        [
            {{
                "book_id": "book_id_here",
                "match_percentage": 85,
                "reason": "This book matches your love for fantasy novels and features your favorite author's writing style."
            }}
        ]
        
        Recommend 5-10 books with match percentage above 60%. If no good matches exist, return empty array [].
        """
        
        return prompt
    
    def _parse_ai_response(
        self, 
        user_id: str, 
        ai_response: str, 
        available_books: List[Dict[str, Any]]
    ) -> List[AIRecommendation]:
        """Parse AI response and create recommendation objects"""
        
        try:
            # Clean the response to extract JSON
            response_text = ai_response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            ai_recommendations = json.loads(response_text)
            
            recommendations = []
            book_ids = {book["id"]: book for book in available_books}
            
            for rec in ai_recommendations:
                if rec["book_id"] in book_ids and rec["match_percentage"] >= 60:
                    recommendation = AIRecommendation(
                        user_id=user_id,
                        book_id=rec["book_id"],
                        match_percentage=rec["match_percentage"],
                        reason=rec["reason"],
                        created_at=datetime.utcnow()
                    )
                    recommendations.append(recommendation)
            
            return recommendations
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing AI response: {str(e)}")
            print(f"AI Response: {ai_response}")
            # Return empty list if parsing fails
            return []
    
    def _fallback_recommendations(
        self, 
        user_id: str, 
        preferences: Dict[str, Any], 
        available_books: List[Dict[str, Any]]
    ) -> List[AIRecommendation]:
        """Fallback recommendation system if AI fails"""
        
        recommendations = []
        
        for book in available_books[:10]:  # Limit to 10 books
            match_percentage = 0
            reasons = []
            
            # Match by genre
            if book.get("genre") in preferences.get("favorite_genres", []):
                match_percentage += 40
                reasons.append(f"Matches your favorite genre: {book['genre']}")
            
            # Match by author
            if book.get("author") in preferences.get("favorite_authors", []):
                match_percentage += 30
                reasons.append(f"By your favorite author: {book['author']}")
            
            # Basic scoring for unknown preferences
            if not preferences.get("favorite_genres") and not preferences.get("favorite_authors"):
                match_percentage = 50
                reasons.append("New discovery based on general popularity")
            
            if match_percentage >= 30:
                recommendation = AIRecommendation(
                    user_id=user_id,
                    book_id=book["id"],
                    match_percentage=match_percentage,
                    reason=", ".join(reasons) if reasons else "Recommended for exploration",
                    created_at=datetime.utcnow()
                )
                recommendations.append(recommendation)
        
        return recommendations

    async def generate_reading_insights(
        self, 
        user_id: str, 
        reading_stats: Dict[str, Any], 
        interactions: List[Dict[str, Any]]
    ) -> str:
        """Generate AI-powered reading insights"""
        
        try:
            prompt = f"""
            Analyze this user's reading behavior and provide personalized insights:
            
            READING STATISTICS:
            - Books Read: {reading_stats.get('books_read', 0)}
            - Pages Read: {reading_stats.get('pages_read', 0)}
            - Authors Explored: {reading_stats.get('authors_explored', 0)}
            - Top Genres: {reading_stats.get('top_genres', [])}
            
            RECENT INTERACTIONS:
            {json.dumps(interactions[-20:], indent=2) if interactions else 'No recent interactions'}
            
            Provide 3-4 brief, encouraging insights about their reading habits, preferences, and suggestions for improvement.
            Keep it positive and motivational. Format as a simple paragraph.
            """
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            print(f"AI Insights Error: {str(e)}")
            return "Keep up the great reading habits! Every book you explore expands your knowledge and imagination."

# Global AI service instance
ai_service = AIRecommendationService() 