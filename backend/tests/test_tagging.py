"""Run from backend/: python -m unittest tests.test_tagging (no LLM needed)"""
import time
import unittest
from unittest import mock

import httpx
import openai
from langchain_core.exceptions import OutputParserException

from services import tagging_service
from services.tagging_service import LLM_TIMEOUT_SECONDS, _run

REQUEST = httpx.Request("POST", "http://llm/v1/chat/completions")


def rate_limited(reset_in: float) -> openai.RateLimitError:
    # Shaped like OpenRouter's free-tier 429, which carries the reset time in the body
    reset_ms = str(int((time.time() + reset_in) * 1000))
    return openai.RateLimitError("429", response=httpx.Response(429, request=REQUEST),
                                 body={"metadata": {"headers": {"X-RateLimit-Reset": reset_ms}}})


class ScriptedChain:
    """Returns the scripted errors for a text, one per call, then succeeds; records each call's settings."""

    def __init__(self, script: dict):
        self.script = {t: list(errs) for t, errs in script.items()}
        self.configs = []

    def __call__(self, temperature, timeout):
        self.configs.append({"temperature": temperature, "timeout": timeout})
        return self

    def batch(self, inputs, config=None, return_exceptions=False):
        out = []
        for i in inputs:
            errs = self.script.get(i["text"])
            out.append(errs.pop(0) if errs else {"text": i["text"]})
        return out

    def batch_as_completed(self, inputs, config=None, return_exceptions=False):
        return enumerate(self.batch(inputs, config, return_exceptions))


@mock.patch.object(tagging_service.time, "sleep")
class PersistentRun(unittest.TestCase):
    def test_retries_until_every_text_succeeds(self, sleep):
        chain = ScriptedChain({"b": [openai.APIConnectionError(request=REQUEST)] * 12})
        self.assertEqual(_run(chain, ["a", "b"], persist=True), [{"text": "a"}, {"text": "b"}])
        self.assertEqual(len(chain.configs), 13)
        self.assertLessEqual(max(c.args[0] for c in sleep.call_args_list), tagging_service.MAX_BACKOFF_SECONDS)

    def test_stuck_call_gets_longer_timeout(self, sleep):
        chain = ScriptedChain({"a": [openai.APITimeoutError(request=REQUEST)] * 2})
        _run(chain, ["a"], persist=True)
        self.assertEqual([c["timeout"] for c in chain.configs],
                         [LLM_TIMEOUT_SECONDS, LLM_TIMEOUT_SECONDS * 2, LLM_TIMEOUT_SECONDS * 4])
        sleep.assert_has_calls([mock.call(0.0), mock.call(0.0)])

    def test_unparseable_output_raises_temperature_without_waiting(self, sleep):
        chain = ScriptedChain({"a": [OutputParserException("bad json")] * 2})
        _run(chain, ["a"], persist=True)
        temps = [c["temperature"] for c in chain.configs]
        self.assertEqual(temps[0], 0.0)
        self.assertLess(temps[0], temps[1])
        self.assertLess(temps[1], temps[2])
        sleep.assert_has_calls([mock.call(0.0), mock.call(0.0)])

    def test_rate_limit_waits_for_reset(self, sleep):
        chain = ScriptedChain({"a": [rate_limited(reset_in=300)]})
        _run(chain, ["a"], persist=True)
        self.assertAlmostEqual(sleep.call_args.args[0], 300, delta=5)

    def test_permanent_error_raises_instead_of_looping(self, sleep):
        auth = openai.AuthenticationError("401", response=httpx.Response(401, request=REQUEST), body=None)
        chain = ScriptedChain({"a": [auth] * 100})
        with self.assertRaises(openai.AuthenticationError):
            _run(chain, ["a"], persist=True)
        self.assertEqual(len(chain.configs), 1)

    def test_on_success_sees_each_finished_text_once_with_its_index(self, sleep):
        chain = ScriptedChain({"b": [openai.APIConnectionError(request=REQUEST)] * 2})
        on_success = mock.Mock()
        _run(chain, ["a", "b", "c"], persist=True, on_success=on_success)
        self.assertEqual(sorted(c.args for c in on_success.call_args_list),
                         [(0, {"text": "a"}), (1, {"text": "b"}), (2, {"text": "c"})])

    def test_single_shot_without_persist(self, sleep):
        chain = ScriptedChain({"a": [OutputParserException("bad json")]})
        self.assertEqual(_run(chain, ["a"]), [None])
        self.assertEqual(len(chain.configs), 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
