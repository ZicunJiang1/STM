const App = (() => {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  const STATUS_LABELS = { todo: 'To-do', doing: 'Doing', done: 'Done' };

  function buildDueFlag(data) {
    if (data.is_overdue) {
      return { text: 'Overdue', className: 'badge badge-danger' };
    }
    if (data.is_due_soon) {
      return { text: 'Due soon', className: 'badge due-badge' };
    }
    return null;
  }

  function nextStatus(currentStatus) {
    const cycle = { todo: 'doing', doing: 'done', done: 'todo' };
    return cycle[currentStatus] || 'todo';
  }

  function getBoardColumn(status) {
    return document.querySelector(`[data-board-column][data-status-key="${status}"]`);
  }

  function getBoardStack(status) {
    return getBoardColumn(status)?.querySelector('[data-board-stack]') || null;
  }

  function createEmptyState(label) {
    const empty = document.createElement('div');
    empty.className = 'kanban-empty';
    empty.dataset.emptyState = 'true';
    empty.innerHTML = `<p>${label}</p>`;
    return empty;
  }

  function syncBoardColumnState(status) {
    const column = getBoardColumn(status);
    if (!column) return;
    const stack = column.querySelector('[data-board-stack]');
    const countTarget = column.querySelector('[data-column-count]');
    if (!stack || !countTarget) return;
    const cards = stack.querySelectorAll('.kanban-task');
    countTarget.textContent = cards.length;

    const existingEmpty = stack.querySelector('[data-empty-state]');
    if (cards.length === 0 && !existingEmpty) {
      stack.appendChild(createEmptyState(stack.dataset.emptyLabel || 'No tasks.'));
    }
    if (cards.length > 0 && existingEmpty) {
      existingEmpty.remove();
    }
  }

  function syncAllBoardColumns() {
    ['todo', 'doing', 'done'].forEach(syncBoardColumnState);
  }

  function moveBoardCard(container, status) {
    if (!container?.classList.contains('kanban-task')) return;
    const destinationStack = getBoardStack(status);
    if (!destinationStack) return;
    const currentStack = container.closest('[data-board-stack]');
    if (currentStack === destinationStack) {
      syncBoardColumnState(status);
      return;
    }
    const emptyState = destinationStack.querySelector('[data-empty-state]');
    if (emptyState) emptyState.remove();
    destinationStack.prepend(container);
    syncAllBoardColumns();
  }

  function optimisticallyMoveBoardCard(container, targetStatus) {
    if (!container?.classList.contains('kanban-task')) return null;
    const originalStatus = container.dataset.taskStatus;
    const originalStack = container.closest('[data-board-stack]');
    const destinationStack = getBoardStack(targetStatus);
    if (!originalStack || !destinationStack || originalStatus === targetStatus) return null;

    const originalNextSibling = container.nextElementSibling;
    const previousLabel = container.querySelector('[data-status-text]')?.textContent || STATUS_LABELS[originalStatus] || originalStatus;
    const previousFlag = container.querySelector('[data-due-flag]')?.outerHTML || '';

    const statusTargets = container.querySelectorAll('[data-status-text]');
    statusTargets.forEach((target) => {
      target.textContent = STATUS_LABELS[targetStatus] || targetStatus;
      target.className = `badge status-badge status-${targetStatus}`;
    });

    const existingFlag = container.querySelector('[data-due-flag]');
    if (existingFlag) existingFlag.remove();

    const emptyState = destinationStack.querySelector('[data-empty-state]');
    if (emptyState) emptyState.remove();
    destinationStack.prepend(container);
    container.dataset.taskStatus = targetStatus;
    syncAllBoardColumns();

    return {
      originalStatus,
      originalStack,
      originalNextSibling,
      previousLabel,
      previousFlag,
      rollback() {
        const currentFlag = container.querySelector('[data-due-flag]');
        if (currentFlag) currentFlag.remove();
        const statusNodes = container.querySelectorAll('[data-status-text]');
        statusNodes.forEach((target) => {
          target.textContent = previousLabel;
          target.className = `badge status-badge status-${originalStatus}`;
        });
        if (previousFlag) {
          const metaRow = container.querySelector('.kanban-task-meta');
          if (metaRow) metaRow.insertAdjacentHTML('beforeend', previousFlag);
        }
        container.dataset.taskStatus = originalStatus;
        if (originalNextSibling && originalNextSibling.parentElement === originalStack) {
          originalStack.insertBefore(container, originalNextSibling);
        } else {
          originalStack.appendChild(container);
        }
        syncAllBoardColumns();
      }
    };
  }

  function updateTaskContainer(container, data) {
    const statusTargets = container.querySelectorAll('[data-status-text]');
    statusTargets.forEach((target) => {
      target.textContent = data.status_label;
      target.className = `badge status-badge status-${data.status}`;
    });

    const dueFlag = buildDueFlag(data);
    const dueTargets = container.querySelectorAll('[data-due-flag]');
    dueTargets.forEach((target) => {
      if (!dueFlag) {
        target.remove();
        return;
      }
      target.textContent = dueFlag.text;
      target.className = dueFlag.className;
    });

    if (!dueTargets.length && dueFlag) {
      const chipRow = container.querySelector('.task-chip-row, .task-row-badges, .hero-pill-row, .kanban-task-meta');
      if (chipRow) {
        const span = document.createElement('span');
        span.dataset.dueFlag = 'true';
        span.textContent = dueFlag.text;
        span.className = dueFlag.className;
        chipRow.appendChild(span);
      }
    }

    container.dataset.taskStatus = data.status;
    container.classList.toggle('task-card-overdue', data.is_overdue);
    container.classList.toggle('task-row-card-overdue', data.is_overdue);
    container.classList.toggle('kanban-task-overdue', data.is_overdue);
    container.classList.toggle('task-card-due-soon', !data.is_overdue && data.is_due_soon);
    container.classList.toggle('task-row-card-due', !data.is_overdue && data.is_due_soon);
    container.classList.toggle('kanban-task-due-soon', !data.is_overdue && data.is_due_soon);

    if (container.classList.contains('kanban-task')) {
      moveBoardCard(container, data.status);
    }
  }

  async function submitTaskStatus(url, status) {
    const body = new URLSearchParams();
    if (status) body.set('status', status);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
      },
      body: body.toString()
    });
    if (!response.ok) {
      throw new Error('Request failed');
    }
    return response.json();
  }

  const QuickStatus = {
    init() {
      const buttons = document.querySelectorAll('.quick-status-btn');
      buttons.forEach((button) => {
        button.addEventListener('click', async () => {
          const url = button.dataset.quickStatusUrl;
          const container = button.closest('[data-task-id]');
          const originalText = button.textContent;
          button.disabled = true;
          button.textContent = 'Updating...';
          try {
            const currentStatus = container?.dataset.taskStatus || 'todo';
            const data = await submitTaskStatus(url, nextStatus(currentStatus));
            if (container) updateTaskContainer(container, data);
            button.textContent = 'Updated';
            setTimeout(() => {
              button.textContent = originalText;
            }, 700);
          } catch (error) {
            button.textContent = 'Try again';
          } finally {
            button.disabled = false;
          }
        });
      });
    }
  };

  const TaskBoardDnD = {
    draggedCard: null,
    init() {
      const cards = document.querySelectorAll('.kanban-task[draggable="true"]');
      const columns = document.querySelectorAll('[data-board-column]');
      if (!cards.length || !columns.length) return;

      cards.forEach((card) => {
        card.addEventListener('dragstart', (event) => {
          this.draggedCard = card;
          card.classList.add('is-dragging');
          if (event.dataTransfer) {
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', card.dataset.taskId || '');
          }
        });

        card.addEventListener('dragend', () => {
          card.classList.remove('is-dragging');
          this.clearColumnHighlights();
          this.draggedCard = null;
        });
      });

      columns.forEach((column) => {
        const stack = column.querySelector('[data-board-stack]');
        if (!stack) return;

        column.addEventListener('dragover', (event) => {
          event.preventDefault();
          column.classList.add('is-drop-target');
          if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
        });

        column.addEventListener('dragleave', (event) => {
          if (!column.contains(event.relatedTarget)) {
            column.classList.remove('is-drop-target');
          }
        });

        column.addEventListener('drop', async (event) => {
          event.preventDefault();
          column.classList.remove('is-drop-target');
          if (!this.draggedCard) return;
          const card = this.draggedCard;
          const targetStatus = column.dataset.statusKey;
          const currentStatus = card.dataset.taskStatus;
          if (!targetStatus || targetStatus === currentStatus) return;

          const quickButton = card.querySelector('.quick-status-btn');
          const url = quickButton?.dataset.quickStatusUrl;
          if (!url) return;

          const rollbackState = optimisticallyMoveBoardCard(card, targetStatus);
          card.classList.add('is-updating');
          try {
            const data = await submitTaskStatus(url, targetStatus);
            updateTaskContainer(card, data);
          } catch (error) {
            rollbackState?.rollback();
            card.classList.add('shake-error');
            setTimeout(() => card.classList.remove('shake-error'), 420);
          } finally {
            card.classList.remove('is-updating');
          }
        });
      });

      syncAllBoardColumns();
    },
    clearColumnHighlights() {
      document.querySelectorAll('[data-board-column]').forEach((column) => {
        column.classList.remove('is-drop-target');
      });
    }
  };
  const ConfirmModal = {
    init() {
      this.root = document.querySelector('[data-confirm-modal]');
      if (!this.root) return;
      this.title = this.root.querySelector('#confirm-modal-title');
      this.message = this.root.querySelector('#confirm-modal-message');
      this.acceptButton = this.root.querySelector('[data-confirm-accept-button]');
      this.cancelButton = this.root.querySelector('[data-confirm-cancel-button]');
      this.closeElements = this.root.querySelectorAll('[data-confirm-close], [data-confirm-cancel-button]');
      this.activeResolver = null;
      this.previouslyFocused = null;

      this.acceptButton.addEventListener('click', () => this.resolve(true));
      this.closeElements.forEach((element) => {
        element.addEventListener('click', () => this.resolve(false));
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && this.isOpen()) {
          this.resolve(false);
        }
      });
    },
    isOpen() {
      return this.root && !this.root.classList.contains('hidden');
    },
    open({ title, message, confirmLabel, cancelLabel }) {
      if (!this.root) return Promise.resolve(window.confirm(message || 'Are you sure?'));
      this.title.textContent = title || 'Confirm action';
      this.message.textContent = message || 'Are you sure?';
      this.acceptButton.textContent = confirmLabel || 'Continue';
      this.cancelButton.textContent = cancelLabel || 'Cancel';
      this.previouslyFocused = document.activeElement;
      this.root.classList.remove('hidden');
      this.root.setAttribute('aria-hidden', 'false');
      document.body.classList.add('modal-open');
      window.setTimeout(() => this.acceptButton.focus(), 0);
      return new Promise((resolve) => {
        this.activeResolver = resolve;
      });
    },
    resolve(value) {
      if (!this.root || !this.activeResolver) return;
      const resolve = this.activeResolver;
      this.activeResolver = null;
      this.root.classList.add('hidden');
      this.root.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('modal-open');
      if (this.previouslyFocused && typeof this.previouslyFocused.focus === 'function') {
        this.previouslyFocused.focus();
      }
      resolve(value);
    }
  };

  const Confirmations = {
    init() {
      const forms = document.querySelectorAll('form[data-confirm], form[data-confirm-title]');
      forms.forEach((form) => {
        form.addEventListener('submit', async (event) => {
          if (form.dataset.confirmed === 'true') {
            form.dataset.confirmed = 'false';
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          const accepted = await ConfirmModal.open({
            title: form.dataset.confirmTitle || 'Confirm action',
            message: form.dataset.confirm || 'Are you sure you want to continue?',
            confirmLabel: form.dataset.confirmConfirm || 'Continue',
            cancelLabel: form.dataset.confirmCancel || 'Cancel'
          });
          if (!accepted) return;
          form.dataset.confirmed = 'true';
          if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
          } else {
            form.submit();
          }
        });
      });
    }
  };

  const FormHelpers = {
    initDescriptionCounter() {
      const textareas = document.querySelectorAll('textarea');
      textareas.forEach((textarea) => {
        const helper = document.querySelector(`[data-char-count-for="${textarea.id}"]`);
        if (!helper) return;
        const render = () => {
          helper.textContent = `${textarea.value.length} characters`;
        };
        textarea.addEventListener('input', render);
        render();
      });
    },
    initAvatarPreview() {
      const avatarInput = document.querySelector('#id_avatar');
      const avatarPreview = document.querySelector('#avatar-preview');
      const avatarFallback = document.querySelector('#avatar-preview-fallback');
      if (!avatarInput || !avatarPreview) return;
      const render = () => {
        const value = avatarInput.value.trim();
        if (value) {
          avatarPreview.src = value;
          avatarPreview.classList.remove('hidden');
          if (avatarFallback) avatarFallback.classList.add('hidden');
        } else {
          avatarPreview.classList.add('hidden');
          if (avatarFallback) avatarFallback.classList.remove('hidden');
        }
      };
      avatarInput.addEventListener('input', render);
      render();
    }
  };

  const Navigation = {
    initMobileNav() {
      const button = document.querySelector('.nav-toggle');
      const nav = document.querySelector('.site-nav');
      if (!button || !nav) return;
      button.addEventListener('click', () => {
        const isOpen = nav.classList.toggle('is-open');
        button.setAttribute('aria-expanded', String(isOpen));
      });
    }
  };

  const BulkActions = {
    init() {
      const form = document.querySelector('[data-bulk-form]');
      if (!form) return;
      const selectAll = form.querySelector('[data-select-all]');
      const checkboxes = document.querySelectorAll('.task-select-checkbox');
      const selectedInput = form.querySelector('[data-selected-tasks-input]');
      const selectionCount = form.querySelector('[data-selection-count]');
      const submitButton = form.querySelector('[data-bulk-submit]');

      const sync = () => {
        const selected = [...checkboxes].filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
        selectedInput.value = selected.join(',');
        if (selectionCount) selectionCount.textContent = `${selected.length} selected`;
        if (submitButton) submitButton.disabled = selected.length === 0;
        if (selectAll) selectAll.checked = selected.length > 0 && selected.length === checkboxes.length;
      };

      if (selectAll) {
        selectAll.addEventListener('change', () => {
          checkboxes.forEach((checkbox) => {
            checkbox.checked = selectAll.checked;
          });
          sync();
        });
      }

      checkboxes.forEach((checkbox) => checkbox.addEventListener('change', sync));
      sync();
    }
  };

  const PageTransition = {
    duration: 130,
    init() {
      requestAnimationFrame(() => document.body.classList.add('page-ready'));
      this.bindLinks();
      this.bindForms();
    },
    shouldHandleLink(link) {
      if (!link || link.target === '_blank' || link.hasAttribute('download')) return false;
      if (link.getAttribute('href')?.startsWith('#')) return false;
      if (link.dataset.noTransition !== undefined) return false;
      const url = new URL(link.href, window.location.origin);
      return url.origin === window.location.origin;
    },
    leave(callback) {
      document.body.classList.remove('page-ready');
      document.body.classList.add('page-leaving');
      window.setTimeout(callback, this.duration);
    },
    bindLinks() {
      document.addEventListener('click', (event) => {
        const link = event.target.closest('a[href]');
        if (!this.shouldHandleLink(link)) return;
        event.preventDefault();
        const destination = link.href;
        this.leave(() => {
          window.location.href = destination;
        });
      });
    },
    bindForms() {
      document.addEventListener('submit', (event) => {
        if (event.defaultPrevented) return;
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        if (form.dataset.pageTransitionForm === undefined) return;
        if (form.dataset.transitionLocked === 'true') return;
        if (form.dataset.ajaxForm === 'true') return;
        event.preventDefault();
        form.dataset.transitionLocked = 'true';
        this.leave(() => form.submit());
      });
    }
  };

  function init() {
    ConfirmModal.init();
    QuickStatus.init();
    Confirmations.init();
    FormHelpers.initDescriptionCounter();
    FormHelpers.initAvatarPreview();
    Navigation.initMobileNav();
    BulkActions.init();
    TaskBoardDnD.init();
    PageTransition.init();
  }

  return { init };
})();

window.addEventListener('DOMContentLoaded', App.init);
