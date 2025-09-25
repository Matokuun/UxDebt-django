import io
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
import csv
from io import StringIO

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
        labels = request.data.get("labels", None)
        print("Labels recibidos:", labels)

        if labels is None:
            labels = []
        elif isinstance(labels, list):
            normalized = []
            for item in labels:
                if isinstance(item, str):
                    # Divido por coma y limpio espacios
                    parts = [p.strip() for p in item.split(",") if p.strip()]
                    normalized.extend(parts)
            labels = normalized
        else:
            labels = []

        if not owner or not name:
            return Response({'error': 'Propietario y Repositorio son campos requeridos.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if Repository.objects.filter(name=name, owner=owner).exists(): #ver despues el caso en el que se edita el label
            return Response(
                {'error': 'El repositorio ingresado ya existe'},
                status=status.HTTP_400_BAD_REQUEST
            )

        git_service = GitService()

        try:
            issues = git_service.download_new_repository(owner, name, labels)

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
    
    @action(detail=False, methods=['post'], url_path='AddLabel')
    def add_label_in_repo(self, request, *args, **kwargs):
        id_repo = request.data.get('id')
        label = request.data.get("newLabel")
        print("Label recibido:", label, ", id del repo:", id_repo)

        git_service = GitService()

        try:
            issues = git_service.update_repository(id_repo, label)

            if not issues['is_success']:
                return Response(
                    {"error": issues['message']},
                    status=issues['response_code']
                )
            #agregar label aqui, en la lista de labels de la bd
            return Response(issues, status=status.HTTP_200_OK)
        
        except Exception as ex:
            return Response({"error": str(ex)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            repo.labels = []
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
        
        csv_buffer = StringIO(newline='')
        writer = csv.writer(csv_buffer, quoting=csv.QUOTE_MINIMAL)

        headers = list(data[0].keys())
        writer.writerow(headers)

        for item in data:
            row = []
            for h in headers:
                val = item.get(h)

                # Si es una lista de dicts con 'name'
                if isinstance(val, list) and all(isinstance(d, dict) and "name" in d for d in val):
                    cell = ", ".join(d["name"] for d in val)

                # Si es un dict con 'name'
                elif isinstance(val, dict) and "name" in val:
                    cell = val["name"]

                # Si es un dict o lista (sin estructura clara)
                elif isinstance(val, (dict, list)):
                    cell = str(val)

                # Si es un string (posiblemente el campo body)
                elif isinstance(val, str):
                    cell = val.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').replace(';',',').strip()

                # Otros valores simples
                else:
                    cell = val

                row.append(cell)
            writer.writerow(row)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename=issues_filtrados.csv'
        response.write(csv_buffer.getvalue())
        return response
    
    @action(detail=False, methods=['post'], url_path='newIssue')
    def createIssue(self, request, *args, **kwargs):
        try:
            title = request.data.get('title')
            body = request.data.get('body', None)
            tag_name = request.data.get('tag', None)

            if not title:
                return Response({'error': 'El campo title es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if body and title:
                issue, created = Issue.objects.get_or_create(
                    title=title,
                    body=body,
                    defaults={
                        'html_url': None,
                        'repository': None,
                        'git_id': None
                    }
                )
            else:
                issue = Issue.objects.create(
                    title=title,
                    body=body,
                    html_url=None,
                    repository=None,
                    git_id=None
                )

            # Asocio el tag si viene
            if tag_name:
                tag, _ = Tag.objects.get_or_create(name=tag_name)
                IssueTag.objects.get_or_create(issue=issue, tag=tag)

            serializer = IssueSerializer(issue)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='ImportIssues')
    def ImportIssue(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        print(f"Archivo recibido: {file.name}")
        errores= 0
        if not file:
            return Response({"error": "No file uploaded."}, status=400)

        try:
            # Leemos el contenido del archivo CSV
            file_data = file.read().decode('utf-8')  # Decodificamos a texto, VER SI ME SIRVE ESTA DECODIFICACION (hay caracteres especiales)
            csv_reader = csv.reader(io.StringIO(file_data))
            for idx, row in enumerate(csv_reader):
                try:
                    if (row[1]) == "title":
                        continue
                    title= row[1]
                    htmlUrl= row[11]
                    issue = Issue.objects.filter(html_url=htmlUrl).first()
                    if issue: #actualizar datos del issue que ya existe
                        print(f"Issue {title} - existe")
                        issue.status = row[2] == 'True'
                        issue.discarded = row[3] == 'True'
                        issue.observation = row[4]
                        issue.labels = row[8]
                        issue.body = row[12]
                        issue.save()
                    else: 
                        #Mirar si existe el repo en la bd. Si existe entonces actualizo su repo. Si no existe entonces traerlo. En ambos casos luego actualizar el issue.
                        print(f"Issue {title} - NO existe")
                        owner_name= htmlUrl.split('/')[3]
                        repo_name= htmlUrl.split('/')[4]
                        repo = Repository.objects.filter(owner=owner_name, name= repo_name).first()
                        git_service = GitService()
                        if repo:
                            print(f"repositorio {repo_name} de {owner_name} existe: actualizo repositorio")
                            #actualizo repo (actualmente no se usa, pero puede servir en un futuro)
                            #git_service.update_repository(repo.repository_id)
                            #issue = Issue.objects.filter(html_url=htmlUrl).first()
                            #issue.discarded = row[3] == 'True'
                            #issue.observation = row[4]
                            #issue.save()
                            issue = Issue.objects.create(
                                title=title,
                                status=row[2] == 'True',
                                discarded=row[3] == 'True',
                                observation=row[4],
                                labels=row[8],
                                body=row[12],
                                html_url=htmlUrl,
                                repository= repo
                            )
                        else:
                            #analizo si es un issue manual o si tiene repo pero no esta en el sistema (entonces lo traigo)
                            if htmlUrl:
                                print(f"repositorio {repo_name} de {owner_name} no existe: agregando nuevo repositorio")
                                #traer el nuevo
                                git_service.register_new_repository(owner_name, repo_name)
                                repo = Repository.objects.filter(owner=owner_name, name= repo_name).first()
                                issue = Issue.objects.create(
                                    title=title,
                                    status=row[2] == 'True',
                                    discarded=row[3] == 'True',
                                    observation=row[4],
                                    labels=row[8],
                                    body=row[12],
                                    html_url=htmlUrl,
                                    repository=repo
                                )
                            else:
                                issue = Issue.objects.create(
                                    title=title,
                                    discarded=row[3] == 'True',
                                    observation=row[4],
                                    body=row[12]
                                )
                    #Analisis del tag del issue: Existe en la base de datos local, no existe (crearlo entonces)
                    tag = Tag.objects.filter(name__iexact=row[10]).first()
                    if not tag:
                        tag = Tag.objects.create(name=row[10])
                        print("TAG NUEVO")
                    else:
                        print("EXISTE EL TAG")
                    IssueTag.objects.get_or_create(issue=issue, tag=tag)

                except Exception as e:
                    print(f"Error en linea {idx}: {e}")
                    errores= errores + 1
                    continue

            if(errores == 0):
                return Response({"message": "Archivo recibido y leído correctamente."})
            else:
                return Response({"message": "Hubo errores durante la importación de issues"}, status=500)
        except Exception as e:
            return Response({"error": str(e)}, status=500)
    
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