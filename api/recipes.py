from pydantic import BaseModel


class CandidateRecipe(BaseModel):
    recipe_contributor_name: str
    name: str
    description: str
    image_url: str

    class Config:
        orm_mode = True

class StarRecipe(BaseModel):
    verification_code: str
    recipe_name: str

    class Config:
        orm_mode = True
