import requests
from .models import Repository, Issue, GitHubToken

class GitService:
    BASE_URL = 'https://api.github.com'

    def _get_github_token(self):
        try:
            token_obj = GitHubToken.objects.latest('created_at')
            return token_obj.token
        except GitHubToken.DoesNotExist:
            raise ValueError("No GitHub token found in the database.")

    def _fetch_all_issues(self, owner, repository):
        issues_data = []
        page = 1
        per_page = 30

        token = self._get_github_token()
        headers = {'Authorization': f'token {token}'}

        while True:
            issues_url = f'{self.BASE_URL}/repos/{owner}/{repository}/issues?page={page}&per_page={per_page}'
            issues_response = requests.get(issues_url, headers=headers)

            if issues_response.status_code != 200:
                return {
                    "is_success": False,
                    "response_code": issues_response.status_code,
                    "message": "Error al obtener los issues",
                    "data": None
                }

            page_issues_data = issues_response.json()
            if not page_issues_data:
                break

            issues_data.extend(page_issues_data)
            page += 1

        return {
            "is_success": True,
            "data": issues_data
        }

    def download_new_repository(self, owner, repository):
        repo_url = f'{self.BASE_URL}/repos/{owner}/{repository}'

        token = self._get_github_token()
        repo_response = requests.get(repo_url, headers={'Authorization': f'token {token}'})

        if repo_response.status_code != 200:
            return {
                "is_success": False,
                "response_code": repo_response.status_code,
                "message": "No se encontró el repositorio ingresado",
                "data": None
            }

        repo_data = repo_response.json()

        existing_repo = Repository.objects.filter(owner=owner, name=repository).first()

        if existing_repo:
            existing_repo.git_id = repo_data['id']
            existing_repo.html_url = repo_data['html_url']
            existing_repo.description = repo_data.get('description', '')
            existing_repo.save()
            new_repo = existing_repo
        else:
            new_repo = Repository(
                owner=owner,
                name=repository,
                git_id=repo_data['id'],
                html_url=repo_data['html_url'],
                description=repo_data.get('description', '')
            )
            new_repo.save()

        issues_result = self._fetch_all_issues(owner, repository)
        if not issues_result['is_success']:
            return issues_result

        for issue_data in issues_result['data']:
            existing_issue = Issue.objects.filter(git_id=issue_data['id']).first()
            status = issue_data['state'] == 'open'

            if existing_issue:
                existing_issue.title = issue_data['title']
                existing_issue.html_url = issue_data['html_url']
                existing_issue.status = status
                existing_issue.labels = ', '.join([label['name'] for label in issue_data.get('labels', [])])
                existing_issue.closed_at = issue_data.get('closed_at')
                existing_issue.save()
            else:
                new_issue = Issue(
                    git_id=issue_data['id'],
                    html_url=issue_data['html_url'],
                    title=issue_data['title'],
                    status=status,
                    labels=', '.join([label['name'] for label in issue_data.get('labels', [])]),
                    repository=new_repo
                )
                new_issue.save()

        return {
            "is_success": True,
            "response_code": 200,
            "message": "Repository and issues downloaded successfully",
            "data": issues_result['data']
        }

    def update_repository(self, repository_id):
        try:
            repo = Repository.objects.get(repository_id=repository_id)

            issues_result = self._fetch_all_issues(repo.owner, repo.name)
            if not issues_result['is_success']:
                return issues_result

            for issue_data in issues_result['data']:
                existing_issue = Issue.objects.filter(git_id=issue_data['id']).first()
                status = issue_data['state'] == 'open'

                if existing_issue:
                    existing_issue.title = issue_data['title']
                    existing_issue.html_url = issue_data['html_url']
                    existing_issue.status = status
                    existing_issue.labels = ', '.join([label['name'] for label in issue_data.get('labels', [])])
                    existing_issue.closed_at = issue_data.get('closed_at')
                    existing_issue.save()
                else:
                    new_issue = Issue(
                        git_id=issue_data['id'],
                        html_url=issue_data['html_url'],
                        title=issue_data['title'],
                        status=status,
                        labels=', '.join([label['name'] for label in issue_data.get('labels', [])]),
                        repository=repo
                    )
                    new_issue.save()

            return {
                "is_success": True,
                "response_code": 200,
                "message": "Repository and issues updated successfully",
                "data": issues_result['data']
            }

        except Repository.DoesNotExist:
            return {
                "is_success": False,
                "response_code": 404,
                "message": "Repository not found",
                "data": None
            }
