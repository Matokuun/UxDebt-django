from rest_framework import serializers
from .models import Repository, Issue, Tag, IssueTag, GitHubToken

class RepositoryCreateSerializer(serializers.ModelSerializer):
    owner = serializers.CharField()
    name = serializers.CharField()
    gitId = serializers.IntegerField(source='git_id')
    htmlUrl = serializers.URLField(source='html_url')
    description = serializers.CharField(allow_null=True)

    class Meta:
        model = Repository
        fields = ['owner', 'name', 'gitId', 'htmlUrl', 'description']

class RepositoryGetAllSerializer(serializers.ModelSerializer):
    owner = serializers.CharField()
    name = serializers.CharField()
    gitId = serializers.IntegerField(source='git_id')
    htmlUrl = serializers.URLField(source='html_url')
    description = serializers.CharField(allow_null=True)
    repositoryId = serializers.IntegerField(source='repository_id')

    class Meta:
        model = Repository
        fields = ['owner', 'name', 'gitId', 'htmlUrl', 'description', 'repositoryId']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = '__all__'


class IssueSerializer(serializers.ModelSerializer):
    issueId = serializers.IntegerField(source='issue_id')
    Title = serializers.CharField(source='title')
    observation = serializers.CharField(allow_blank=True, required=False)
    Status = serializers.CharField(source='status')
    Discarded = serializers.BooleanField(source='discarded')
    CreatedAt = serializers.DateTimeField(source='created_at')
    RepositoryId = serializers.IntegerField(source='repository_id')
    tags = TagSerializer(many=True, read_only=True) 
    htmlUrl = serializers.CharField(source='html_url')
    body = serializers.CharField()

    class Meta:
        model = Issue
        fields = [
            'issueId', 'Title', 'observation', 'Status', 'Discarded', 
            'CreatedAt', 'RepositoryId', 'tags', 'htmlUrl', 'body'
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
    repoName = serializers.CharField(source='repository.name')
    createdAt = serializers.DateTimeField(source='created_at')
    closedAt = serializers.DateTimeField(source='closed_at', allow_null=True)
    labels = serializers.JSONField()
    repositoryId = serializers.IntegerField(source='repository_id') 
    tags = TagSerializer(many=True, read_only=True) 
    htmlUrl = serializers.CharField(source='html_url')
    body = serializers.CharField()


    class Meta:
        model = Issue
        fields = ['issueId', 'title', 'status', 'discarded', 'observation', 'repoName', 'createdAt', 'closedAt', 'labels', 'repositoryId', 'tags', 'htmlUrl', 'body']

class GitConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitHubToken
        fields = ['token']