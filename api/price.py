from pydantic import BaseModel, validator, ValidationError


class RecipeServingPrice(BaseModel):
    recipe_name: str
    serving_size: int
    price: float

    @validator('serving_size')
    def validate_serving_size(cls, serving_size: int) -> int:
        valid_serving_sizes = [2, 4, 6]
        if serving_size not in valid_serving_sizes:
            raise ValidationError("Invalid serving size.")
        return serving_size