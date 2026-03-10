from django.urls import path
from django.views.generic import RedirectView

from .views import (
    BulkTaskActionView,
    CourseCreateView,
    CourseDeleteView,
    CourseListView,
    CourseUpdateView,
    DashboardView,
    OverviewView,
    ProfileUpdateView,
    ProfileView,
    RegisterView,
    TaskCreateView,
    TaskDeleteView,
    TaskDetailView,
    TaskListView,
    TaskNoteCreateView,
    TaskUpdateView,
    quick_status_update,
)

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False), name='home'),
    path('register/', RegisterView.as_view(), name='register'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('overview/', OverviewView.as_view(), name='overview'),
    path('tasks/', TaskListView.as_view(), name='task_list'),
    path('tasks/new/', TaskCreateView.as_view(), name='task_create'),
    path('tasks/bulk/', BulkTaskActionView.as_view(), name='task_bulk_action'),
    path('tasks/<int:pk>/', TaskDetailView.as_view(), name='task_detail'),
    path('tasks/<int:pk>/edit/', TaskUpdateView.as_view(), name='task_update'),
    path('tasks/<int:pk>/delete/', TaskDeleteView.as_view(), name='task_delete'),
    path('tasks/<int:pk>/notes/', TaskNoteCreateView.as_view(), name='task_note_create'),
    path('tasks/<int:pk>/quick-status/', quick_status_update, name='quick_status_update'),
    path('courses/', CourseListView.as_view(), name='course_list'),
    path('courses/new/', CourseCreateView.as_view(), name='course_create'),
    path('courses/<int:pk>/edit/', CourseUpdateView.as_view(), name='course_update'),
    path('courses/<int:pk>/delete/', CourseDeleteView.as_view(), name='course_delete'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/edit/', ProfileUpdateView.as_view(), name='profile_edit'),
]
