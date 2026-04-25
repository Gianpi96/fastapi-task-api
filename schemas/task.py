from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=3)
    description: Optional[str] = None
    completed: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if value.isdigit():
            raise ValueError("Il titolo non può contenere solo numeri")
        return value.capitalize()


class TaskResponse(TaskCreate):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: int
    owner_id: int
