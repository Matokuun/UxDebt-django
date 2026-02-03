from django.urls import path
from .api import GithubWebookAPI

urlpatterns = [
    path('', GithubWebookAPI.as_view()),
]