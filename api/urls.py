from rest_framework.routers import DefaultRouter
from .views import RepositoryViewSet, IssueViewSet, TagViewSet, IssueTagViewSet, GitViewSet, GitConfigViewSet

router = DefaultRouter()
router.register(r'Repository', RepositoryViewSet, basename='repository')
router.register(r'Issue', IssueViewSet, basename='issue')
router.register(r'Tag', TagViewSet)
router.register(r'issue-tag', IssueTagViewSet)
router.register(r'Git', GitViewSet, basename='git')
router.register(r'GitHubToken', GitConfigViewSet, basename='github-token')

urlpatterns = router.urls
