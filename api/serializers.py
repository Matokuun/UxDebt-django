from rest_framework import serializers
from .models import IssueTagPredicted, Repository, Issue, Tag, IssueTag, GitHubToken, Project, ProjectIssue
from django.contrib.auth.models import User

class RepositoryCreateSerializer(serializers.ModelSerializer):
    owner = serializers.CharField()
    name = serializers.CharField()
    gitId = serializers.IntegerField(source='git_id')
    htmlUrl = serializers.URLField(source='html_url')
    description = serializers.CharField(allow_null=True)
    labels = serializers.ListField(
        child=serializers.CharField(), required=False
    )

    class Meta:
        model = Repository
        fields = ['owner', 'name', 'gitId', 'htmlUrl', 'description', 'labels']

class RepositoryGetAllSerializer(serializers.ModelSerializer):
    owner = serializers.CharField()
    name = serializers.CharField()
    gitId = serializers.IntegerField(source='git_id')
    htmlUrl = serializers.URLField(source='html_url')
    description = serializers.CharField(allow_null=True)
    repositoryId = serializers.IntegerField(source='repository_id')
    labels = serializers.ListField(
        child=serializers.CharField(), required=False
    )

    class Meta:
        model = Repository
        fields = ['owner', 'name', 'gitId', 'htmlUrl', 'description', 'repositoryId', 'labels']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'

class IssueTagPredictedSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)

    class Meta:
        model = IssueTagPredicted
        fields = ['tag', 'confidence', 'rank', 'created_at']
        
class IssueSerializer(serializers.ModelSerializer):
    issueId = serializers.IntegerField(source='issue_id')
    Title = serializers.CharField(source='title')
    observation = serializers.CharField(allow_blank=True, required=False)
    Status = serializers.CharField(source='status')
    Discarded = serializers.BooleanField(source='discarded')
    CreatedAt = serializers.DateTimeField(source='created_at')
    RepositoryId = serializers.IntegerField(source='repository_id')
    tags = TagSerializer(many=True, read_only=True)
    predicted_tags = IssueTagPredictedSerializer(many=True, read_only=True) 
    htmlUrl = serializers.CharField(source='html_url')
    body = serializers.CharField()

    class Meta:
        model = Issue
        fields = [
            'issueId', 'Title', 'observation', 'Status', 'Discarded', 
            'CreatedAt', 'RepositoryId', 'tags', 'predicted_tags', 'htmlUrl', 'body'
        ]

class IssueTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueTag
        fields = '__all__'

class GetIssueViewModelSerializer(serializers.ModelSerializer):
    issueId = serializers.IntegerField(source='issue_id')
    title = serializers.CharField()
    status = serializers.CharField()
    discarded = serializers.BooleanField()
    observation = serializers.CharField(allow_null=True)
    repoName = serializers.CharField(source='repository.name', default=None)
    createdAt = serializers.DateTimeField(source='created_at')
    closedAt = serializers.DateTimeField(source='closed_at', allow_null=True)
    labels = serializers.JSONField()
    repositoryId = serializers.IntegerField(source='repository_id') 
    tags = TagSerializer(many=True, read_only=True) 
    htmlUrl = serializers.CharField(source='html_url')
    body = serializers.CharField()
    predicted_tags = IssueTagPredictedSerializer(many=True,read_only=True)

    class Meta:
        model = Issue
        fields = ['issueId', 'title', 'status', 'discarded', 'observation', 'repoName', 'createdAt', 'closedAt', 'labels', 'repositoryId', 'tags', 'htmlUrl', 'body','predicted_tags']

class GitConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitHubToken
        fields = ['token']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email'),
            password=validated_data['password']
        )
        return user
    
class ProjectSerializer(serializers.ModelSerializer):
    projectId = serializers.IntegerField(source='project_id')

    class Meta:
        model = Project
        fields = [
            'projectId',
            'name',
            'description',
            'git_id',
            'html_url',
            'created_at',
        ]

class IssueProjectSerializer(serializers.ModelSerializer):
    projectId = serializers.IntegerField(source='project.project_id')
    projectName = serializers.CharField(source='project.name')

    class Meta:
        model = ProjectIssue
        fields = [
            'projectId',
            'projectName',
            'status',
        ]

class ProjectListSerializer(serializers.ModelSerializer):
    projectId = serializers.IntegerField(source='project_id')
    issuesCount = serializers.IntegerField(source='issues.count', read_only=True)

    class Meta:
        model = Project
        fields = [
            'projectId',
            'name',
            'description',
            'issuesCount',
            'created_at',
            'owner',
            'html_url',
            'git_id',
        ]

class IssueWithProjectsSerializer(IssueSerializer):
    projects = IssueProjectSerializer(
        source='projectissue_set',
        many=True,
        read_only=True
    )

    class Meta(IssueSerializer.Meta):
        fields = IssueSerializer.Meta.fields + ['projects']

class IssueWithProjectsViewSerializer(GetIssueViewModelSerializer):
    projects = IssueProjectSerializer(
        source='projectissue_set',
        many=True,
        read_only=True
    )

    class Meta(GetIssueViewModelSerializer.Meta):
        fields = GetIssueViewModelSerializer.Meta.fields + ['projects']