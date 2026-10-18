"""Summary status is read-only and stays useful while the background job completes or fails."""
import threading
import unittest
import urllib.error
from unittest.mock import patch

import test_app
from elyra import providers


class SummaryStatusTest(unittest.TestCase):
    request = test_app.AppTests.request
    json = test_app.AppTests.json
    room = test_app.AppTests.room

    @classmethod
    def setUpClass(cls):
        test_app.AppTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        test_app.AppTests.tearDownClass.__func__(cls)

    def test_status_poll_never_calls_model_or_changes_notes(self):
        room = self.room()
        self.store.save_notes(room['id'], 'My private note')
        self.store.save_summary(room['id'], 'Existing automatic summary', 1, 0)
        with patch('app.summary.run') as run, patch('elyra.providers.complete') as complete:
            for _ in range(2):
                status = self.json(f'/api/rooms/{room["id"]}/summary')
                self.assertEqual(status, {'summary':'Existing automatic summary','summary_count':1,'summary_state':'idle'})
            run.assert_not_called()
            complete.assert_not_called()
        self.assertEqual(self.store.room(room['id'])['notes'], 'My private note')
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.json('/api/rooms/missing/summary')
        self.assertEqual(raised.exception.code,404)

    def test_busy_job_is_deduplicated_and_new_summary_becomes_visible(self):
        room = self.room()
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        def summarize(store, room_id, provider, model):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('Test worker did not resume')
            store.save_summary(room_id, 'Updated automatically', 1, 0)
            return True
        # Observe cleanup without relying on an arbitrary time.sleep.
        class Jobs(set):
            def discard(inner, value):
                super().discard(value)
                finished.set()
        self.server.summarizing = Jobs()
        try:
            with patch('app.summary.run',side_effect=summarize) as run:
                self.server.summarize_later(room['id'],'xai','test-model')
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.json(f'/api/rooms/{room["id"]}/summary')['summary_state'],'updating')
                self.server.summarize_later(room['id'],'xai','test-model')
                self.assertEqual(run.call_count,1)
                release.set()
                self.assertTrue(finished.wait(3))
            status = self.json(f'/api/rooms/{room["id"]}/summary')
            self.assertEqual(status['summary'],'Updated automatically')
            self.assertEqual(status['summary_state'],'idle')
        finally:
            release.set()

    def test_failure_preserves_previous_summary_and_retry_clears_error(self):
        room = self.room()
        self.store.save_summary(room['id'],'Keep this summary',1,0)
        finished = threading.Event()
        class Jobs(set):
            def discard(inner, value):
                super().discard(value)
                finished.set()
        self.server.summarizing = Jobs()
        with patch('app.summary.run',side_effect=providers.ProviderError('private upstream detail')):
            self.server.summarize_later(room['id'],'xai','test-model')
            self.assertTrue(finished.wait(3))
        status = self.json(f'/api/rooms/{room["id"]}/summary')
        self.assertEqual(status['summary'],'Keep this summary')
        self.assertEqual(status['summary_state'],'error')
        self.assertNotIn('private',str(status))
        finished.clear()
        with patch('app.summary.run',return_value=False):
            self.server.summarize_later(room['id'],'xai','test-model')
            self.assertTrue(finished.wait(3))
        self.assertEqual(self.json(f'/api/rooms/{room["id"]}/summary')['summary_state'],'idle')
