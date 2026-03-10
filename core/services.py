from __future__ import annotations

from datetime import timedelta
from collections import OrderedDict

from django.db.models import Case, Count, IntegerField, Min, Q, When
from django.utils import timezone

from .models import Course, Task


PRIORITY_ORDER = Case(
    When(priority=Task.Priority.HIGH, then=0),
    When(priority=Task.Priority.MEDIUM, then=1),
    When(priority=Task.Priority.LOW, then=2),
    default=3,
    output_field=IntegerField(),
)


STATUS_COLUMNS = [
    (Task.Status.TODO, 'To-do'),
    (Task.Status.DOING, 'Doing'),
    (Task.Status.DONE, 'Done'),
]


def base_task_queryset(user):
    return Task.objects.filter(user=user).select_related('course')


def apply_task_filters(queryset, params):
    search_term = params.get('q', '').strip()
    course_id = params.get('course', '').strip()
    status = params.get('status', '').strip()
    priority = params.get('priority', '').strip()
    deadline = params.get('deadline', '').strip()
    sort = params.get('sort', 'smart').strip() or 'smart'
    today = timezone.localdate()

    if search_term:
        queryset = queryset.filter(
            Q(title__icontains=search_term)
            | Q(description__icontains=search_term)
            | Q(course__title__icontains=search_term)
            | Q(course__code__icontains=search_term)
        )
    if course_id:
        queryset = queryset.filter(course_id=course_id)
    if status:
        queryset = queryset.filter(status=status)
    if priority:
        queryset = queryset.filter(priority=priority)
    if deadline == 'due_soon':
        queryset = queryset.filter(
            status__in=[Task.Status.TODO, Task.Status.DOING],
            due_date__gte=today,
            due_date__lte=today + timedelta(days=3),
        )
    elif deadline == 'overdue':
        queryset = queryset.filter(
            status__in=[Task.Status.TODO, Task.Status.DOING],
            due_date__lt=today,
        )

    if sort == 'due_desc':
        queryset = queryset.order_by('-due_date', '-updated_at')
    elif sort == 'priority':
        queryset = queryset.order_by(PRIORITY_ORDER, 'due_date', '-updated_at')
    elif sort == 'updated_desc':
        queryset = queryset.order_by('-updated_at')
    elif sort == 'course':
        queryset = queryset.order_by('course__code', 'due_date', PRIORITY_ORDER)
    else:
        queryset = queryset.annotate(
            urgency_bucket=Case(
                When(status__in=[Task.Status.TODO, Task.Status.DOING], due_date__lt=today, then=0),
                When(status__in=[Task.Status.TODO, Task.Status.DOING], due_date__lte=today + timedelta(days=3), then=1),
                When(status=Task.Status.DOING, then=2),
                When(status=Task.Status.TODO, then=3),
                When(status=Task.Status.DONE, then=4),
                default=5,
                output_field=IntegerField(),
            )
        ).order_by('urgency_bucket', PRIORITY_ORDER, 'due_date', '-updated_at')
    return queryset


def build_dashboard_summary(task_queryset):
    today = timezone.localdate()
    total_tasks = task_queryset.count()
    done_count = task_queryset.filter(status=Task.Status.DONE).count()
    active_count = task_queryset.exclude(status=Task.Status.DONE).count()
    due_soon_filter = Q(
        status__in=[Task.Status.TODO, Task.Status.DOING],
        due_date__gte=today,
        due_date__lte=today + timedelta(days=3),
    )
    overdue_filter = Q(status__in=[Task.Status.TODO, Task.Status.DOING], due_date__lt=today)
    due_soon_tasks = task_queryset.filter(due_soon_filter).order_by('due_date', PRIORITY_ORDER)[:4]
    overdue_tasks = task_queryset.filter(overdue_filter).order_by('due_date', PRIORITY_ORDER)[:4]
    recent_completed_tasks = task_queryset.filter(status=Task.Status.DONE).order_by('-completed_at')[:4]
    completion_rate = round((done_count / total_tasks) * 100) if total_tasks else 0
    return {
        'total_tasks': total_tasks,
        'active_count': active_count,
        'done_count': done_count,
        'due_soon_count': task_queryset.filter(due_soon_filter).count(),
        'overdue_count': task_queryset.filter(overdue_filter).count(),
        'completion_rate': completion_rate,
        'due_soon_tasks': due_soon_tasks,
        'overdue_tasks': overdue_tasks,
        'recent_completed_tasks': recent_completed_tasks,
    }


def build_course_summaries(user):
    active_statuses = [Task.Status.TODO, Task.Status.DOING]
    return Course.objects.filter(user=user).annotate(
        total_tasks=Count('tasks', distinct=True),
        completed_tasks=Count('tasks', filter=Q(tasks__status=Task.Status.DONE), distinct=True),
        active_tasks=Count('tasks', filter=Q(tasks__status__in=active_statuses), distinct=True),
        next_due_date=Min('tasks__due_date', filter=Q(tasks__status__in=active_statuses)),
    )


def build_status_board(task_queryset, limit_per_column=6):
    board = []
    for status_value, label in STATUS_COLUMNS:
        board.append({
            'key': status_value,
            'label': label,
            'tasks': list(task_queryset.filter(status=status_value)[:limit_per_column]),
        })
    return board


def get_dashboard_board(user, limit_per_column=6):
    return build_status_board(base_task_queryset(user).order_by('due_date', '-updated_at'), limit_per_column=limit_per_column)


def get_filtered_tasks(user, params):
    return apply_task_filters(base_task_queryset(user), params)


def get_overview_context(user):
    all_tasks = base_task_queryset(user).order_by('due_date', '-updated_at')
    summary = build_dashboard_summary(all_tasks)
    summary['course_count'] = Course.objects.filter(user=user).count()
    summary['course_summaries'] = build_course_summaries(user)[:6]
    return summary


def group_tasks_by_course(tasks):
    grouped = OrderedDict()
    for task in tasks:
        grouped.setdefault(str(task.course), []).append(task)
    return grouped
