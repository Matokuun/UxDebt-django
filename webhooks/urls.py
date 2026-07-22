from django.urls import path
from .api import GithubWebhookAPI

urlpatterns = [
    path('github', GithubWebhookAPI.as_view()),
]