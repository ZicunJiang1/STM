from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import BulkTaskActionForm, CourseForm, DashboardCourseFilterForm, ProfileForm, RegisterForm, TaskFilterForm, TaskForm, TaskNoteForm
from .models import Course, Task
from .services import (
    apply_task_filters,
    base_task_queryset,
    build_course_summaries,
    build_dashboard_summary,
    build_status_board,
)


class OwnerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        obj = self.get_object()
        return obj.user == self.request.user


class NextUrlMixin:
    fallback_url_name = 'dashboard'

    def get_fallback_url(self):
        return reverse(self.fallback_url_name)

    def get_next_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return self.get_fallback_url()

    def get_success_url(self):
        return self.get_next_url()


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = 'core/register.html'
    success_url = reverse_lazy('dashboard')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, 'Your account has been created.')
        return response


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        board_filter_form = DashboardCourseFilterForm(self.request.GET or None, user=self.request.user)
        all_tasks = base_task_queryset(self.request.user).order_by('due_date', '-updated_at')
        filtered_tasks = all_tasks
        selected_course = None
        if board_filter_form.is_valid():
            selected_course = board_filter_form.cleaned_data.get('course')
            if selected_course is not None:
                filtered_tasks = filtered_tasks.filter(course=selected_course)
        summary = build_dashboard_summary(filtered_tasks)
        context.update({
            'board_filter_form': board_filter_form,
            'selected_course': selected_course,
            'board_columns': build_status_board(filtered_tasks, limit_per_column=6),
            **summary,
        })
        return context


class OverviewView(LoginRequiredMixin, TemplateView):
    template_name = 'core/overview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_tasks = base_task_queryset(self.request.user).order_by('due_date', '-updated_at')
        summary = build_dashboard_summary(all_tasks)
        context.update({
            'course_count': Course.objects.filter(user=self.request.user).count(),
            'course_summaries': build_course_summaries(self.request.user)[:6],
            **summary,
        })
        return context


class TaskListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = 'core/task_list.html'
    context_object_name = 'tasks'

    def get_queryset(self):
        return apply_task_filters(base_task_queryset(self.request.user), self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_tasks = base_task_queryset(self.request.user)
        current_query = self.request.GET.urlencode()
        current_list_url = reverse('task_list')
        if current_query:
            current_list_url = f'{current_list_url}?{current_query}'
        context['filter_form'] = TaskFilterForm(self.request.GET or None, user=self.request.user)
        context['bulk_form'] = BulkTaskActionForm(initial={'next': current_list_url})
        context['current_query'] = current_query
        context['current_list_url'] = current_list_url
        context.update(build_dashboard_summary(all_tasks))
        context['filter_active'] = any(self.request.GET.get(key) for key in ['q', 'course', 'status', 'priority', 'deadline'])
        return context


class TaskCreateView(LoginRequiredMixin, NextUrlMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'core/task_form.html'
    fallback_url_name = 'task_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_mode'] = 'create'
        context['next_url'] = self.get_next_url()
        return context

    def dispatch(self, request, *args, **kwargs):
        if not Course.objects.filter(user=request.user).exists():
            messages.info(request, 'Create a course first before adding a task.')
            return redirect('course_create')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Task created successfully.')
        return super().form_valid(form)


class TaskUpdateView(LoginRequiredMixin, OwnerRequiredMixin, NextUrlMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = 'core/task_form.html'
    fallback_url_name = 'task_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_mode'] = 'edit'
        context['next_url'] = self.get_next_url()
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Task updated successfully.')
        return super().form_valid(form)


class TaskDetailView(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = Task
    template_name = 'core/task_detail.html'
    context_object_name = 'task'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.object
        next_url = self.request.GET.get('next') or reverse('task_list')
        context['note_form'] = TaskNoteForm()
        context['next_url'] = next_url
        context['related_tasks'] = (
            base_task_queryset(self.request.user)
            .filter(course=task.course)
            .exclude(pk=task.pk)
            .prefetch_related('notes')
            .order_by('due_date')[:4]
        )
        return context


class TaskNoteCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task.objects.prefetch_related('notes'), pk=pk, user=request.user)
        form = TaskNoteForm(request.POST)
        next_url = request.POST.get('next') or reverse('task_detail', args=[pk])
        if form.is_valid():
            note = form.save(commit=False)
            note.task = task
            note.user = request.user
            note.save()
            messages.success(request, 'Note added to the task.')
        else:
            messages.error(request, 'Please enter a note before submitting.')
        return redirect(next_url)


class TaskDeleteView(LoginRequiredMixin, OwnerRequiredMixin, NextUrlMixin, DeleteView):
    model = Task
    template_name = 'core/task_confirm_delete.html'
    fallback_url_name = 'task_list'

    def form_valid(self, form):
        messages.success(self.request, 'Task deleted successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next_url'] = self.get_next_url()
        return context


class CourseListView(LoginRequiredMixin, ListView):
    model = Course
    template_name = 'core/course_list.html'
    context_object_name = 'courses'

    def get_queryset(self):
        return build_course_summaries(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course_total'] = Course.objects.filter(user=self.request.user).count()
        context['open_tasks_total'] = Task.objects.filter(user=self.request.user).exclude(status=Task.Status.DONE).count()
        return context


class CourseCreateView(LoginRequiredMixin, NextUrlMixin, CreateView):
    model = Course
    form_class = CourseForm
    template_name = 'core/course_form.html'
    fallback_url_name = 'course_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_mode'] = 'create'
        context['next_url'] = self.get_next_url()
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Course created successfully.')
        return super().form_valid(form)


class CourseUpdateView(LoginRequiredMixin, OwnerRequiredMixin, NextUrlMixin, UpdateView):
    model = Course
    form_class = CourseForm
    template_name = 'core/course_form.html'
    fallback_url_name = 'course_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_mode'] = 'edit'
        context['next_url'] = self.get_next_url()
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Course updated successfully.')
        return super().form_valid(form)


