
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

class GithubWebookAPI(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        event_type = request.headers.get('X-GitHub-Event')
        payload = request.data

        action = payload.get("action")
        print("action:", action)
        if action == "opened":
            issue_title = payload["issue"]["title"]
            issue_user = payload["issue"]["user"]["login"]
            print(f"Nuevo issue detectado Título: {issue_title} por {issue_user}")

        return Response({'status': 'received'}, status=status.HTTP_200_OK)