from sqlalchemy.orm import configure_mappers

from app.entities.base import Base
from app.entities.user import User
from app.entities.conversation import Conversation
from app.entities.message import Message

configure_mappers()

print("Registered tables:", list(Base.metadata.tables.keys()))
print("All entity mappings configured successfully.")
