from django.urls import path
from .api import GithubWebhookAPI

urlpatterns = [
    path('', GithubWebhookAPI.as_view()),
]