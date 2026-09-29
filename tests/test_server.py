import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('server', Path(__file__).resolve().parents[1] / 'plugin/server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class MatrixOrderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        server.DATA_FILE = Path(self.directory.name) / 'tasks.json'
        server.LOCK_FILE = server.DATA_FILE.with_suffix('.lock')
        self.task = dict(id='a', name='Example', importance='high', urgency='high', matrixOrder=2, today=True)

    def test_legacy_tasks_remain_valid(self):
        del self.task['matrixOrder']
        self.assertNotIn('matrixOrder', server.valid_task(self.task))

    def test_order_round_trip_and_codex_edits(self):
        server.change_tasks([self.task])
        self.assertEqual(server.read_tasks()[0]['matrixOrder'], 2)
        updated = server.call_tool('update_task', {'id': 'a', 'name': 'Renamed'})
        self.assertEqual(updated['matrixOrder'], 2)
        self.assertTrue(updated['today'])
        server.call_tool('complete_task', {'id': 'a'})
        reopened = server.call_tool('complete_task', {'id': 'a', 'completed': False})
        self.assertEqual(reopened['matrixOrder'], 2)

    def test_codex_move_clears_old_box_order(self):
        server.change_tasks([self.task])
        moved = server.call_tool('update_task', {'id': 'a', 'urgency': 'low'})
        self.assertNotIn('matrixOrder', moved)
        self.assertNotIn('matrixOrder', server.read_tasks()[0])

    def test_invalid_order_rejected(self):
        for value in [-1, 1.5, True, '2', float('inf'), 9007199254740992]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                server.valid_task({**self.task, 'matrixOrder': value})


if __name__ == '__main__':
    unittest.main()
