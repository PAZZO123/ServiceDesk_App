from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


class APISchema(BaseModel):
    model_config=ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )
    
    #Reusable pwd type
def _check_password_strength(value:str) ->str:
    if value.isdigit():
        raise ValueError("Password cannot be only numbers.")
    if value.lower() in {"password", "12345678", "quertyui", "servicedesk"}:
        raise ValueError("that password is too common.")
    return value
PasswordStr=Annotated[
    str,
    Field(
        min_length=8,
        max_length=72,
        description="8-72 characters."
    ),
    AfterValidator(_check_password_strength)
]

class Message(APISchema):

    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"message": "Password updated successfully."}
        }
    )


class Page[T](APISchema):
    items: list[T]
    total: int = Field(description="Total rows matching the filter.")
    page: int = Field(description="Current page, 1-based.")
    size: int = Field(description="Rows per page.")
    pages: int = Field(description="Total number of pages.")
    
    @classmethod
    def create(cls, items: list[T], total:int, page:int,size:int)->"Page[T]":
        total_pages=-(-total//size) if size else 0
        return cls(items=items, total=total, page=page, size=size, pages=total_pages)
    
class PaginationParams(APISchema):
    
    page: int = Field(default=1, ge=1, description="1-based page number.")
    size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Rows per page (max 100).",
    )
    @property
    def offset(self) ->int:
        return (self.page-1)*self.size