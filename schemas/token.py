from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Schema esplicito per la risposta del login — nessun campo sensibile."""

    access_token: str
    token_type: str
