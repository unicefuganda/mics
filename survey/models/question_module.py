from survey.models import BaseModel
from django.db import models


class QuestionModule(BaseModel):
    name = models.CharField(max_length=255)