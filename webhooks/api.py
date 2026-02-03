
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
import requests
import hmac
import hashlib
import jwt
import time


def get_installation_token(installation_id):
    try:
        with open(settings.GITHUB_PRIVATE_KEY_PATH, 'r') as f:
            private_key = f.read()
    except FileNotFoundError:
        print(f"Private key not found in {settings.GITHUB_PRIVATE_KEY_PATH}")
        return None

    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": settings.GITHUB_APP_ID,
    }
    encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
    
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {"Authorization": f"Bearer {encoded_jwt}", "Accept": "application/vnd.github+json"}
    
    response = requests.post(url, headers=headers)
    return response.json().get("token")

def add_label_to_issue(repo_full_name, issue_number, token, label):
    url = f"https://api.github.com/repos/{repo_full_name}/issues/{issue_number}/labels"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    data = {"labels": [label]}
    
    response = requests.post(url, headers=headers, json=data)
    return response.status_code

class GithubWebhookAPI(APIView):
    permission_classes = [permissions.AllowAny]

    def verify_secret(self, payload_body, signature_header):
        """Verifica que el webhook realmente venga de GitHub."""
        if not signature_header:
            return False
    
        hash_object = hmac.new(settings.GITHUB_WEBHOOK_SECRET, msg=payload_body, digestmod=hashlib.sha256)
        expected_signature = "sha256=" + hash_object.hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)

    def post(self, request, *args, **kwargs):
        event_type = request.headers.get('X-GitHub-Event')
    
        if not self.verify_secret(request.body, request.headers.get('X-Hub-Signature-256')):
            return Response({'detail': 'Invalid signature'}, status=status.HTTP_403_FORBIDDEN)
        
        payload = request.data
        action = payload.get("action")
        if action == "opened":
            issue_title = payload["issue"]["title"]
            issue_user = payload["issue"]["user"]["login"]
            issue_number = payload["issue"]["number"]
            repo_full_name = payload["repository"]["full_name"]
            print(f"Nuevo issue detectado Titulo: {issue_title} por {issue_user}")
            
            installation_id = payload["installation"]["id"]
            token = get_installation_token(installation_id)

            code = add_label_to_issue(repo_full_name, issue_number, token, "needs-triage")
        
            if code == 200:
                print(f"Label 'needs-triage' añadido con éxito al issue #{issue_number}")
            else:
                print(f"Error al añadir label: {code}")


        return Response({'status': 'received'}, status=status.HTTP_200_OK)