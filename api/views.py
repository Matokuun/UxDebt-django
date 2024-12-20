from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from .models import Repository, Issue, Tag, IssueTag, Status
from .serializers import RepositoryCreateSerializer, RepositoryGetAllSerializer, IssueSerializer, TagSerializer, IssueTagSerializer, GetIssueViewModelSerializer
from .filters import IssueFilter
from .services import GitService
from django.http import HttpResponse
import requests

class RepositoryViewSet(viewsets.ModelViewSet):
    queryset = Repository.objects.all()
    # serializer_class = RepositorySerializer
    # permission_classes = [IsAuthenticated]
    # filter_backends = (DjangoFilterBackend,)
    # filterset_class = RepositoryFilter
    # pagination_class = PageNumberPagination

    @action(detail=False, methods=['post'], url_path='Create')
    def Create(self, request, *args, **kwargs):
        serializer = RepositoryCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
    
    @action(detail=False, methods=['get'], url_path='GetAll')
    def GetAll(self, request, *args, **kwargs):
        repositories = self.queryset.all()
        serializer = RepositoryGetAllSerializer(repositories, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='DownloadNewRepository/(?P<owner>[^/.]+)/(?P<name>[^/.]+)')
    def download_new_repository(self, request, owner, name):
        try:
            api_url = f'https://api.github.com/repos/{owner}/{name}'

            response = requests.get(api_url)

            if response.status_code != 200:
                return Response({'error': 'Repository not found or error fetching data.'}, status=status.HTTP_404_NOT_FOUND)

            repo_data = response.json()

            existing_repo = Repository.objects.filter(owner=owner, name=name).first()

            if existing_repo:
                existing_repo.git_id = repo_data['id']
                existing_repo.html_url = repo_data['html_url']
                existing_repo.description = repo_data.get('description', '')
                existing_repo.save()
                return Response({'status': 'Repository updated successfully!'}, status=status.HTTP_200_OK)
            else:
                new_repo = Repository(
                    owner=owner,
                    name=name,
                    git_id=repo_data['id'],
                    html_url=repo_data['html_url'],
                    description=repo_data.get('description', '')
                )
                new_repo.save()

                return Response({'status': 'Repository downloaded and created successfully!'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='UpdateRepository')
    def update_repository(self, request, pk=None):
        try:
            repo = self.get_object()

            api_url = f'https://api.github.com/repos/{repo.owner}/{repo.name}'
            response = requests.get(api_url)

            if response.status_code != 200:
                return Response({'error': 'Error fetching repository data from GitHub.'}, status=status.HTTP_404_NOT_FOUND)

            repo_data = response.json()

            repo.git_id = repo_data['id']
            repo.html_url = repo_data['html_url']
            repo.description = repo_data.get('description', '')
            repo.save()

            issues_url = f'https://api.github.com/repos/{repo.owner}/{repo.name}/issues'
            issues_response = requests.get(issues_url)

            if issues_response.status_code != 200:
                return Response({'error': 'Error fetching issues from GitHub.'}, status=status.HTTP_404_NOT_FOUND)

            issues_data = issues_response.json()

            return Response({'status': 'Repository and issues updated successfully!'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    # permission_classes = [IsAuthenticated]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IssueFilter

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=['post'], url_path='SwitchDiscarded/(?P<pk>[^/.]+)')
    def SwitchDiscarded(self, request, pk=None):
        issue = self.get_object()
        issue.discarded = not issue.discarded  # Cambia el estado de descartado (opuesto)
        issue.save()
        return Response({'status': 'Issue discarded' if issue.discarded else 'Issue restored'}, status=status.HTTP_200_OK)


    @action(detail=False, methods=['post'], url_path='GetAllByFilter/(?P<pageNumber>\\d+)/(?P<pageSize>\\d+)')
    def GetAllByFilter(self, request, pageNumber=None, pageSize=None):
        try:
            filter_data = request.data

            status_map = {
                0: Status.OPEN,
                1: Status.CLOSED,
                2: Status.ALL
            }


            # Aplicar filtros
            queryset = Issue.objects.all()
            queryset = queryset.order_by('created_at')

            # Solo aplicar filtros si tienen un valor válido
            if filter_data.get('Title'):
                queryset = queryset.filter(title__icontains=filter_data['Title'])

            if filter_data.get('Status') is not None:
                status_value = filter_data.get('Status')
                status = status_map.get(int(status_value), Status.ALL) 
                if status != Status.ALL:
                    queryset = queryset.filter(status=status)

            if filter_data.get('Discarded') is not None:
                queryset = queryset.filter(discarded=filter_data['Discarded'])
            if filter_data.get('RepositoryId'):
                queryset = queryset.filter(repository_id=filter_data['RepositoryId'])
            if filter_data.get('CreatedAt'):
                queryset = queryset.filter(created_at=filter_data['CreatedAt'])
            if filter_data.get('Tags') and filter_data['Tags']:
                queryset = queryset.filter(tags__id__in=filter_data['Tags']).distinct()

            # Paginar los resultados
            paginator = PageNumberPagination()
            paginator.page_size = int(pageSize) if pageSize else 10
            paginated_queryset = paginator.paginate_queryset(queryset, request)

            # Serializar los datos
            serializer = GetIssueViewModelSerializer(paginated_queryset, many=True)

            return Response({
                'count': paginator.page.paginator.count,
                'items': serializer.data,
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
            })

        except Exception as ex:
            return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['put'], url_path='Update/(?P<id>\d+)')
    def Update(self, request, id=None):
        print(request.data)
        try:
            issue = get_object_or_404(Issue, pk=id)

            serializer = IssueSerializer(issue, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as ex:
            return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    # permission_classes = [IsAuthenticated]
    filter_backends = (DjangoFilterBackend,)

    @action(detail=False, methods=['get'], url_path='GetAll')
    def GetAll(self, request, *args, **kwargs):
        tags = self.queryset.all()
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put'], url_path='Update/(?P<id>\d+)')
    def Update(self, request, id=None):
        print(request.data)
        try:
            issue = get_object_or_404(Issue, pk=id)

            serializer = IssueSerializer(issue, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as ex:
            return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='AddTagToIssue')
    def AddTagToIssue(self, request):
        tags_id = request.data.get('tagsId')
        issue_id = request.data.get('issueId')

        print("Received data:", request.data)
        
        # Validar que ambos IDs estén presentes
        if not tags_id or not issue_id:
            return Response({'error': 'tagsId and issueId are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(tags_id, list):
            return Response({'error': 'tagsId must be a list.'}, status=status.HTTP_400_BAD_REQUEST)
        
        issue = get_object_or_404(Issue, issue_id=issue_id)

        if tags_id:
            tags = []
            for tag_id in tags_id:
                try:
                    tag = get_object_or_404(Tag, tagId=tag_id)
                    tags.append(tag)
                except Tag.DoesNotExist:
                    return Response({'error': f'Tag with id {tag_id} does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

            issue.tags.set(tags)
            issue.save()

            return Response({'status': 'Tags added to Issue successfully.'}, status=status.HTTP_201_CREATED)
        
        else:
            issue.tags.clear()
            return Response({'status': 'Tags removed from Issue successfully.'}, status=status.HTTP_200_OK)

class IssueTagViewSet(viewsets.ModelViewSet):
    queryset = IssueTag.objects.all()
    serializer_class = IssueTagSerializer

class GitViewSet(viewsets.ViewSet):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.git_service = GitService()

    @action(detail=False, methods=['post'], url_path='DownloadNewRepository/(?P<owner>[^/.]+)/(?P<repository>[^/.]+)')
    def download_new_repository(self, request, owner, repository):
        """Descargar un nuevo repositorio y sus issues."""
        try:
            issues = self.git_service.download_new_repository(owner, repository)
            if not issues['is_success']:
                return Response({"error": issues['message']}, status=issues['response_code'])
            return Response(issues, status=status.HTTP_200_OK)

        except Exception as ex:
            return Response({"error": str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='UpdateRepository/(?P<repository_id>[^/.]+)')
    def update_repository(self, request, repository_id):
        """Actualizar un repositorio y sus issues."""
        try:
            issues = self.git_service.update_repository(repository_id)
            if not issues['is_success']:
                return Response({"error": issues['message']}, status=issues['response_code'])
            return Response(issues, status=status.HTTP_200_OK)

        except Exception as ex:
            return Response({"error": str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def home(request):
    return HttpResponse("Bienvenido a la API de UxDebt. Usa /api/ para acceder a los endpoints.")

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100