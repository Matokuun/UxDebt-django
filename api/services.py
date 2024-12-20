import requests
from django.conf import settings
from .models import Repository, Issue, IssueTag

class GitService:
    BASE_URL = 'https://api.github.com'

    def add_tag_to_issue(self, tag, issue):
        """Agrega una etiqueta a un issue."""
        try:
            issue_tag, created = IssueTag.objects.get_or_create(issue=issue, tag=tag)
            if created:
                return {"is_success": True, "message": "Tag added to Issue successfully."}
            else:
                return {"is_success": False, "message": "Tag already exists for this Issue."}
        except Exception as e:
            return {"is_success": False, "message": str(e)}

    def download_new_repository(self, owner, repository):
        """Descargar un nuevo repositorio y obtener los issues asociados."""
        try:
            # Llamada a la API de GitHub para obtener el repositorio
            repo_url = f'{self.BASE_URL}/repos/{owner}/{repository}'
            repo_response = requests.get(repo_url)

            if repo_response.status_code != 200:
                return {
                    "is_success": False,
                    "response_code": repo_response.status_code,
                    "message": "Error al descargar el repositorio",
                    "data": None
                }

            repo_data = repo_response.json()

            # Verificar si el repositorio ya existe en la base de datos
            existing_repo = Repository.objects.filter(owner=owner, name=repository).first()

            if existing_repo:
                # Actualizar el repositorio existente
                existing_repo.git_id = repo_data['id']
                existing_repo.html_url = repo_data['html_url']
                existing_repo.description = repo_data.get('description', '')
                existing_repo.save()
            else:
                # Crear un nuevo repositorio
                new_repo = Repository(
                    owner=owner,
                    name=repository,
                    git_id=repo_data['id'],
                    html_url=repo_data['html_url'],
                    description=repo_data.get('description', '')
                )
                new_repo.save()

            # Obtener los issues asociados al repositorio
            issues_url = f'{self.BASE_URL}/repos/{owner}/{repository}/issues'
            issues_response = requests.get(issues_url)

            if issues_response.status_code != 200:
                return {
                    "is_success": False,
                    "response_code": issues_response.status_code,
                    "message": "Error al obtener los issues",
                    "data": None
                }

            issues_data = issues_response.json()

            # Guardar los issues en la base de datos
            for issue_data in issues_data:
                existing_issue = Issue.objects.filter(git_id=issue_data['id']).first()

                if existing_issue:
                    # Actualizar el issue existente
                    existing_issue.title = issue_data['title']
                    existing_issue.html_url = issue_data['html_url']
                    existing_issue.status = issue_data['state']
                    existing_issue.labels = ', '.join([label['name'] for label in issue_data.get('labels', [])])
                    existing_issue.closed_at = issue_data.get('closed_at')
                    existing_issue.save()
                else:
                    # Crear un nuevo issue
                    new_issue = Issue(
                        git_id=issue_data['id'],
                        html_url=issue_data['html_url'],
                        title=issue_data['title'],
                        status=issue_data['state'],
                        labels=', '.join([label['name'] for label in issue_data.get('labels', [])]),
                        repository=new_repo  # Relacionar el issue con el nuevo repositorio
                    )
                    new_issue.save()

            return {
                "is_success": True,
                "response_code": 200,
                "message": "Repository and issues downloaded successfully",
                "data": issues_data
            }

        except requests.exceptions.RequestException as e:
            return {
                "is_success": False,
                "response_code": 500,
                "message": f"Error de conexión: {str(e)}",
                "data": None
            }
        except Exception as e:
            return {
                "is_success": False,
                "response_code": 500,
                "message": f"Internal server error: {str(e)}",
                "data": None
            }

    def update_repository(self, repository_id):
        """Actualizar un repositorio y obtener los nuevos problemas (issues)."""
        try:
            # Obtener el repositorio existente
            repo = Repository.objects.get(repository_id=repository_id)

            # Obtener los issues asociados al repositorio
            issues_url = f'{self.BASE_URL}/repos/{repo.owner}/{repo.name}/issues'
            issues_response = requests.get(issues_url)

            if issues_response.status_code != 200:
                return {
                    "is_success": False,
                    "response_code": issues_response.status_code,
                    "message": "Error al obtener los issues",
                    "data": None
                }

            issues_data = issues_response.json()

            # Actualizar o crear issues en la base de datos
            for issue_data in issues_data:
                existing_issue = Issue.objects.filter(git_id=issue_data['id']).first()

                if existing_issue:
                    # Actualizar el issue existente
                    existing_issue.title = issue_data['title']
                    existing_issue.html_url = issue_data['html_url']
                    existing_issue.status = issue_data['state']
                    existing_issue.labels = ', '.join([label['name'] for label in issue_data.get('labels', [])])
                    existing_issue.closed_at = issue_data.get('closed_at')
                    existing_issue.save()
                else:
                    # Crear un nuevo issue
                    new_issue = Issue(
                        git_id=issue_data['id'],
                        html_url=issue_data['html_url'],
                        title=issue_data['title'],
                        status=issue_data['state'],
                        labels=', '.join([label['name'] for label in issue_data.get('labels', [])]),
                        repository=repo  # Relacionar el issue con el repositorio existente
                    )
                    new_issue.save()

            return {
                "is_success": True,
                "response_code": 200,
                "message": "Repository and issues updated successfully",
                "data": issues_data
            }

        except Repository.DoesNotExist:
            return {
                "is_success": False,
                "response_code": 404,
                "message": "Repository not found",
                "data": None
            }
        except Exception as e:
            return {
                "is_success": False,
                "response_code": 500,
                "message": f"Internal server error: {str(e)}",
                "data": None
            }

    def get_repository(self, owner, name):
        """Obtener los detalles de un repositorio específico."""
        api_url = f'{self.BASE_URL}/repos/{owner}/{name}'
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json()
        return None

    def get_all_issues(self, owner, name):
        """Obtener todos los issues de un repositorio específico."""
        issues_url = f'{self.BASE_URL}/repos/{owner}/{name}/issues'
        response = requests.get(issues_url)
        if response.status_code == 200:
            return response.json()
        return []
