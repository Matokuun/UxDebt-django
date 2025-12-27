from rest_framework.routers import DefaultRouter
from .views import RepositoryViewSet, IssueViewSet, TagViewSet, IssueTagViewSet, GitViewSet, GitConfigViewSet, RegisterView, LogoutView, ProjectViewSet
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r'Repository', RepositoryViewSet, basename='repository')
router.register(r'Issue', IssueViewSet, basename='issue')
router.register(r'Tag', TagViewSet)
router.register(r'issue-tag', IssueTagViewSet)
router.register(r'Git', GitViewSet, basename='git')
router.register(r'GitHubToken', GitConfigViewSet, basename='github-token')
router.register(r'project', ProjectViewSet, basename='project')

urlpatterns = [
    path('auth/register/', RegisterView.as_view()),
    path('auth/login/', TokenObtainPairView.as_view()),
    path('auth/refresh/', TokenRefreshView.as_view()),
    path('auth/logout/', LogoutView.as_view()),
]

urlpatterns += router.urls
