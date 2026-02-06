import requests
from .models import Repository, Issue, GitHubToken, Tag, IssueTag, IssueTagPredicted
from .predictor import predict_tag
from urllib.parse import urlparse

class GitService:
    BASE_URL = 'https://api.github.com'

    def __init__(self, user):
        self.user = user

    def _get_github_token(self):
        try:
            return self.user.github_token.token
        except GitHubToken.DoesNotExist:
            raise ValueError("El usuario no tiene token de GitHub configurado.")

    def _create_github_label(self, owner, repo, name, color, description=""):
        token = self._get_github_token()

        url = f"{self.BASE_URL}/repos/{owner}/{repo}/labels"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        payload = {
            "name": name,
            "color": color,
            "description": description
        }

        response = requests.post(url, headers=headers, json=payload)

        return {
            "status_code": response.status_code,
            "response": response.json() if response.content else None
        }

    def _fetch_all_issues(self, owner, repository, labels=None):
        issues_data = []
        page = 1
        per_page = 30

        token = self._get_github_token()
        headers = {'Authorization': f'token {token}'}

        if not isinstance(labels, list):
            labels = []

        while True:
            issues_url = f'{self.BASE_URL}/repos/{owner}/{repository}/issues'
            params = {
                "state": "all",
                'page': page,
                'per_page': per_page
            }
            
            if labels:
                params['labels'] = ",".join(labels)
                print("Labels enviados a GitHub:", params['labels'])
            else:
                print("Labels enviados a GitHub: ninguno")

            issues_response = requests.get(issues_url, headers=headers, params=params)

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
    
    def _fetch_issues_for_label(self, owner, repository, label):
        issues_data = []
        page = 1
        per_page = 30

        token = self._get_github_token()
        headers = {'Authorization': f'token {token}'}

        while True:
            issues_url = f'{self.BASE_URL}/repos/{owner}/{repository}/issues'
            params = {
                'page': page,
                'per_page': per_page,
                'labels': label,
                "state": "all"
            }
            
            issues_response = requests.get(issues_url, headers=headers, params=params)

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
    
    def extract_repo_from_issue_url(self, issue_url):
        try:
            path = urlparse(issue_url).path.strip("/").split("/")
            # /owner/repo/issues/number
            if len(path) >= 4 and path[2] == "issues":
                return path[0], path[1]
        except Exception:
            pass

        return None, None

    def create_default_labels(self, owner, repo):
        labels = [
            {
                "name": "NEW/UPDATE FUNCTIONALITY",
                "color": "1f6feb",
                "description": "Fixes, updates or new functionality"
            },
            {
                "name": "UX BUG",
                "color": "d73a4a",
                "description": "User experience bug"
            },
            {
                "name": "UX ISSUE",
                "color": "fbca04",
                "description": "User experience smell or UX inconsistency"
            },
            {
                "name": "UX FEATURE REQUEST",
                "color": "0e8a16",
                "description": "New UX feature request"
            },
            {
                "name": "FEATURE REQUEST",
                "color": "5319e7",
                "description": "New feature request"
            }
        ]

        results = []
        for label in labels:
            result = self._create_github_label(
                owner=owner,
                repo=repo,
                name=label["name"],
                color=label["color"],
                description=label["description"]
            )
            results.append({
                "label": label["name"],
                "status_code": result["status_code"]
            })

        return results
    
    def ensure_repo_labels(self, owner, repo):
        return self.create_default_labels(owner, repo)
    
    def extract_issue_number(self, issue_url):
        try:
            return int(issue_url.rstrip("/").split("/")[-1])
        except Exception:
            return None

    def apply_label_to_issue(self, owner, repo, issue_number, label_name):
        token = self._get_github_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/labels"

        payload = {
            "labels": [label_name]
        }

        response = requests.post(url, json=payload, headers=headers)

        # 200 = ok, 201 = created
        if response.status_code not in (200, 201):
            print(
                f"[GitHub] Error asignando label '{label_name}' "
                f"a {owner}/{repo}#{issue_number}: {response.text}"
            )

        return response.status_code in (200, 201)

    def download_new_repository(self, owner, repository, labels):
        repo_url = f'{self.BASE_URL}/repos/{owner}/{repository}?state=all' #por defecto, trae issues en estado open (en caso de querer cambiarlo, se debe modificar el request a github, con state=all)

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

        existing_repo = Repository.objects.filter(owner=owner, name=repository, user=self.user).first()

        if existing_repo:
            existing_repo.git_id = repo_data['id']
            existing_repo.html_url = repo_data['html_url']
            existing_repo.description = repo_data.get('description', '')
            existing_repo.labels = labels or []
            existing_repo.save()
            new_repo = existing_repo
        else:
            new_repo = Repository(
                owner=owner,
                name=repository,
                git_id=repo_data['id'],
                html_url=repo_data['html_url'],
                description=repo_data.get('description', ''),
                labels=labels or [],
                user=self.user
            )
            new_repo.save()

        issues_result = self._fetch_all_issues(owner, repository, labels)
        if not issues_result['is_success']:
            return issues_result
        
        new_issues_count = 0
        for issue_data in issues_result['data']:
            existing_issue = Issue.objects.filter(git_id=issue_data['id']).first()
            status = issue_data['state'] == 'open'

            if existing_issue:
                existing_issue.title = issue_data['title']
                existing_issue.html_url = issue_data['html_url']
                existing_issue.body= issue_data['body']
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
                    repository=new_repo,
                    body=issue_data['body']
                )
                new_issue.save()
                new_issues_count += 1
            #predicción de tags
            preds = predict_tag(f"{issue_data['title']}. {issue_data['body'] or ''}")
            if preds:
                # Primera predicción
                tag1, _ = Tag.objects.get_or_create(name=preds["primary_label"])
                IssueTagPredicted.objects.update_or_create(
                    issue=existing_issue if existing_issue else new_issue,
                    tag=tag1,
                    defaults={
                        "confidence": preds["primary_score"],
                        "rank": 1
                    }
                )
                # Segunda predicción
                tag2, _ = Tag.objects.get_or_create(name=preds["secondary_label"])
                IssueTagPredicted.objects.update_or_create(
                    issue=existing_issue if existing_issue else new_issue,
                    tag=tag2,
                    defaults={
                        "confidence": preds["secondary_score"],
                        "rank": 2
                    }
                )
                IssueTag.objects.update_or_create(
                    issue= existing_issue if existing_issue else new_issue,
                    tag= tag1
                )
        return {
            "is_success": True,
            "response_code": 200,
            "message": "Repository and issues downloaded successfully",
            "data": issues_result['data'],
            "new_issues": new_issues_count
        }
    
    def register_new_repository(self, owner, repository):
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
        print('repositorio: ', repo_data['html_url'], repo_data['id'])
        print('repositorio: ', owner, repository)
        existing_repo = Repository.objects.filter(owner=owner, name=repository, user=self.user).first()

        if existing_repo:
            existing_repo.git_id = repo_data['id']
            existing_repo.html_url = repo_data['html_url']
            existing_repo.description = repo_data.get('description', ''),
            existing_repo.labels = []
            existing_repo.save()
        else:
            new_repo = Repository(
                owner=owner,
                name=repository,
                git_id=repo_data['id'],
                html_url=repo_data['html_url'],
                description=repo_data.get('description', ''),
                labels= [],
                user=self.user
            )
            new_repo.save()

        return {
            "is_success": True,
            "response_code": 200,
            "message": "Repository registered successfully",
            "data": repository
        }

    def update_repository(self, repository_id, label=None):
        try:
            repo = Repository.objects.get(repository_id=repository_id, user=self.user)
            if label is None:
                issues_result = self._fetch_all_issues(repo.owner, repo.name)
            else:
                issues_result = self._fetch_issues_for_label(repo.owner, repo.name, label)
                
            if not issues_result['is_success']:
                return issues_result

            new_issues_count = 0
            for issue_data in issues_result['data']:
                existing_issue = Issue.objects.filter(git_id=issue_data['id']).first()
                status = issue_data['state'] == 'open'

                if existing_issue:
                    existing_issue.title = issue_data['title']
                    existing_issue.html_url = issue_data['html_url']
                    existing_issue.status = status
                    existing_issue.body= issue_data['body']
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
                        repository=repo,
                        body=issue_data['body']
                    )
                    new_issue.save()
                    new_issues_count += 1
                #predicción de tags
                preds = predict_tag(f"{issue_data['title']}. {issue_data['body'] or ''}")
                if preds:
                    # Primera predicción
                    tag1, _ = Tag.objects.get_or_create(name=preds["primary_label"])
                    IssueTagPredicted.objects.update_or_create(
                        issue=existing_issue if existing_issue else new_issue,
                        tag=tag1,
                        defaults={
                            "confidence": preds["primary_score"],
                            "rank": 1
                        }
                    )
                    # Segunda predicción
                    tag2, _ = Tag.objects.get_or_create(name=preds["secondary_label"])
                    IssueTagPredicted.objects.update_or_create(
                        issue=existing_issue if existing_issue else new_issue,
                        tag=tag2,
                        defaults={
                            "confidence": preds["secondary_score"],
                            "rank": 2
                        }
                    )
                    IssueTag.objects.update_or_create(
                        issue= existing_issue if existing_issue else new_issue,
                        tag= tag1
                    )

            if label is not None:
                repo.labels.append(label)
                repo.save()
            else:
                # Si no se pasa label, limpio la lista de labels, porque significa que no hay filtro de labels
                repo.labels = []
                repo.save(update_fields=['labels'])

            return {
                "is_success": True,
                "response_code": 200,
                "message": "Repository and issues updated successfully",
                "data": issues_result['data'],
                "new_issues": new_issues_count
            }

        except Repository.DoesNotExist:
            return {
                "is_success": False,
                "response_code": 404,
                "message": "Repository not found",
                "data": None
            }
        
    def _run_graphql(self, query, variables):
        token = self._get_github_token()
        headers = {
            "Authorization": f"Bearer {token}"
        }

        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers
        )

        try:
            return response.json()
        except Exception:
            return {}
    
    def fetch_project_with_issues(self, owner, project_number):
        variables = {
            "login": owner,
            "projectNumber": project_number
        }
        PROJECT_QUERY = """
        query($login: String!, $projectNumber: Int!) {
        %s(login: $login) {
            projectV2(number: $projectNumber) {
            id
            title
            url
            items(first: 100) {
                nodes {
                content {
                    ... on Issue {
                    id
                    title
                    url
                    body
                    state
                    labels(first: 20) {
                        nodes {
                            name
                        }
                    }
                    }
                }
                fieldValues(first: 20) {
                    nodes {
                    ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field {
                        ... on ProjectV2SingleSelectField {
                            name
                        }
                        }
                    }
                    }
                }
                }
            }
            }
        }
        }
        """
        org_query = PROJECT_QUERY % "organization"
        org_payload = self._run_graphql(org_query, variables)

        print("ORG PAYLOAD:", org_payload)

        project = (
            org_payload
            .get("data", {})
            .get("organization")
        )

        if project and project.get("projectV2"):
            return {
                "is_success": True,
                "data": {
                    "data": {
                        "user": {
                            "projectV2": project["projectV2"]
                        }
                    }
                }
            }
        
        user_query = PROJECT_QUERY % "user"
        user_payload = self._run_graphql(user_query, variables)

        print("USER PAYLOAD:", user_payload)

        project = (
            user_payload
            .get("data", {})
            .get("user")
        )

        if project and project.get("projectV2"):
            return {
                "is_success": True,
                "data": {
                    "data": {
                        "user": {
                            "projectV2": project["projectV2"]
                        }
                    }
                }
            }
        return {
            "is_success": False,
            "error": "Proyecto no encontrado ni como usuario ni como organización",
            "debug": {
                "user": user_payload,
                "organization": org_payload
            }
        }