class CourseDeleteView(LoginRequiredMixin, OwnerRequiredMixin, NextUrlMixin, DeleteView):
    model = Course
    template_name = 'core/course_confirm_delete.html'
    fallback_url_name = 'course_list'

    def form_valid(self, form):
        messages.success(self.request, 'Course deleted successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next_url'] = self.get_next_url()
        return context


class ProfileView(LoginRequiredMixin, DetailView):
    template_name = 'core/profile.html'

    def get_object(self):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        summary = build_dashboard_summary(base_task_queryset(self.request.user))
        context['task_total'] = summary['total_tasks']
        context['course_total'] = Course.objects.filter(user=self.request.user).count()
        context['active_count'] = summary['active_count']
        context['completion_rate'] = summary['completion_rate']
        return context


class ProfileUpdateView(LoginRequiredMixin, NextUrlMixin, UpdateView):
    form_class = ProfileForm
    template_name = 'core/profile_form.html'
    fallback_url_name = 'profile'

    def get_object(self):
        return self.request.user.profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next_url'] = self.get_next_url()
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)


class BulkTaskActionView(LoginRequiredMixin, View):
    def post(self, request):
        form = BulkTaskActionForm(request.POST)
        fallback = request.POST.get('next') or reverse('task_list')
        if not form.is_valid():
            messages.error(request, next(iter(form.errors.values()))[0])
            return redirect(fallback)

        task_ids = [int(pk) for pk in form.cleaned_data['selected_tasks']]
        tasks = Task.objects.filter(user=request.user, pk__in=task_ids)
        action = form.cleaned_data['action']

        if action == 'delete':
            count = tasks.count()
            tasks.delete()
            messages.success(request, f'Deleted {count} selected task(s).')
        else:
            status_map = {
                'mark_todo': Task.Status.TODO,
                'mark_doing': Task.Status.DOING,
                'mark_done': Task.Status.DONE,
            }
            updated = 0
            for task in tasks:
                task.status = status_map[action]
                task.save()
                updated += 1
            messages.success(request, f'Updated {updated} selected task(s).')
        return redirect(form.cleaned_data.get('next') or reverse('task_list'))


@require_POST
def quick_status_update(request: HttpRequest, pk: int) -> JsonResponse:
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=401)

    task = get_object_or_404(Task, pk=pk, user=request.user)
    requested_status = request.POST.get('status', '').strip()
    cycle = {
        Task.Status.TODO: Task.Status.DOING,
        Task.Status.DOING: Task.Status.DONE,
        Task.Status.DONE: Task.Status.TODO,
    }
    valid_statuses = {choice for choice, _ in Task.Status.choices}

    if requested_status:
        if requested_status not in valid_statuses:
            return JsonResponse({'error': 'Invalid status.'}, status=400)
        task.status = requested_status
    else:
        task.status = cycle[task.status]
    task.save()
    return JsonResponse(
        {
            'id': task.id,
            'status': task.status,
            'status_label': task.get_status_display(),
            'is_due_soon': task.is_due_soon,
            'is_overdue': task.is_overdue,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'detail_url': reverse('task_detail', args=[task.pk]),
            'priority_label': task.get_priority_display(),
            'course_code': task.course.code,
            'course_title': task.course.title,
            'due_date': task.due_date.strftime('%d %b %Y'),
        }
    )
