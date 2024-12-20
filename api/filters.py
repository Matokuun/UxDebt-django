from django.db.models import Q
from django_filters import rest_framework as filters
from .models import Issue

class IssueFilter(filters.FilterSet):
    title = filters.CharFilter(field_name="title", lookup_expr="icontains")
    discarded = filters.BooleanFilter()
    status = filters.CharFilter()
    repository_id = filters.NumberFilter()
    created_at = filters.DateFilter()

    class Meta:
        model = Issue
        fields = ['title', 'discarded', 'status', 'repository_id', 'created_at']
