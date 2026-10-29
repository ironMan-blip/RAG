"""Run from backend/: python -m unittest tests.test_upload_jobs (no database needed)"""
import unittest
from unittest import mock

from services import document_service, upload_jobs
from services.upload_jobs import UploadJob


def resumed_tools_job() -> UploadJob:
    """A tools job as a restart loads it: 2 chunks, metadata and one chunk's tags already saved."""
    return UploadJob("a.pdf", "tools", chunks=[{"text": "x"}, {"text": "y"}], doc_metadata={"year": "2024"},
                     tags=[["t"] * 10, None], summaries=[None, None])


class UploadJobProgress(unittest.TestCase):
    def test_percent_unknown_until_chunks_extracted(self):
        self.assertIsNone(UploadJob("a.pdf", "library").to_dict()["percent"])

    def test_resumed_job_keeps_progress_and_times_only_new_work(self):
        job = resumed_tools_job()
        self.assertEqual(job.to_dict()["percent"], 33)  # 2 of 6 units: metadata + one chunk's tags
        with mock.patch.object(upload_jobs.time, "monotonic", side_effect=[100.0, 110.0]):
            job.begin()
            job.set_tags(1, ["t"] * 10)
            d = job.to_dict()
        self.assertEqual((d["percent"], d["eta_seconds"]), (50, 30))  # 10s per new unit, 3 units left

    def test_untracked_job_never_touches_database(self):
        job = UploadJob("a.pdf", "")
        with mock.patch.object(upload_jobs, "db_cursor") as db:
            job.set_chunks([{"text": "x"}])
            job.set_summary(0, "s")
        db.assert_not_called()


class Resume(unittest.TestCase):
    def test_only_missing_results_are_generated(self):
        job = resumed_tools_job()
        generate = mock.Mock(side_effect=lambda texts, on_result: on_result(0, ["new"] * 10))
        document_service._fill_missing(job.tags, ["x", "y"], generate, job.set_tags)
        generate.assert_called_once()
        self.assertEqual(generate.call_args.args[0], ["y"])
        self.assertEqual(job.tags[1], ["new"] * 10)

    def test_nothing_generated_when_all_saved(self):
        generate = mock.Mock()
        document_service._fill_missing(["a", "b"], ["x", "y"], generate, None)
        generate.assert_not_called()


class Registry(unittest.TestCase):
    def tearDown(self):
        upload_jobs._jobs.clear()

    @mock.patch.object(upload_jobs, "db_cursor")
    def test_finished_job_leaves_failed_job_stays_listed(self, db):
        ok, bad = UploadJob("ok.pdf", "library", id="1"), UploadJob("bad.pdf", "library", id="2")
        upload_jobs._jobs.update({"1": ok, "2": bad})
        upload_jobs.finish(ok)
        upload_jobs.finish(bad, error="boom")
        listed = {j["filename"]: j for j in upload_jobs.list_jobs()}
        self.assertNotIn("ok.pdf", listed)
        self.assertEqual(listed["bad.pdf"]["error"], "boom")


class Cancel(unittest.TestCase):
    def test_cancel_drops_job_and_stops_worker_at_next_save(self):
        job = UploadJob("a.pdf", "library", id="j1", chunks=[{"text": "x"}], tags=[None], summaries=[None])
        upload_jobs._jobs["j1"] = job
        with mock.patch.object(upload_jobs, "db_cursor"):
            self.assertTrue(upload_jobs.cancel("j1"))
            self.assertFalse(upload_jobs.cancel("j1"))
            with self.assertRaises(upload_jobs.Cancelled):
                job.set_summary(0, "s")
        self.assertNotIn("j1", upload_jobs._jobs)


class Pause(unittest.TestCase):
    def test_paused_job_stops_at_next_save_and_resumes(self):
        job = UploadJob("a.pdf", "library", id="p1", chunks=[{"text": "x"}], tags=[None], summaries=[None])
        upload_jobs._jobs["p1"] = job
        try:
            self.assertTrue(document_service.pause_upload("p1"))
            with self.assertRaises(upload_jobs.Cancelled):
                job.set_summary(0, "s")
            self.assertTrue(job.to_dict()["stopped"])
            with mock.patch.object(document_service, "_process_in_background") as start:
                self.assertIsNone(document_service.resume_upload("p1"))
            start.assert_called_once_with(job)
            self.assertFalse(job.paused)
        finally:
            upload_jobs._jobs.pop("p1", None)
