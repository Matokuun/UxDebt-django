from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from .models import Repository, Issue, Tag, IssueTag, GitHubToken
from .serializers import RepositoryGetAllSerializer, IssueSerializer, TagSerializer, IssueTagSerializer, GetIssueViewModelSerializer, GitConfigSerializer
from .filters import IssueFilter
from .services import GitService
from django.http import HttpResponse
from django.conf import settings
import requests
from django.core.paginator import Paginator
from datetime import datetime
import openpyxl

class RepositoryViewSet(viewsets.ModelViewSet):
    queryset = Repository.objects.all()
    # serializer_class = RepositorySerializer
    # permission_classes = [IsAuthenticated]
    # filter_backends = (DjangoFilterBackend,)
    # filterset_class = RepositoryFilter
    # pagination_class = PageNumberPagination

    @action(detail=False, methods=['post'], url_path='Create')
    def Create(self, request, *args, **kwargs):
        owner = request.data.get('owner')
        name = request.data.get('name')

        if not owner or not name:
            return Response({'error': 'Propietario y Repositorio son campos requeridos.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if Repository.objects.filter(name=name, owner=owner).exists():
            return Response(
                {'error': 'El repositorio ingresado ya existe'},
                status=status.HTTP_400_BAD_REQUEST
            )

        git_service = GitService()

        try:
            issues = git_service.download_new_repository(owner, name)

            if not issues['is_success']:
                return Response(
                    {"error": issues['message']},
                    status=issues['response_code']
                )

            return Response(issues, status=status.HTTP_200_OK)
        
        except Exception as ex:
            return Response({"error": str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='GetAll')
    def GetAll(self, request, *args, **kwargs):
        repositories = self.queryset.all().order_by('name')
        serializer = RepositoryGetAllSerializer(repositories, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='UpdateRepository')
    def update_repository(self, request, pk=None):
        try:
            repo = self.get_object()

            api_url = f'https://api.github.com/repos/{repo.owner}/{repo.name}'
            response = requests.get(api_url)

            if response.status_code != 200:
                return Response({'error': 'Error al obtener los datos del repositorio desde GitHub.'}, status=status.HTTP_404_NOT_FOUND)

            repo_data = response.json()

            repo.git_id = repo_data['id']
            repo.html_url = repo_data['html_url']
            repo.description = repo_data.get('description', '')
            repo.save()

            issues_url = f'https://api.github.com/repos/{repo.owner}/{repo.name}/issues'
            issues_response = requests.get(issues_url)

            if issues_response.status_code != 200:
                return Response({'error': 'Error al obtener los issues desde GitHub.'}, status=status.HTTP_404_NOT_FOUND)

            return Response({'status': 'Repositorio e issues actualizados correctamente!'}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='fetch-github-repos')
    def fetch_github_repos(self, request):
        owner = request.query_params.get('owner')

        if not owner:
            return Response({'error': 'El propietario es requerido'}, status=status.HTTP_400_BAD_REQUEST)

        github_url = f'https://api.github.com/users/{owner}/repos'
        headers = {'Authorization': f'Bearer {settings.GITHUB_TOKEN}'}

        try:
            response = requests.get(github_url, headers=headers)
            
            if response.status_code != 200:
                return Response({'error': 'Error al obtener los repositorios desde GitHub'}, status=status.HTTP_404_NOT_FOUND)

            repos = response.json()
            return Response({'repos': repos}, status=status.HTTP_200_OK)
        
        except requests.exceptions.RequestException as e:
            return Response({'error': f'Error al obtener la información desde GitHub: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    # permission_classes = [IsAuthenticated]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IssueFilter

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=['get'], url_path='GetAll')
    def GetAll(self, request, *args, **kwargs):
        issues = self.queryset.all().order_by('title').distinct('title')
        serializer = IssueSerializer(issues, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='SwitchDiscarded/(?P<pk>[^/.]+)')
    def SwitchDiscarded(self, request, pk=None):
        issue = self.get_object()
        issue.discarded = not issue.discarded
        issue.save()
        return Response({'status': 'Issue cerrado' if issue.discarded else 'Issue abierto'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='GetAllByFilter')
    def GetAllByFilter(self, request, *args, **kwargs):
        filter_data = request.data
        queryset = Issue.objects.all()

        if filter_data.get('Title'):
            queryset = queryset.filter(title__icontains=filter_data['Title'])
        
        if filter_data.get('Status') is not None:
            queryset = queryset.filter(status=filter_data['Status'])

        if filter_data.get('Discarded') is not None:
            queryset = queryset.filter(discarded=filter_data['Discarded'])

        if filter_data.get('RepositoryId'):
            queryset = queryset.filter(repository_id__in=filter_data['RepositoryId'])

        if filter_data.get('Tags'):
            queryset = queryset.filter(tags__tagId__in=filter_data['Tags']).distinct()

        if filter_data.get('startDate') and filter_data.get('endDate'):
            try:
                start_date = datetime.fromisoformat(filter_data['startDate'].replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(filter_data['endDate'].replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__range=[start_date, end_date])
            except ValueError:
                return Response({'error': 'Formato de fecha inválido. Esperado: YYYY-MM-DDTHH:MM:SSZ.'}, status=status.HTTP_400_BAD_REQUEST)

        elif filter_data.get('startDate'):
            try:
                start_date = datetime.fromisoformat(filter_data['startDate'].replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=start_date)
            except ValueError:
                return Response({'error': 'Formato de fecha inválido. Esperado: YYYY-MM-DDTHH:MM:SSZ.'}, status=status.HTTP_400_BAD_REQUEST)

        elif filter_data.get('endDate'):
            try:
                end_date = datetime.fromisoformat(filter_data['endDate'].replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=end_date)
            except ValueError:
                return Response({'error': 'Formato de fecha inválido. Esperado: YYYY-MM-DDTHH:MM:SSZ.'}, status=status.HTTP_400_BAD_REQUEST)

        order_by = filter_data.get('OrderBy', 'created_at')
        queryset = queryset.order_by(order_by)

        page = filter_data.get('pageNumber', 1)
        page_size = filter_data.get('pageSize', 5)

        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        serializer = GetIssueViewModelSerializer(page_obj, many=True)

        return Response({
            'results': serializer.data,
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'next': page_obj.has_next(),
            'previous': page_obj.has_previous(),
        })
    
    @action(detail=False, methods=['post'], url_path='GetFile')
    def GetFile(self, request, *args, **kwargs):
        filter_data = request.data
        queryset = Issue.objects.all()

        if filter_data.get('Title'):
            queryset = queryset.filter(title__icontains=filter_data['Title'])
        
        if filter_data.get('Status') is not None:
            queryset = queryset.filter(status=filter_data['Status'])

        if filter_data.get('Discarded') is not None:
            queryset = queryset.filter(discarded=filter_data['Discarded'])

        if filter_data.get('RepositoryId'):
            queryset = queryset.filter(repository_id__in=filter_data['RepositoryId'])

        if filter_data.get('Tags'):
            queryset = queryset.filter(tags__tagId__in=filter_data['Tags']).distinct()

        if filter_data.get('startDate') and filter_data.get('endDate'):
            try:
                start_date = datetime.fromisoformat(filter_data['startDate'].replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(filter_data['endDate'].replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__range=[start_date, end_date])
            except ValueError:
                return Response({'error': 'Formato de fecha inválido. Esperado: YYYY-MM-DDTHH:MM:SSZ.'}, status=status.HTTP_400_BAD_REQUEST)

        elif filter_data.get('startDate'):
            try:
                start_date = datetime.fromisoformat(filter_data['startDate'].replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=start_date)
            except ValueError:
                return Response({'error': 'Formato de fecha inválido. Esperado: YYYY-MM-DDTHH:MM:SSZ.'}, status=status.HTTP_400_BAD_REQUEST)

        elif filter_data.get('endDate'):
            try:
                end_date = datetime.fromisoformat(filter_data['endDate'].replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=end_date)
            except ValueError:
                return Response({'error': 'Formato de fecha inválido. Esperado: YYYY-MM-DDTHH:MM:SSZ.'}, status=status.HTTP_400_BAD_REQUEST)

        order_by = filter_data.get('OrderBy', 'created_at')
        queryset = queryset.order_by(order_by)

        serializer = GetIssueViewModelSerializer(queryset, many=True)
        data = serializer.data
        
        wb = openpyxl.Workbook()
        ws = wb.active
        date= datetime.now().strftime("%d/%m/%Y_%H:%M")
        filename = f'issues_{date}'
        ws.title = filename

        if data:
            headers = list(data[0].keys())
            ws.append(headers)

            for item in data:
                row = [str(item[h]) if isinstance(item[h], (dict, list)) else item[h] for h in headers]
                ws.append(row)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename={filename}.xlsx'
        wb.save(response)
        return response
    
    @action(detail=False, methods=['put'], url_path='Update/(?P<id>\d+)')
    def Update(self, request, id=None):
        try:
            issue = get_object_or_404(Issue, pk=id)
            serializer = IssueSerializer(issue, data=request.data, partial=True)

            if serializer.is_valid():
                updated_issue = serializer.save()

                tags_id = request.data.get('tagsId')
                if tags_id is not None:
                    issue_tags = []
                    for tag_id in tags_id:
                        try:
                            tag = get_object_or_404(Tag, tagId=tag_id)
                            issue_tags.append(tag)
                        except Tag.DoesNotExist:
                            return Response({'error': f'El tag {tag_id} no existe.'}, status=status.HTTP_400_BAD_REQUEST)

                    updated_issue.tags.set(issue_tags)
                    updated_issue.save()

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
        tags = self.queryset.all().order_by('name')
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put'], url_path='Update/(?P<id>\d+)')
    def Update(self, request, id=None):
        try:
            tag = get_object_or_404(Tag, pk=id)
            serializer = TagSerializer(tag, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as ex:
            return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
        
    @action(detail=False, methods=['post'], url_path='Create')
    def Create(self, request):
        try:
            serializer = TagSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as ex:
            return Response({'error': str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=False, methods=['post'], url_path='AddTagToIssue')
    def AddTagToIssue(self, request):
        tags_id = request.data.get('tagsId')
        issue_id = request.data.get('issueId')

        if not issue_id:
            return Response({'error': 'issueId es requerido'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(tags_id, list):
            return Response({'error': 'tagsId debe ser una lista'}, status=status.HTTP_400_BAD_REQUEST)

        issue = get_object_or_404(Issue, issue_id=issue_id)

        if tags_id == []:
            issue.tags.clear()
            issue.save()
            return Response({'status': 'Todos los tags han sido eliminados del Issue.'}, status=status.HTTP_200_OK)

        if tags_id:
            tags = []
            for tag_id in tags_id:
                try:
                    tag = get_object_or_404(Tag, tagId=tag_id)
                    tags.append(tag)
                except Tag.DoesNotExist:
                    return Response({'error': f'El tag {tag_id} no existe.'}, status=status.HTTP_400_BAD_REQUEST)

            if set(tags) != set(issue.tags.all()):
                issue.tags.set(tags)
                issue.save()
                return Response({'status': 'Tags agregados al Issue correctamente.'}, status=status.HTTP_201_CREATED)
            else:
                return Response({'status': 'No se realizaron cambios en los tags.'}, status=status.HTTP_200_OK)

class IssueTagViewSet(viewsets.ModelViewSet):
    queryset = IssueTag.objects.all()
    serializer_class = IssueTagSerializer

class GitViewSet(viewsets.ViewSet):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.git_service = GitService()

    @action(detail=False, methods=['post'], url_path='UpdateRepository/(?P<repository_id>[^/.]+)')
    def update_repository(self, request, repository_id):
        try:
            issues = self.git_service.update_repository(repository_id)
            if not issues['is_success']:
                return Response({"error": issues['message']}, status=issues['response_code'])
            return Response(issues, status=status.HTTP_200_OK)
        except Exception as ex:
            return Response({"error": f"Internal Server Error: {str(ex)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def home(request):
    return HttpResponse("Bienvenido a la API de UxDebt. Usa /api/ para acceder a los endpoints.")

class CustomPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'pageSize'
    page_query_param = 'page'
    max_page_size = 100 

    def get_page_size(self, request):
        return int(request.GET.get('pageSize', self.page_size))
    
class GitConfigViewSet(viewsets.ModelViewSet):
    queryset = GitHubToken.objects.all()
    serializer_class = GitConfigSerializer

    @action(detail=False, methods=['post'], url_path='saveToken')
    def save_token(self, request):
        token = request.data.get('token')

        if not token:
            return Response({'error': 'Token no proporcionado'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            git_config, created = GitHubToken.objects.get_or_create(id=1)
            git_config.token = token
            git_config.save()

            return Response({'message': 'Token guardado con éxito'}, status=status.HTTP_201_CREATED)

        except Exception as ex:
            return Response({'error': f'Error al guardar el token: {str(ex)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='getToken')
    def get_token(self, request):
        try:
            git_config = GitHubToken.objects.first()

            if not git_config:
                return Response({'error': 'No se encontró un token guardado'}, status=status.HTTP_404_NOT_FOUND)

            return Response({'token': git_config.token}, status=status.HTTP_200_OK)

        except Exception as ex:
            return Response({'error': f'Error al obtener el token: {str(ex)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)