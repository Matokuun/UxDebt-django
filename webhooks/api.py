
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
import hmac
import hashlib

WEBHOOK_SECRET = b"your_webhook_secret_here"

class GithubWebhookAPI(APIView):
    permission_classes = [permissions.AllowAny]

    def verify_secret(self, payload_body, signature_header):
        """Verifica que el webhook realmente venga de GitHub."""
        if not signature_header:
            return False
    
        hash_object = hmac.new(WEBHOOK_SECRET, msg=payload_body, digestmod=hashlib.sha256)
        expected_signature = "sha256=" + hash_object.hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)

    def post(self, request, *args, **kwargs):
        event_type = request.headers.get('X-GitHub-Event')
    
        if not self.verify_secret(request.body, request.headers.get('X-Hub-Signature-256')):
            return Response({'detail': 'Invalid signature'}, status=status.HTTP_403_FORBIDDEN)
        
        payload = request.data
        action = payload.get("action")
        print("action:", action)
        if action == "opened":
            issue_title = payload["issue"]["title"]
            issue_user = payload["issue"]["user"]["login"]
            print(f"Nuevo issue detectado Título: {issue_title} por {issue_user}")

        return Response({'status': 'received'}, status=status.HTTP_200_OK)