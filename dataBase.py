import motor.motor_asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")  # Ensure this matches the .env variable name
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client.bookwisedb  # Your database name here
