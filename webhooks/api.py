from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
import requests
import hmac
import hashlib
import jwt
import time
from api.predictor import predict_tag, predict_ux_smell

DEFAULT_LABELS = [
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
        "name": "UX SMELL",
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
    },
    {
        "name": "CLIPPED/OVERLAPPING UI",
        "color": "fbca04",
        "description": "UI elements overlap or are visually clipped"
    },
    {
        "name": "INCONSISTENT FEEDBACK",
        "color": "fbca04",
        "description": "System feedback is inconsistent or unclear"
    },
    {
        "name": "POOR ACCESSIBILITY",
        "color": "fbca04",
        "description": "Contrast/color visibility problems or use of a screen reader that reduces accessibility."
    },
    {
        "name": "POOR DISCOVERABILITY",
        "color": "fbca04",
        "description": "Features or actions are difficult to find"
    },
    {
        "name": "UI INCONSISTENCY",
        "color": "fbca04",
        "description": "Inconsistent UI patterns or design elements"
    },
    {
        "name": "UNDESCRIPTIVE ELEMENT",
        "color": "fbca04",
        "description": "UI elements lack clear labeling or meaning"
    },
    {
        "name": "WRONG DEFAULT VALUE",
        "color": "fbca04",
        "description": "Incorrect or misleading default values"
    },

]

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

def ensure_default_labels(repo_full_name, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo_full_name}/labels"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("Error obteniendo labels existentes")
        return False

    existing_labels = {label["name"] for label in response.json()}

    for label in DEFAULT_LABELS:
        if label["name"] not in existing_labels:
            create_response = requests.post(
                url,
                headers=headers,
                json=label
            )

            if create_response.status_code not in [200, 201]:
                print(f"Error creando label {label['name']}")
            else:
                print(f"Label {label['name']} creado")

    return True
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
        if action in ["opened", "edited"]:

            issue_title = payload["issue"]["title"]
            issue_user = payload["issue"]["user"]["login"]
            issue_number = payload["issue"]["number"]
            repo_full_name = payload["repository"]["full_name"]
            issue_body= payload["issue"]["body"]

            print(f"Nuevo issue detectado Titulo: {issue_title} por {issue_user}")
        
            installation_id = payload["installation"]["id"]
            token = get_installation_token(installation_id)
            preds = predict_tag(f"{issue_title}. {issue_body or ''}")
            if preds: 
                predicted_label = preds["primary_label"]
                if (predicted_label == "UX ISSUE"):
                    predicted_label = "UX SMELL"
                ensure_default_labels(repo_full_name, token)
                code = add_label_to_issue(repo_full_name, issue_number, token, predicted_label)
                if code in [200, 201]:
                    print(f"Label '{predicted_label}' añadido con éxito al issue #{issue_number}")
                else:
                    print(f"Error al añadir label: {code}")
                if predicted_label == "UX SMELL":
                    preds_ux_smell= predict_ux_smell(f"{issue_title}. {issue_body or ''}")
                    secondary_label = preds_ux_smell["label"]
                    code_secondary= add_label_to_issue(repo_full_name, issue_number, token, secondary_label)
                    if code_secondary in [200, 201]:
                        print(f"Label '{secondary_label}' añadido con éxito al issue #{issue_number}")
                    else:
                        print(f"Error al añadir label: {code_secondary}")


        return Response({'status': 'received'}, status=status.HTTP_200_OK)