from pydantic import BaseModel

class UrlContainer(BaseModel):
    url: str