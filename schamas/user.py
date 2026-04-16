from pydantic import BaseModel, Field, ConfigDict
# -----------------------
# USER SCHEMAS
# -----------------------


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    email: str
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_active: bool
