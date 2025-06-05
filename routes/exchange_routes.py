from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from models.exchange_models import ExchangeRequest, ExchangeResponse, ExchangeDetails, ExchangeStatus
from dataBase import db

router = APIRouter(prefix="/exchanges", tags=["exchanges"])

@router.post("/request", response_model=ExchangeDetails)
async def request_exchange(exchange: ExchangeRequest):
    try:
        # Verify book exists and is available
        book = await db.books.find_one({"_id": ObjectId(exchange.book_id)})
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        if book.get("is_taken", False):
            raise HTTPException(status_code=400, detail="Book is not available for exchange")

        # Create exchange request
        exchange_dict = exchange.dict()
        exchange_dict["created_at"] = datetime.utcnow()
        result = await db.exchanges.insert_one(exchange_dict)
        
        # Get created exchange
        created_exchange = await db.exchanges.find_one({"_id": result.inserted_id})
        created_exchange["id"] = str(created_exchange["_id"])
        del created_exchange["_id"]
        
        return created_exchange
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}", response_model=List[ExchangeDetails])
async def get_user_exchanges(
    user_id: str,
    status: Optional[ExchangeStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    try:
        query = {
            "$or": [
                {"requester_id": user_id},
                {"owner_id": user_id}
            ]
        }
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

@router.put("/{exchange_id}/respond", response_model=ExchangeDetails)
async def respond_to_exchange(exchange_id: str, response: ExchangeResponse):
    try:
        # Update exchange status
        result = await db.exchanges.update_one(
            {"_id": ObjectId(exchange_id)},
            {
                "$set": {
                    "status": response.response_type,
                    "response": response.dict()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Exchange not found")
            
        # Get updated exchange
        updated_exchange = await db.exchanges.find_one({"_id": ObjectId(exchange_id)})
        updated_exchange["id"] = str(updated_exchange["_id"])
        del updated_exchange["_id"]
        
        # Update book status if exchange is accepted
        if response.response_type == ExchangeStatus.ACCEPTED:
            await db.books.update_one(
                {"_id": ObjectId(updated_exchange["book_id"])},
                {"$set": {"is_taken": True}}
            )
        
        return updated_exchange
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{exchange_id}/complete", response_model=ExchangeDetails)
async def complete_exchange(exchange_id: str):
    try:
        # Verify exchange exists and is accepted
        exchange = await db.exchanges.find_one({"_id": ObjectId(exchange_id)})
        if not exchange:
            raise HTTPException(status_code=404, detail="Exchange not found")
        if exchange["status"] != ExchangeStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="Exchange must be accepted before completion")

        # Update exchange status
        result = await db.exchanges.update_one(
            {"_id": ObjectId(exchange_id)},
            {"$set": {"status": ExchangeStatus.COMPLETED}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Exchange not found")
            
        # Get updated exchange
        updated_exchange = await db.exchanges.find_one({"_id": ObjectId(exchange_id)})
        updated_exchange["id"] = str(updated_exchange["_id"])
        del updated_exchange["_id"]
        
        return updated_exchange
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 