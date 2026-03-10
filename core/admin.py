from django.contrib import admin

from .models import Course, Profile, Task, TaskNote


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'created_at')
    search_fields = ('user__username', 'display_name')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'semester', 'user')
    search_fields = ('code', 'title', 'user__username')
    list_filter = ('semester',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'user', 'priority', 'status', 'due_date')
    search_fields = ('title', 'description', 'course__title', 'course__code', 'user__username')
    list_filter = ('priority', 'status', 'due_date')


@admin.register(TaskNote)
class TaskNoteAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'created_at')
    search_fields = ('task__title', 'content', 'user__username')
