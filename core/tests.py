from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import BulkTaskActionForm, CourseForm, DashboardCourseFilterForm, TaskForm
from .models import Course, Task, TaskNote


class ModelSignalTests(TestCase):
    def test_profile_created_when_user_is_created(self):
        user = User.objects.create_user(username='alice', password='pass12345')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.display_name, 'alice')


class TaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bob', password='pass12345')
        self.course = Course.objects.create(user=self.user, code='ENG5056', title='Systems Project')

    def test_completed_at_is_set_when_task_is_done(self):
        task = Task.objects.create(
            user=self.user,
            course=self.course,
            title='Submit report',
            status=Task.Status.DONE,
            priority=Task.Priority.HIGH,
            due_date=timezone.localdate(),
        )
        self.assertIsNotNone(task.completed_at)
        self.assertTrue(task.is_completed)

    def test_due_soon_property(self):
        task = Task.objects.create(
            user=self.user,
            course=self.course,
            title='Prepare demo',
            status=Task.Status.TODO,
            priority=Task.Priority.MEDIUM,
            due_date=timezone.localdate() + timedelta(days=2),
        )
        self.assertTrue(task.is_due_soon)

    def test_is_overdue_property(self):
        task = Task.objects.create(
            user=self.user,
            course=self.course,
            title='Old task',
            status=Task.Status.DOING,
            priority=Task.Priority.MEDIUM,
            due_date=timezone.localdate() - timedelta(days=1),
        )
        self.assertTrue(task.is_overdue)

    def test_mark_done_updates_status(self):
        task = Task.objects.create(
            user=self.user,
            course=self.course,
            title='Draft report',
            status=Task.Status.TODO,
            priority=Task.Priority.LOW,
            due_date=timezone.localdate() + timedelta(days=7),
        )
        task.mark_done()
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)
        self.assertIsNotNone(task.completed_at)


class FormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='eve', password='pass12345')
        self.other_user = User.objects.create_user(username='mallory', password='pass12345')
        self.course = Course.objects.create(user=self.user, code='COMPSCI5060', title='Internet Technology')
        self.other_course = Course.objects.create(user=self.other_user, code='OTHER1', title='Other Course')

    def test_course_form_normalises_code(self):
        form = CourseForm(data={'code': ' eng5056 ', 'title': '  Project  ', 'semester': ' S2 '}, user=self.user)
        self.assertTrue(form.is_valid())
        course = form.save()
        self.assertEqual(course.code, 'ENG5056')
        self.assertEqual(course.title, 'Project')

    def test_task_form_rejects_other_users_course(self):
        form = TaskForm(
            data={
                'title': 'Write report',
                'description': 'desc',
                'course': self.other_course.pk,
                'due_date': timezone.localdate() + timedelta(days=2),
                'priority': Task.Priority.MEDIUM,
                'status': Task.Status.TODO,
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('course', form.errors)

    def test_bulk_action_form_requires_selection(self):
        form = BulkTaskActionForm(data={'action': 'mark_done', 'selected_tasks': ''})
        self.assertFalse(form.is_valid())

    def test_dashboard_course_filter_form_limits_choices_to_user_courses(self):
        form = DashboardCourseFilterForm(user=self.user)
        self.assertIn(self.course, form.fields['course'].queryset)
        self.assertNotIn(self.other_course, form.fields['course'].queryset)


class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='carol', password='pass12345')
        self.other_user = User.objects.create_user(username='dave', password='pass12345')
        self.course = Course.objects.create(user=self.user, code='COMPSCI5060', title='Internet Technology')
        self.other_course = Course.objects.create(user=self.other_user, code='OTHER1', title='Other Course')
        self.task = Task.objects.create(
            user=self.user,
            course=self.course,
            title='Finish prototype',
            status=Task.Status.TODO,
            priority=Task.Priority.HIGH,
            due_date=timezone.localdate() + timedelta(days=1),
        )
        self.other_task = Task.objects.create(
            user=self.other_user,
            course=self.other_course,
            title='Someone else task',
            status=Task.Status.TODO,
            priority=Task.Priority.LOW,
            due_date=timezone.localdate() + timedelta(days=5),
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_overview_requires_login(self):
        response = self.client.get(reverse('overview'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_dashboard_course_filter_shows_only_selected_course_tasks(self):
        second_course = Course.objects.create(user=self.user, code='ENG6001', title='Embedded Systems')
        Task.objects.create(
            user=self.user,
            course=second_course,
            title='Other course task',
            status=Task.Status.DOING,
            priority=Task.Priority.MEDIUM,
            due_date=timezone.localdate() + timedelta(days=3),
        )
        self.client.login(username='carol', password='pass12345')
        response = self.client.get(reverse('dashboard'), {'course': self.course.pk})
        self.assertContains(response, 'Finish prototype')
        self.assertNotContains(response, 'Other course task')

    def test_task_list_only_shows_current_users_tasks(self):
        self.client.login(username='carol', password='pass12345')
        response = self.client.get(reverse('task_list'))
        self.assertContains(response, 'Finish prototype')
        self.assertNotContains(response, 'Someone else task')

    def test_overdue_filter_works(self):
        self.task.due_date = timezone.localdate() - timedelta(days=1)
        self.task.save()
        self.client.login(username='carol', password='pass12345')
        response = self.client.get(reverse('task_list'), {'deadline': 'overdue'})
        self.assertContains(response, 'Finish prototype')

    def test_quick_status_update_changes_status(self):
        self.client.login(username='carol', password='pass12345')
        response = self.client.post(reverse('quick_status_update', args=[self.task.pk]))
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.DOING)
        self.assertEqual(response.json()['status_label'], 'Doing')

    def test_quick_status_can_cycle_done_back_to_todo(self):
        self.task.status = Task.Status.DONE
        self.task.save()
        self.client.login(username='carol', password='pass12345')
        response = self.client.post(reverse('quick_status_update', args=[self.task.pk]))
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.TODO)
        self.assertEqual(response.json()['status_label'], 'To-do')

    def test_quick_status_can_set_specific_status(self):
        self.client.login(username='carol', password='pass12345')
        response = self.client.post(reverse('quick_status_update', args=[self.task.pk]), {'status': Task.Status.DONE})
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.DONE)
        self.assertEqual(response.json()['status'], Task.Status.DONE)

    def test_task_detail_rejects_other_users_task(self):
        self.client.login(username='dave', password='pass12345')
        response = self.client.get(reverse('task_detail', args=[self.task.pk]))
        self.assertEqual(response.status_code, 403)

    def test_task_note_can_be_added(self):
        self.client.login(username='carol', password='pass12345')
        response = self.client.post(reverse('task_note_create', args=[self.task.pk]), {'content': 'Discussed with group.'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TaskNote.objects.filter(task=self.task).count(), 1)

    def test_bulk_mark_done_updates_selected_tasks(self):
        second_task = Task.objects.create(
            user=self.user,
            course=self.course,
            title='Write README',
            status=Task.Status.TODO,
            priority=Task.Priority.MEDIUM,
            due_date=timezone.localdate() + timedelta(days=2),
        )
        self.client.login(username='carol', password='pass12345')
        response = self.client.post(
            reverse('task_bulk_action'),
            {'action': 'mark_done', 'selected_tasks': f'{self.task.pk},{second_task.pk}', 'next': reverse('task_list')},
        )
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        second_task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.DONE)
        self.assertEqual(second_task.status, Task.Status.DONE)

    def test_task_update_redirects_back_to_filtered_list(self):
        self.client.login(username='carol', password='pass12345')
        next_url = reverse('task_list') + '?deadline=overdue'
        response = self.client.post(
            reverse('task_update', args=[self.task.pk]),
            {
                'title': 'Finish prototype v2',
                'description': 'Updated',
                'course': self.course.pk,
                'due_date': timezone.localdate() + timedelta(days=1),
                'priority': Task.Priority.HIGH,
                'status': Task.Status.DOING,
                'next': next_url,
            },
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
