from __future__ import annotations

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Course, Profile, Task, TaskNote


class StyledFormMixin:
    def apply_styling(self):
        for field_name, field in self.fields.items():
            css_class = 'form-control'
            if isinstance(field.widget, forms.Select):
                css_class = 'form-select'
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = 'form-check-input'
            field.widget.attrs.setdefault('class', css_class)
            field.widget.attrs.setdefault('autocomplete', 'off')
            if self.errors.get(field_name):
                field.widget.attrs['aria-invalid'] = 'true'


class RegisterForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.setdefault('placeholder', 'Choose a username')
        self.fields['email'].widget.attrs.setdefault('placeholder', 'you@example.com')
        self.fields['password1'].widget.attrs.setdefault('placeholder', 'Create a strong password')
        self.fields['password2'].widget.attrs.setdefault('placeholder', 'Repeat your password')
        self.apply_styling()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('display_name', 'avatar')
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': 'Display name'}),
            'avatar': forms.URLInput(attrs={'placeholder': 'https://example.com/avatar.png'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styling()


class CourseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = ('code', 'title', 'semester')
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': 'e.g. ENG5056'}),
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Internet Technology'}),
            'semester': forms.TextInput(attrs={'placeholder': 'e.g. Semester 2'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.apply_styling()

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            raise forms.ValidationError('Course code cannot be empty.')
        queryset = Course.objects.filter(user=self.user, code=code)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if self.user is not None and queryset.exists():
            raise forms.ValidationError('You already have a course with this code.')
        return code

    def clean_title(self):
        title = (self.cleaned_data.get('title') or '').strip()
        if not title:
            raise forms.ValidationError('Course title cannot be empty.')
        return title

    def clean_semester(self):
        return (self.cleaned_data.get('semester') or '').strip()

    def save(self, commit=True):
        course = super().save(commit=False)
        if self.user is not None:
            course.user = self.user
        if commit:
            course.save()
        return course


class TaskForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ('title', 'description', 'course', 'due_date', 'priority', 'status')
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Input task title'}),
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Add task context, subtasks, or links', 'maxlength': '1200'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user is not None:
            self.fields['course'].queryset = Course.objects.filter(user=self.user)
        self.apply_styling()

    def clean_title(self):
        title = (self.cleaned_data.get('title') or '').strip()
        if not title:
            raise forms.ValidationError('Task title cannot be empty.')
        return title

    def clean_description(self):
        return (self.cleaned_data.get('description') or '').strip()

    def clean_course(self):
        course = self.cleaned_data['course']
        if self.user is not None and course.user != self.user:
            raise forms.ValidationError('You can only assign tasks to your own courses.')
        return course

    def save(self, commit=True):
        task = super().save(commit=False)
        if self.user is not None:
            task.user = self.user
        if commit:
            task.save()
        return task


class TaskNoteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TaskNote
        fields = ('content',)
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Write a progress note, reminder, or meeting update', 'maxlength': '800'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styling()

    def clean_content(self):
        content = (self.cleaned_data.get('content') or '').strip()
        if not content:
            raise forms.ValidationError('Please enter a note before submitting.')
        return content


class DashboardCourseFilterForm(StyledFormMixin, forms.Form):
    course = forms.ModelChoiceField(
        required=False,
        queryset=Course.objects.none(),
        empty_label='All courses',
        label='Course',
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['course'].queryset = Course.objects.filter(user=user).order_by('code', 'title')
        self.apply_styling()


class TaskFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(required=False, label='Search', widget=forms.TextInput(attrs={'placeholder': 'Search title, description, or course'}))
    course = forms.ModelChoiceField(required=False, queryset=Course.objects.none(), empty_label='All courses')
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses'), *Task.Status.choices])
    priority = forms.ChoiceField(required=False, choices=[('', 'All priorities'), *Task.Priority.choices])
    deadline = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All deadlines'),
            ('due_soon', 'Due soon'),
            ('overdue', 'Overdue'),
        ],
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ('smart', 'Smart order'),
            ('due_asc', 'Due date ↑'),
            ('due_desc', 'Due date ↓'),
            ('priority', 'Priority'),
            ('updated_desc', 'Recently updated'),
            ('course', 'Course'),
        ],
        initial='smart',
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['course'].queryset = Course.objects.filter(user=user)
        self.apply_styling()


class BulkTaskActionForm(StyledFormMixin, forms.Form):
    action = forms.ChoiceField(
        choices=[
            ('mark_todo', 'Mark as To-do'),
            ('mark_doing', 'Mark as Doing'),
            ('mark_done', 'Mark as Done'),
            ('delete', 'Delete selected'),
        ]
    )
    selected_tasks = forms.CharField(widget=forms.HiddenInput)
    next = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styling()

    def clean_selected_tasks(self):
        raw = self.cleaned_data.get('selected_tasks', '')
        values = [item.strip() for item in raw.split(',') if item.strip()]
        if not values:
            raise forms.ValidationError('Select at least one task.')
        if any(not value.isdigit() for value in values):
            raise forms.ValidationError('Invalid task selection.')
        return values
