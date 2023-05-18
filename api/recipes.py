from pydantic import BaseModel


class CandidateRecipe(BaseModel):
    contributor_name: str
    recipe_name: str
    description: str
    image_url: str

    class Config:
        orm_mode = True


class StarRecipe(BaseModel):
    verification_code: str
    recipe_id: int

    class Config:
        orm_mode = True
