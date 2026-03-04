from pydantic import BaseModel


class RefreshToken(BaseModel):
    refresh_token: str


class Tokens(BaseModel):
    refresh_token: str
    access_token: str
    token_type: str


class ChangePassword(BaseModel):
    old_password: str
    new_password: str
