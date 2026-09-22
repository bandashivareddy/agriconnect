"""Deterministic season labels and snapshot scheduling; no agronomy calendar."""
from datetime import timedelta

DATE_SCHEDULES = ('days_after_season_start', 'days_before_planting',
                  'days_after_planting', 'days_before_harvest')


def season_label(start, lifecycle=None):
    if start is None:
        return None
    return f'{start.year}-{str(start.year + 1)[-2:]}' if lifecycle == 'perennial' else str(start.year)


def next_season_start(start):
    try:
        return start.replace(year=start.year + 1)
    except ValueError:
        if start.year == 9999:
            raise ValueError('Next season is outside the supported date range.')
        return start.replace(year=start.year + 1, day=28)


def validate_season_dates(start, planting, harvest, perennial=False):
    if start and harvest and harvest <= start:
        raise ValueError('Expected harvest must be after season start.')
    if start and planting and not perennial and planting < start:
        raise ValueError('Season start must be on or before expected/actual planting.')


def task_due(task, start, planting, harvest):
    kind = task['schedule_type']
    if kind not in DATE_SCHEDULES:
        return None
    anchor = start if kind == 'days_after_season_start' else harvest if kind == 'days_before_harvest' else planting
    if anchor is None:
        names = {'days_after_season_start': 'season start', 'days_before_harvest': 'expected harvest'}
        raise ValueError(f"Enter {names.get(kind, 'expected/actual planting')} for this task schedule.")
    try:
        due = anchor + timedelta(days=task['offset_days'] * (-1 if kind.startswith('days_before') else 1))
    except OverflowError as exc:
        raise ValueError('Calculated task date is outside the supported date range.') from exc
    if start and task.get('phase') is not None and due < start:
        raise ValueError('A task falls before season start. Correct the season dates or select an appropriate SOP.')
    return due
