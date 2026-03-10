from __future__ import annotations

import calendar
from collections import OrderedDict, defaultdict
from datetime import date, timedelta

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

PRIORITY_ORDER_DESC = Case(
    When(priority=Task.Priority.LOW, then=0),
    When(priority=Task.Priority.MEDIUM, then=1),
    When(priority=Task.Priority.HIGH, then=2),
    default=3,
    output_field=IntegerField(),
)

STATUS_ORDER = Case(
    When(status=Task.Status.TODO, then=0),
    When(status=Task.Status.DOING, then=1),
    When(status=Task.Status.DONE, then=2),
    default=3,
    output_field=IntegerField(),
)

STATUS_COLUMNS = [
    (Task.Status.TODO, 'To-do'),
    (Task.Status.DOING, 'Doing'),
    (Task.Status.DONE, 'Done'),
]

OVERVIEW_TABS = (
    ('progress', 'Progress'),
    ('deadlines', 'Deadlines'),
    ('calendar', 'Calendar'),
)


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

    if sort == 'title_asc':
        queryset = queryset.order_by('title', '-updated_at')
    elif sort == 'title_desc':
        queryset = queryset.order_by('-title', '-updated_at')
    elif sort == 'course_asc':
        queryset = queryset.order_by('course__code', 'title')
    elif sort == 'course_desc':
        queryset = queryset.order_by('-course__code', 'title')
    elif sort == 'status_asc':
        queryset = queryset.annotate(status_rank=STATUS_ORDER).order_by('status_rank', 'due_date', '-updated_at')
    elif sort == 'status_desc':
        queryset = queryset.annotate(status_rank=STATUS_ORDER).order_by('-status_rank', 'due_date', '-updated_at')
    elif sort in {'priority', 'priority_asc'}:
        queryset = queryset.order_by(PRIORITY_ORDER, 'due_date', '-updated_at')
    elif sort == 'priority_desc':
        queryset = queryset.order_by(PRIORITY_ORDER_DESC, 'due_date', '-updated_at')
    elif sort == 'due_asc':
        queryset = queryset.order_by('due_date', '-updated_at')
    elif sort == 'due_desc':
        queryset = queryset.order_by('-due_date', '-updated_at')
    elif sort in {'updated_desc', 'updated_descending'}:
        queryset = queryset.order_by('-updated_at')
    elif sort == 'updated_asc':
        queryset = queryset.order_by('updated_at')
    elif sort == 'created_asc':
        queryset = queryset.order_by('created_at')
    elif sort == 'created_desc':
        queryset = queryset.order_by('-created_at')
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


def parse_month_param(month_value: str | None) -> tuple[int, int]:
    today = timezone.localdate()
    if month_value:
        try:
            year_str, month_str = month_value.split('-', 1)
            year = int(year_str)
            month = int(month_str)
            if 1 <= month <= 12:
                return year, month
        except (TypeError, ValueError):
            pass
    return today.year, today.month


def build_calendar_context(user, month_value: str | None = None):
    year, month = parse_month_param(month_value)
    month_start = date(year, month, 1)
    month_calendar = calendar.Calendar(firstweekday=0)
    week_dates = month_calendar.monthdatescalendar(year, month)
    range_start = week_dates[0][0]
    range_end = week_dates[-1][-1]

    tasks = list(
        base_task_queryset(user)
        .filter(due_date__gte=range_start, due_date__lte=range_end)
        .order_by('due_date', PRIORITY_ORDER, 'title')
    )
    tasks_by_date = defaultdict(list)
    for task in tasks:
        tasks_by_date[task.due_date].append(task)

    today = timezone.localdate()
    weeks = []
    for week in week_dates:
        day_cells = []
        for day in week:
            day_tasks = tasks_by_date.get(day, [])
            day_cells.append({
                'date': day,
                'in_month': day.month == month,
                'is_today': day == today,
                'tasks': day_tasks[:2],
                'extra_count': max(0, len(day_tasks) - 2),
            })
        weeks.append(day_cells)

    prev_anchor = month_start - timedelta(days=1)
    next_anchor = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_task_count = sum(1 for task in tasks if task.due_date.month == month and task.due_date.year == year)

    return {
        'calendar_label': month_start.strftime('%B %Y'),
        'calendar_month_param': month_start.strftime('%Y-%m'),
        'calendar_prev_param': prev_anchor.strftime('%Y-%m'),
        'calendar_next_param': next_anchor.strftime('%Y-%m'),
        'calendar_weeks': weeks,
        'calendar_weekdays': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'calendar_month_task_count': month_task_count,
    }


def group_tasks_by_course(tasks):
    grouped = OrderedDict()
    for task in tasks:
        grouped.setdefault(str(task.course), []).append(task)
    return grouped
