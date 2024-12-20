from rest_framework.routers import DefaultRouter
from .views import RepositoryViewSet, IssueViewSet, TagViewSet, IssueTagViewSet, GitViewSet

router = DefaultRouter()
router.register(r'Repository', RepositoryViewSet, basename='repository')
router.register(r'Issue', IssueViewSet, basename='issue')
router.register(r'Tag', TagViewSet)
router.register(r'issue-tag', IssueTagViewSet)
router.register(r'Git', GitViewSet, basename='git')

urlpatterns = router.urls
