from django.db import models

class Repository(models.Model):
    repository_id = models.AutoField(primary_key=True)
    owner = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    git_id = models.IntegerField(unique=True)
    html_url = models.URLField()
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'repository'

    def __str__(self):
        return f"{self.owner}/{self.name}"
    
class Tag(models.Model):
    tagId = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    code = models.CharField(max_length=50)

    class Meta:
        db_table = 'tag'

    def __str__(self):
        return self.name
    
class Issue(models.Model):
    issue_id = models.AutoField(primary_key=True)
    git_id = models.BigIntegerField(unique=True)
    html_url = models.URLField()
    status = models.BooleanField(default=True)
    title = models.CharField(max_length=255)
    discarded = models.BooleanField(default=False)
    labels = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    body = models.TextField(null=True, blank=True)

    repository = models.ForeignKey('Repository', on_delete=models.CASCADE, related_name='issues')
    tags = models.ManyToManyField(Tag, through='IssueTag')

    class Meta:
        db_table = 'issue'

    def __str__(self):
        return self.title

class IssueTag(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='issue_tags')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='issue_tags')

    class Meta:
        db_table = 'issue_tag'
        unique_together = (('issue', 'tag'),)

    def __str__(self):
        return f"{self.issue.title} - {self.tag.name}"
    
class GitHubToken(models.Model):
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'github_token'