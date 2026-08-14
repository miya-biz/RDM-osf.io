# -*- coding: utf-8 -*-
from unittest import mock
import pytest

from celery import states


def _addon_with_task(task_id):
    addon = mock.MagicMock()
    addon.owner._id = 'node123'
    addon.get_publish_task_id.return_value = {'task_id': task_id}
    return addon


def _async_result(state, info_reads):
    """AsyncResult stub whose info property yields a different value per read,
    like the real live property that queries the result backend each time."""
    aresult = mock.MagicMock()
    aresult.state = state
    aresult.failed.return_value = state == states.FAILURE
    reads = iter(info_reads)
    # a plain side_effect list would raise exception instances instead of
    # returning them, so hand each value back through a callable
    type(aresult).info = mock.PropertyMock(side_effect=lambda: next(reads))
    return aresult


@pytest.mark.usefixtures('request_context')
def test_progress_poll_uses_a_single_info_snapshot():
    """The task can finish between two reads of AsyncResult.info; the view must
    branch and read on one snapshot instead of raising KeyError."""
    from addons.weko import views

    progress_info = {'progress': 60}
    result_info = {'result': 'https://weko.test/records/1', 'response': {'status': 'OK'}}
    # enough reads for multi-read code to cross the progress-to-result
    # transition; single-snapshot code consumes only the first entry
    aresult = _async_result('PROGRESS', [progress_info, progress_info, result_info, result_info])

    with mock.patch.object(views.celery_app, 'AsyncResult', return_value=aresult):
        ret = views._get_publishing_project_metadata_progress(
            _addon_with_task('task123'), 'draft_registration', 'md123')

    attr = ret['data']['attributes']
    assert attr['progress'] == {'state': 'PROGRESS', 'rate': 60}


@pytest.mark.usefixtures('request_context')
def test_progress_poll_reports_completed_result():
    from addons.weko import views

    result_info = {'result': 'https://weko.test/records/1', 'response': {'status': 'OK'}}
    aresult = _async_result(states.SUCCESS, [result_info] * 6)

    with mock.patch.object(views.celery_app, 'AsyncResult', return_value=aresult):
        ret = views._get_publishing_project_metadata_progress(
            _addon_with_task('task123'), 'draft_registration', 'md123')

    attr = ret['data']['attributes']
    assert attr['result'] == 'https://weko.test/records/1'
    assert attr['response'] == {'status': 'OK'}


@pytest.mark.usefixtures('request_context')
def test_progress_poll_reports_failure():
    from addons.weko import views

    error = RuntimeError('deposit failed')
    aresult = _async_result(states.FAILURE, [error] * 6)

    with mock.patch.object(views.celery_app, 'AsyncResult', return_value=aresult):
        ret = views._get_publishing_project_metadata_progress(
            _addon_with_task('task123'), 'draft_registration', 'md123')

    attr = ret['data']['attributes']
    assert attr['error'] == 'deposit failed'
