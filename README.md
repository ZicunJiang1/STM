# STM
This is a student task manager app for assessment of Information Technology
=======
# Student Task Manager — UI-focused second version

A Django coursework project implementing a premium-feel student task manager with:

- user registration, login, and logout
- course CRUD
- task CRUD
- quick status cycling with JavaScript
- smart filtering and sorting
- due soon / overdue visual emphasis
- dashboard analytics cards
- task detail page with notes
- profile page with avatar preview

## Run locally

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Test suite

```bash
python manage.py test
```

## Main routes

- `/dashboard/`
- `/tasks/`
- `/tasks/<id>/`
- `/courses/`
- `/profile/`

## Notes

This second version prioritises visual hierarchy, premium UI styling, cleaner card-based layouts, and a more presentation-ready dashboard.


## Added in this version

- Overview page separated from the main dashboard.
- Task detail page with notes.
- Overdue filter in the task list.
- Bulk task actions from the task list.
- Filter-preserving navigation when opening, editing, and deleting tasks.
- Logout confirmation and page transition animations.
- Environment-variable based settings via `.env.example`.
