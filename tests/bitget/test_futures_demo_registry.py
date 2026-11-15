"""Real private registry/lease/crash checks; synthetic identity, no broker calls."""
from dataclasses import replace
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Barrier, Event, Thread
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_bitget.futures_demo import DemoRejected, digest
from investalo_bitget.futures_demo_outbox import DemoOutbox, encode
from investalo_bitget.futures_demo_registry import RegisteredDemoOutbox, _Registry, _key
from test_futures_demo import AT, OWNER, OTHER, BINDING, intent
from test_futures_demo_account import cohort, expectation

BOX = UUID(int=123)


class DemoRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry, self.directory = self.private("registry"), self.private("original")
        self.box = RegisteredDemoOutbox.create(self.registry, self.directory,
            binding=BINDING, outbox_id=BOX, context=OWNER)

    def tearDown(self):
        self.box.close()
        self.tmp.cleanup()

    def private(self, name):
        path = self.root / name
        path.mkdir(mode=0o700)
        return path

    def restore(self, **kwargs):
        self.box.close()
        self.box = RegisteredDemoOutbox.restore(self.registry, self.directory,
            binding=BINDING, outbox_id=BOX, context=OWNER, **kwargs)
        return self.box

    def claim(self, binding=BINDING):
        return self.registry / ("account-" + _key(binding) + ".json")

    def test_private_original_registration_and_no_execution_claim(self):
        for path in self.registry.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.stat().st_nlink, 1)
        original = self.claim().read_bytes()
        receipt = self.box.receipt
        self.restore(minimum_receipt=receipt)
        self.assertEqual(self.box.receipt, receipt)
        self.assertEqual(self.claim().read_bytes(), original)
        self.assertNotIn("broker_uid", repr(self.box))

    def test_same_broker_uid_cannot_create_second_path_with_new_key_or_owner(self):
        alternate = self.private("alternate")
        for binding in (BINDING, replace(BINDING, credential_ref=UUID(int=901)),
                        replace(BINDING, account_id=UUID(int=902)),
                        replace(BINDING, owner=OTHER)):
            with self.subTest(binding=binding), self.assertRaisesRegex(DemoRejected, "binding_conflict"):
                RegisteredDemoOutbox.create(self.registry, alternate,
                    binding=binding, outbox_id=UUID(int=903), context=binding.owner)
        self.assertEqual(list(alternate.iterdir()), [])
        self.assertEqual(self.box.receipt.revision, 0)

    def test_closed_original_still_blocks_rebinding_and_create_reset(self):
        self.box.close()
        with self.assertRaisesRegex(DemoRejected, "already_registered"):
            RegisteredDemoOutbox.create(self.registry, self.directory,
                binding=BINDING, outbox_id=BOX, context=OWNER)
        with self.assertRaisesRegex(DemoRejected, "binding_conflict"):
            RegisteredDemoOutbox.restore(self.registry, self.directory,
                binding=replace(BINDING, credential_ref=UUID(int=904)), outbox_id=BOX, context=OWNER)
        self.restore()

    def test_distinct_account_can_run_concurrently_but_shared_resources_reject(self):
        binding = replace(BINDING, broker_uid="987654", account_id=UUID(int=905))
        alternative = self.private("other")
        with RegisteredDemoOutbox.create(self.registry, alternative,
                binding=binding, outbox_id=UUID(int=906), context=OWNER) as peer:
            self.assertEqual(peer.receipt.revision, 0)
            self.box.prepare(intent(), context=OWNER, expected_revision=0)
            self.assertEqual(peer.receipt.revision, 0)
        for index, (changed, directory, box_id) in enumerate((
                (replace(binding, account_id=BINDING.account_id), alternative, UUID(int=907)),
                (binding, self.directory, UUID(int=907)), (binding, alternative, BOX))):
            changed = replace(changed, broker_uid=str(900000 + index),
                              account_id=changed.account_id if index == 0 else UUID(int=930 + index))
            with self.subTest(directory=directory), self.assertRaises(DemoRejected):
                RegisteredDemoOutbox.create(self.registry, directory,
                    binding=changed, outbox_id=box_id, context=OWNER)

    def test_unregistered_existing_outbox_is_not_adopted(self):
        other = self.private("unregistered")
        binding = replace(BINDING, broker_uid="876543", account_id=UUID(int=908))
        with DemoOutbox.create(other, binding=binding, outbox_id=UUID(int=909), context=OWNER):
            pass
        for create in (True, False):
            method = RegisteredDemoOutbox.create if create else RegisteredDemoOutbox.restore
            with self.subTest(create=create), self.assertRaises(DemoRejected):
                method(self.registry, other, binding=binding, outbox_id=UUID(int=909), context=OWNER)
        self.assertFalse(self.claim(binding).exists())

    def test_actual_account_lease_rejects_second_writer_then_releases(self):
        with self.assertRaisesRegex(DemoRejected, "account_writer_busy"):
            RegisteredDemoOutbox.restore(self.registry, self.directory,
                binding=BINDING, outbox_id=BOX, context=OWNER)
        self.restore()
        self.assertEqual(self.box.receipt.revision, 0)

    def test_global_catalog_busy_prevents_outbox_append_without_poison(self):
        lock = os.open(self.registry / "registry.lock", os.O_RDWR)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(DemoRejected, "registry_busy"):
                self.box.prepare(intent(), context=OWNER, expected_revision=0)
        finally:
            os.close(lock)
        self.assertEqual(self.box.receipt.revision, 0)
        self.box.prepare(intent(), context=OWNER, expected_revision=0)

    def test_cas_owner_conflicts_leave_registration_and_session_reusable(self):
        original = self.claim().read_bytes()
        for context, revision in ((OTHER, 0), (OWNER, 1), (OWNER, True)):
            with self.subTest(context=context), self.assertRaises(DemoRejected):
                self.box.prepare(intent(), context=context, expected_revision=revision)
        self.box.prepare(intent(), context=OWNER, expected_revision=0)
        self.assertEqual(self.claim().read_bytes(), original)
        self.assertEqual(self.restore().receipt.revision, 1)

    def test_unknown_attempt_restores_under_original_minimum_without_resend(self):
        order = intent()
        self.box.prepare(order, context=OWNER, expected_revision=0)
        with patch.object(self.box._box, "_publish", side_effect=OSError("synthetic")):
            with self.assertRaisesRegex(DemoRejected, "write_unknown"):
                self.box.begin_attempt(order.command_id, context=OWNER, expected_revision=1, at_ms=AT)
        self.restore()
        self.assertEqual(self.box.receipt.revision, 2)
        self.assertFalse(self.box.traces(context=OWNER)[0].can_submit)
        with self.assertRaisesRegex(DemoRejected, "resend_denied"):
            self.box.begin_attempt(order.command_id, context=OWNER, expected_revision=2, at_ms=AT + 1)

    def test_claim_survives_genesis_failure_and_cannot_reset(self):
        binding = replace(BINDING, broker_uid="765432", account_id=UUID(int=910))
        other = self.private("failed")
        with patch.object(DemoOutbox, "create", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                RegisteredDemoOutbox.create(self.registry, other,
                    binding=binding, outbox_id=UUID(int=911), context=OWNER)
        original = self.claim(binding).read_bytes()
        with self.assertRaisesRegex(DemoRejected, "already_registered"):
            RegisteredDemoOutbox.create(self.registry, other,
                binding=binding, outbox_id=UUID(int=911), context=OWNER)
        with self.assertRaises(FileNotFoundError):
            RegisteredDemoOutbox.restore(self.registry, other,
                binding=binding, outbox_id=UUID(int=911), context=OWNER)
        self.assertEqual(self.claim(binding).read_bytes(), original)

    def test_claim_fsync_unknown_retains_record_never_creates_journal(self):
        binding = replace(BINDING, broker_uid="654321", account_id=UUID(int=912))
        other = self.private("fsync-failed")
        claim = _Registry.claim

        def fail(registry, record):
            with patch("investalo_bitget.futures_demo_registry.os.fsync", side_effect=OSError("synthetic")):
                return claim(registry, record)
        with patch.object(_Registry, "claim", fail):
            with self.assertRaisesRegex(DemoRejected, "registry_write_unknown"):
                RegisteredDemoOutbox.create(self.registry, other,
                    binding=binding, outbox_id=UUID(int=913), context=OWNER)
        self.assertTrue(self.claim(binding).is_file())
        self.assertEqual(list(other.iterdir()), [])
        with self.assertRaisesRegex(DemoRejected, "already_registered"):
            RegisteredDemoOutbox.create(self.registry, other,
                binding=binding, outbox_id=UUID(int=913), context=OWNER)

    def test_missing_or_changed_claim_latches_stop_even_after_repair(self):
        original = self.claim().read_bytes()
        self.claim().write_bytes(b"{}\n")
        with self.assertRaises(DemoRejected):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)
        self.claim().write_bytes(original)
        with self.assertRaisesRegex(DemoRejected, "stopped"):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)
        self.restore()
        self.assertEqual(self.box.receipt.revision, 0)

    def test_renamed_original_directory_rejects_replacement_inode(self):
        self.directory.rename(self.root / "preserved")
        self.directory.mkdir(mode=0o700)
        with self.assertRaisesRegex(DemoRejected, "directory_replaced"):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_registry_root_or_lock_replacement_stops_writer(self):
        lock = self.registry / "registry.lock"
        lock.rename(self.registry / "preserved.lock")
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with self.assertRaisesRegex(DemoRejected, "file_replaced"):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)
        self.assertEqual(len((self.directory / "commands.jsonl").read_bytes().splitlines()), 1)

    def test_registry_root_replacement_does_not_follow_preserved_descriptor(self):
        self.registry.rename(self.root / "preserved-registry")
        self.registry.mkdir(mode=0o700)
        with self.assertRaisesRegex(DemoRejected, "root_replaced"):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)
        self.assertEqual(list(self.registry.iterdir()), [])

    def test_missing_original_global_and_account_locks_are_not_recreated(self):
        self.box.close()
        lease = self.registry / ("account-" + _key(BINDING) + ".lock")
        lease.rename(self.root / "preserved-lease")
        with self.assertRaises(FileNotFoundError):
            self.restore()
        self.assertFalse(lease.exists())
        (self.registry / "registry.lock").unlink()
        with self.assertRaisesRegex(DemoRejected, "original_registry_lock_missing"):
            self.restore()
        self.assertFalse((self.registry / "registry.lock").exists())

    def test_changed_account_lease_stops_before_append(self):
        lease = self.registry / ("account-" + _key(BINDING) + ".lock")
        lease.rename(self.root / "preserved-lease")
        fd = os.open(lease, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        with self.assertRaisesRegex(DemoRejected, "file_replaced"):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)

    def test_valid_but_foreign_registration_hash_cannot_rebind_active_session(self):
        import json
        raw = json.loads(self.claim().read_bytes())
        raw["outbox_id"] = str(UUID(int=999))
        raw["head"] = digest({key: value for key, value in raw.items() if key != "head"})
        self.claim().write_bytes(encode(raw))
        with self.assertRaisesRegex(DemoRejected, "registration_changed"):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)

    def test_foreign_minimum_receipt_rejects_full_restore(self):
        minimum = replace(self.box.receipt, outbox_id=str(UUID(int=999)))
        with self.assertRaisesRegex(DemoRejected, "foreign_minimum_receipt"):
            self.restore(minimum_receipt=minimum)
        self.restore()
        self.assertEqual(self.box.receipt.revision, 0)

    def test_registered_accountcheck_has_same_receipt_and_no_new_revision(self):
        before = self.box.receipt
        report = self.box.check_account(expectation(), cohort(), context=OWNER,
            expected_revision=0, now_ms=AT + 100)
        self.assertTrue(report.matched)
        self.assertFalse(report.execution_ready)
        self.assertEqual(report.receipt, before)
        self.assertEqual(self.box.receipt, before)
        self.restore(minimum_receipt=before)
        self.assertEqual(self.box.check_account(expectation(), cohort(), context=OWNER,
            expected_revision=0, now_ms=AT + 100), report)

    def test_capacity_invalid_before_any_claim_and_unknown_registry_files_reject(self):
        other = self.private("capacity")
        binding = replace(BINDING, broker_uid="432109", account_id=UUID(int=940))
        for capacity in (True, 0, 10001):
            with self.subTest(capacity=capacity), self.assertRaisesRegex(DemoRejected, "capacity"):
                RegisteredDemoOutbox.create(self.registry, other, binding=binding,
                    outbox_id=UUID(int=941), context=OWNER, capacity=capacity)
        self.assertFalse(self.claim(binding).exists())
        (self.registry / "unexpected.tmp").touch(mode=0o600)
        with self.assertRaisesRegex(DemoRejected, "unknown_registry_file"):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)

    def test_unknown_partial_registry_record_blocks_every_account(self):
        (self.registry / ("account-" + "a" * 64 + ".json")).write_bytes(b'{"schema":')
        os.chmod(self.registry / ("account-" + "a" * 64 + ".json"), 0o600)
        with self.assertRaises(DemoRejected):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)

    def test_fifo_claim_rejects_without_blocking_or_outbox_write(self):
        self.claim().unlink()
        os.mkfifo(self.claim(), mode=0o600)
        with self.assertRaisesRegex(DemoRejected, "private_regular_file_required"):
            self.box.prepare(intent(), context=OWNER, expected_revision=0)
        self.assertEqual(len((self.directory / "commands.jsonl").read_bytes().splitlines()), 1)

    def test_symlink_hardlink_and_broad_claim_permissions_reject(self):
        original = self.claim().read_bytes()
        target = self.root / "claim-copy"
        target.write_bytes(original)
        os.chmod(target, 0o600)
        self.claim().unlink()
        self.claim().symlink_to(target)
        with self.assertRaises((DemoRejected, OSError)):
            self.restore()
        self.claim().unlink()
        os.link(target, self.claim())
        with self.assertRaisesRegex(DemoRejected, "private_regular"):
            self.restore()
        self.claim().unlink()
        self.claim().write_bytes(original)
        os.chmod(self.claim(), 0o644)
        with self.assertRaisesRegex(DemoRejected, "private_regular"):
            self.restore()

    def test_symlink_ancestor_and_nonprivate_roots_reject(self):
        link = self.root / "alias"
        link.symlink_to(self.registry, target_is_directory=True)
        for root in (link, Path("relative"), self.root / ".." / self.root.name / "registry"):
            with self.subTest(root=root), self.assertRaises((DemoRejected, OSError)):
                RegisteredDemoOutbox.restore(root, self.directory,
                    binding=BINDING, outbox_id=BOX, context=OWNER)
        os.chmod(self.registry, 0o755)
        with self.assertRaisesRegex(DemoRejected, "private_directory"):
            self.restore()

    def test_concurrent_same_uid_claim_has_one_original_winner(self):
        binding = replace(BINDING, broker_uid="543210", account_id=UUID(int=914))
        first, second = self.private("first"), self.private("second")
        barrier, results = Barrier(3), []

        def create(path):
            barrier.wait()
            try:
                with RegisteredDemoOutbox.create(self.registry, path,
                        binding=binding, outbox_id=UUID(int=915), context=OWNER):
                    results.append(("created", path))
            except DemoRejected:
                results.append(("rejected", path))
        threads = [Thread(target=create, args=(path,)) for path in (first, second)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        self.assertCountEqual([status for status, _ in results], ["created", "rejected"])
        loser = next(path for status, path in results if status == "rejected")
        self.assertEqual(list(loser.iterdir()), [])

    def test_actual_child_exit_releases_lease_and_restores_unknown(self):
        self.box.close()
        script = """
import os,sys
from uuid import UUID
from investalo_bitget.futures_demo_registry import RegisteredDemoOutbox
from test_futures_demo import AT,OWNER,BINDING,intent
box=RegisteredDemoOutbox.restore(sys.argv[1],sys.argv[2],binding=BINDING,outbox_id=UUID(int=123),context=OWNER)
order=intent()
box.prepare(order,context=OWNER,expected_revision=0)
box.begin_attempt(order.command_id,context=OWNER,expected_revision=1,at_ms=AT)
os._exit(23)
"""
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((
            str(Path(__file__).resolve().parents[2] / "integrations/bitget/src"),
            str(Path(__file__).resolve().parent))), PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-c", script, str(self.registry), str(self.directory)],
                                env=env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 23, result.stderr.decode())
        self.restore()
        self.assertEqual(self.box.receipt.revision, 2)
        self.assertEqual(self.box.traces(context=OWNER)[0].state, "submission_unknown")

    def test_inherited_session_refuses_fork_use(self):
        if not hasattr(os, "fork"):
            self.skipTest("POSIX fork required")
        pid = os.fork()
        if pid == 0:
            try:
                self.box.prepare(intent(), context=OWNER, expected_revision=0)
            except DemoRejected:
                os._exit(0)
            os._exit(1)
        _, status = os.waitpid(pid, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        self.assertEqual(self.box.receipt.revision, 0)

    def test_fork_rejection_does_not_wait_on_parent_thread_mutex(self):
        if not hasattr(os, "fork"):
            self.skipTest("POSIX fork required")
        import signal
        held, release = Event(), Event()

        def hold():
            with self.box._mutex:
                held.set()
                release.wait(timeout=5)
        thread = Thread(target=hold)
        thread.start()
        self.assertTrue(held.wait(timeout=2))
        try:
            import warnings
            with warnings.catch_warnings():
                # This regression deliberately forks while a parent mutex is held.
                warnings.filterwarnings("ignore", message="This process .* is multi-threaded",
                                        category=DeprecationWarning)
                pid = os.fork()
            if pid == 0:
                signal.alarm(2)
                try:
                    self.box.prepare(intent(), context=OWNER, expected_revision=0)
                except DemoRejected:
                    os._exit(0)
                os._exit(1)
            _, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        finally:
            release.set()
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
