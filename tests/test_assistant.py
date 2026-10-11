import json
import os
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from actions.file_actions import FileActions
from core.command_router import CommandRouter
from voice.action_registry import PlanValidationError, requests_from_plan, validate_plan
from voice.command_parser import ActionRequest, CommandParser
from voice.gemini_interpreter import (
    DEFAULT_MODEL,
    GeminiInterpreter,
    PlannerUnavailable,
    validate_result,
)
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv


class TestNaturalLanguageParser(unittest.TestCase):
    def setUp(self):
        self.parser = CommandParser()

    def test_common_requests_and_paraphrases(self):
        cases = {
            "Search for beatboxing tutorials on Google": ("BROWSER", "SEARCH_GOOGLE"),
            "Find my resume in Documents folder": ("FILE_SYSTEM", "FIND_FILE"),
            "Open Recycle Bin": ("FILE_SYSTEM", "OPEN_RECYCLE_BIN"),
            "Increase text size": ("SYSTEM", "OPEN_ACCESSIBILITY_SETTINGS"),
            "Turn the volume down": ("SYSTEM", "VOLUME_DOWN"),
            "Explain what is happening in the application": ("SYSTEM", "EXPLAIN_STATUS"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                request = self.parser.parse(text)[0]
                self.assertEqual((request.domain, request.intent), expected)

        find_request = self.parser.parse("Find my resume in Documents folder")[0]
        self.assertEqual(find_request.params, {"query": "resume", "folder_key": "documents"})

    def test_compound_launch_and_search_is_ordered(self):
        requests = self.parser.parse(
            "Open Chrome and search for Python accessibility tools"
        )
        self.assertEqual(
            [(request.domain, request.intent) for request in requests],
            [("APPLICATION", "LAUNCH_APP"), ("BROWSER", "SEARCH_GOOGLE")],
        )
        self.assertEqual(requests[1].params["query"], "python accessibility tools")

    def test_url_and_typed_text_retain_user_content(self):
        url = self.parser.parse("Go to https://example.com/a-b?q=x")[0]
        self.assertEqual(url.params["url"], "https://example.com/a-b?q=x")

        typed = self.parser.parse("Type Hello, World!")[0]
        self.assertEqual(typed.params["text"], "Hello, World!")

    def test_existing_volume_and_unsafe_shell_requests(self):
        self.assertEqual(self.parser.parse("volume up")[0].intent, "VOLUME_UP")
        self.assertEqual(self.parser.parse("volume down")[0].intent, "VOLUME_DOWN")
        self.assertEqual(self.parser.parse("open powershell")[0].domain, "REJECT")
        self.assertEqual(
            self.parser.parse("search Google for PowerShell documentation")[0].intent,
            "SEARCH_GOOGLE",
        )


class TestCapabilityValidation(unittest.TestCase):
    def test_rejects_unknown_actions_and_malformed_parameters(self):
        with self.assertRaises(PlanValidationError):
            requests_from_plan({
                "steps": [{
                    "domain": "SYSTEM",
                    "intent": "RUN_COMMAND",
                    "params": {"command": "format c:"},
                }]
            })
        with self.assertRaises(PlanValidationError):
            validate_plan([ActionRequest("BROWSER", "SEARCH_GOOGLE", {})])
        with self.assertRaises(PlanValidationError):
            validate_plan([
                ActionRequest("BROWSER", "OPEN_URL", {"url": "javascript:alert(1)"})
            ])
        with self.assertRaises(PlanValidationError):
            validate_plan([
                ActionRequest("APPLICATION", "LAUNCH_APP", {"app_name": "powershell"})
            ])
        with self.assertRaises(PlanValidationError):
            validate_plan([
                ActionRequest("FILE_SYSTEM", "OPEN_FILE", {"filename": "payload.exe"})
            ])

    def test_optional_ai_planner_requires_explicit_configuration(self):
        with patch("voice.gemini_interpreter.load_dotenv"), patch.dict(
            os.environ, {}, clear=True
        ):
            self.assertIsNone(GeminiInterpreter.from_environment())


class TestChatbotPlanner(unittest.TestCase):
    def test_env_file_loads_values_and_preserves_process_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                'AIRCONTROL_AI_API_KEY="test-key"\n'
                "AIRCONTROL_AI_MODEL=test-model\n"
                "IGNORED_SETTING=not-loaded\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"AIRCONTROL_AI_MODEL": "process-model"}, clear=True):
                load_dotenv(dotenv_path=env_path, override=False)
                self.assertEqual(os.environ["AIRCONTROL_AI_API_KEY"], "test-key")
                self.assertEqual(os.environ["AIRCONTROL_AI_MODEL"], "process-model")
                self.assertEqual(os.environ["IGNORED_SETTING"], "not-loaded")

    def test_response_supports_answers_and_validated_registered_actions(self):
        action, answer = validate_result({
            "kind": "answer",
            "action_name": None,
            "params": {},
            "answer": "AirControl supports pinch-to-left-click.",
        })
        self.assertIsNone(action)
        self.assertEqual(answer, "AirControl supports pinch-to-left-click.")

        action, answer = validate_result({
            "kind": "action",
            "action_name": "BROWSER.SEARCH_YOUTUBE",
            "params": {"query": "beginner beatboxing tutorials"},
            "answer": None,
        })
        self.assertEqual(action.intent, "SEARCH_YOUTUBE")
        self.assertEqual(action.params["query"], "beginner beatboxing tutorials")
        self.assertEqual(answer, "")

        with self.assertRaises(PlanValidationError):
            validate_result({
                "kind": "action",
                "action_name": "SYSTEM.RUN_COMMAND",
                "params": {"command": "whoami"},
                "answer": None,
            })
        with self.assertRaises(PlanValidationError):
            validate_result({
                "kind": "answer",
                "action_name": None,
                "params": {"query": "unexpected"},
                "answer": "Answer only.",
            })

    def test_gemini_client_uses_default_model_schema_and_history(self):
        client = MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps({
                "kind": "answer",
                "action_name": None,
                "params": {},
                "answer": "A pinch clicks the mouse.",
            })
        )
        planner = GeminiInterpreter("fake-test-key", client=client)
        history = [
            {"role": "user", "content": "How do I click?"},
            {"role": "assistant", "content": "Use the pinch gesture."},
        ]
        action, answer, confident = planner.interpret(
            "What did you mean?", history=history
        )
        call = client.models.generate_content.call_args.kwargs
        self.assertEqual(call["model"], DEFAULT_MODEL)
        self.assertTrue(confident)
        self.assertIsNone(action)
        self.assertEqual(answer, "A pinch clicks the mouse.")
        self.assertEqual(
            [item["role"] for item in call["contents"]],
            ["user", "assistant", "user"],
        )
        schema = call["config"].response_schema
        string_schema = next(
            item
            for item in schema["properties"]["action_name"]["anyOf"]
            if item.get("type") == "string"
        )
        self.assertIn("BROWSER.SEARCH_GOOGLE", string_schema["enum"])

    def test_none_result_is_not_confident(self):
        client = MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps({
                "kind": "none",
                "action_name": None,
                "params": {},
                "answer": None,
            })
        )
        action, answer, confident = GeminiInterpreter(
            "fake-test-key", client=client
        ).interpret("Something unsupported")
        self.assertIsNone(action)
        self.assertEqual(answer, "")
        self.assertFalse(confident)

    def test_environment_uses_requested_default_model_and_timeout(self):
        with patch("voice.gemini_interpreter.load_dotenv"), patch.dict(
            os.environ, {"AIRCONTROL_AI_API_KEY": "fake-test-key"}, clear=True
        ), patch("voice.gemini_interpreter.genai.Client") as client_factory:
            planner = GeminiInterpreter.from_environment()
        self.assertEqual(planner.model, DEFAULT_MODEL)
        self.assertEqual(planner.timeout_seconds, 12)
        self.assertEqual(
            client_factory.call_args.kwargs["http_options"].timeout, 12000
        )

    def test_malformed_json_is_rejected(self):
        client = MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(
            text='{"kind":"action", bad json'
        )
        with self.assertRaisesRegex(PlannerUnavailable, "invalid response"):
            GeminiInterpreter("fake-test-key", client=client).interpret("unknown")

    def test_rate_limit_and_model_not_found_do_not_change_configured_model(self):
        class RateLimitError(Exception):
            code = 429

        class ModelNotFoundError(Exception):
            code = 404

        client = MagicMock()
        planner = GeminiInterpreter("fake-test-key", client=client)
        client.models.generate_content.side_effect = RateLimitError()
        with self.assertRaisesRegex(PlannerUnavailable, "rate-limited"):
            planner.interpret("Could you make it louder?")

        client.models.generate_content.side_effect = ModelNotFoundError()
        client.models.list.return_value = [
            SimpleNamespace(name="models/gemini-3.5-flash-lite"),
            SimpleNamespace(name="models/gemini-other"),
        ]
        with self.assertRaisesRegex(PlannerUnavailable, "Models currently listed"):
            planner.interpret("Could you make it louder?")
        self.assertEqual(
            client.models.generate_content.call_args.kwargs["model"], DEFAULT_MODEL
        )
        client.models.list.assert_called_once()

    def test_timeout_and_quota_errors_are_user_friendly(self):
        client = MagicMock()
        planner = GeminiInterpreter("fake-test-key", client=client)
        client.models.generate_content.side_effect = TimeoutError()
        with self.assertRaisesRegex(PlannerUnavailable, "before the timeout"):
            planner.interpret("Explain screen readers")

        class QuotaError(Exception):
            code = 429
            message = "quota exceeded"

        client.models.generate_content.side_effect = QuotaError()
        with self.assertRaisesRegex(PlannerUnavailable, "quota is exhausted"):
            planner.interpret("Explain screen readers")

    def test_valid_action_with_markdown_fences(self):
        client = MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(
            text='```json\n{"kind": "action", "action_name": "SYSTEM.VOLUME_UP", "params": {}, "answer": null}\n```'
        )
        planner = GeminiInterpreter("fake-test-key", client=client)
        action, answer, confident = planner.interpret("make it louder")
        self.assertIsNotNone(action)
        self.assertEqual(action.domain, "SYSTEM")
        self.assertEqual(action.intent, "VOLUME_UP")
        self.assertEqual(answer, "")
        self.assertTrue(confident)

    def test_valid_action_with_generic_markdown_fences_and_whitespace(self):
        client = MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(
            text='   \n\n```\n{"kind": "action", "action_name": "WINDOW.MINIMIZE", "params": {}, "answer": null}\n```\n\n  '
        )
        planner = GeminiInterpreter("fake-test-key", client=client)
        action, answer, confident = planner.interpret("minimize window")
        self.assertIsNotNone(action)
        self.assertEqual(action.domain, "WINDOW")
        self.assertEqual(action.intent, "MINIMIZE")
        self.assertTrue(confident)

    def test_response_parsed_attribute_supported(self):
        client = MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(
            parsed={
                "kind": "action",
                "action_name": "SYSTEM.MUTE",
                "params": {},
                "answer": None,
            },
            text=None,
        )
        planner = GeminiInterpreter("fake-test-key", client=client)
        action, answer, confident = planner.interpret("mute audio")
        self.assertIsNotNone(action)
        self.assertEqual(action.domain, "SYSTEM")
        self.assertEqual(action.intent, "MUTE")
        self.assertTrue(confident)

    def test_empty_or_missing_response_content(self):
        client = MagicMock()
        planner = GeminiInterpreter("fake-test-key", client=client)

        client.models.generate_content.return_value = SimpleNamespace(text="")
        with self.assertRaisesRegex(PlannerUnavailable, "empty response"):
            planner.interpret("hello")

        client.models.generate_content.return_value = SimpleNamespace(text="   \n  ")
        with self.assertRaisesRegex(PlannerUnavailable, "empty response"):
            planner.interpret("hello")

        client.models.generate_content.return_value = SimpleNamespace(text=None, candidates=[])
        with self.assertRaisesRegex(PlannerUnavailable, "empty response"):
            planner.interpret("hello")

    def test_candidate_parts_fallback_text(self):
        client = MagicMock()
        candidate = SimpleNamespace(
            finish_reason=None,
            content=SimpleNamespace(
                parts=[
                    SimpleNamespace(text='{"kind": "answer", "action_name": null, "params": {}, "answer": "Hello from parts!"}')
                ]
            ),
        )
        client.models.generate_content.return_value = SimpleNamespace(
            text=None,
            candidates=[candidate],
        )
        planner = GeminiInterpreter("fake-test-key", client=client)
        action, answer, confident = planner.interpret("say hello")
        self.assertIsNone(action)
        self.assertEqual(answer, "Hello from parts!")
        self.assertTrue(confident)

    def test_blocked_by_safety_filter(self):
        client = MagicMock()
        candidate = SimpleNamespace(finish_reason="SAFETY")
        client.models.generate_content.return_value = SimpleNamespace(
            candidates=[candidate], text=None
        )
        planner = GeminiInterpreter("fake-test-key", client=client)
        with self.assertRaisesRegex(PlannerUnavailable, "blocked by safety"):
            planner.interpret("something risky")

    def test_token_limit_exceeded(self):
        client = MagicMock()
        candidate = SimpleNamespace(finish_reason="MAX_TOKENS")
        client.models.generate_content.return_value = SimpleNamespace(
            candidates=[candidate], text=None
        )
        planner = GeminiInterpreter("fake-test-key", client=client)
        with self.assertRaisesRegex(PlannerUnavailable, "token limit"):
            planner.interpret("tell me an extremely long story")

    def test_prompt_feedback_blocked(self):
        client = MagicMock()
        client.models.generate_content.return_value = SimpleNamespace(
            prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
            candidates=[],
            text=None,
        )
        planner = GeminiInterpreter("fake-test-key", client=client)
        with self.assertRaisesRegex(PlannerUnavailable, "blocked"):
            planner.interpret("something blocked")

    def test_missing_api_key_raises_planner_unavailable(self):
        with self.assertRaisesRegex(PlannerUnavailable, "not configured"):
            GeminiInterpreter("")

    def test_unknown_action_and_invalid_parameters_rejected(self):
        client = MagicMock()
        planner = GeminiInterpreter("fake-test-key", client=client)

        client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps({
                "kind": "action",
                "action_name": "MALICIOUS.FORMAT_HARD_DRIVE",
                "params": {},
                "answer": None,
            })
        )
        with self.assertRaisesRegex(PlannerUnavailable, "invalid response"):
            planner.interpret("format hard drive")

        # Missing required parameter for BROWSER.SEARCH_GOOGLE
        client.models.generate_content.return_value = SimpleNamespace(
            text=json.dumps({
                "kind": "action",
                "action_name": "BROWSER.SEARCH_GOOGLE",
                "params": {},
                "answer": None,
            })
        )
        with self.assertRaisesRegex(PlannerUnavailable, "invalid response"):
            planner.interpret("search google")

    def test_local_commands_succeed_even_when_gemini_fails(self):
        failing_client = MagicMock()
        failing_client.models.generate_content.side_effect = RuntimeError("Network down")
        failing_planner = GeminiInterpreter("fake-test-key", client=failing_client)

        router = CommandRouter(ai_planner=failing_planner)
        with patch.object(
            router.system_actions,
            "volume_up",
            return_value=(True, "Action: Volume Up", "Volume Up"),
        ) as volume_up, patch.object(
            router.system_actions,
            "mute",
            return_value=(True, "Action: Mute", "Mute"),
        ) as mute:
            success, msg, label = router.execute("volume up")
            self.assertTrue(success)
            self.assertEqual(label, "Volume Up")
            volume_up.assert_called_once()

            success, msg, label = router.execute("mute")
            self.assertTrue(success)
            self.assertEqual(label, "Mute")
            mute.assert_called_once()
        # Ensure Gemini was never even called for deterministic commands
        failing_client.models.generate_content.assert_not_called()

    def legacy_planner_sends_auth_and_bounded_history(self):
        payload = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "answer": "A pinch clicks the mouse.",
                        "steps": [],
                    })
                }
            }]
        }

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _limit):
                return json.dumps(payload).encode("utf-8")

        # pyrefly: ignore [unknown-name]
        planner = OpenAICompatiblePlanner(
            "https://api.example.com/v1/chat/completions", "secret-test-key", "gemini-3.5-flash-lite"
        )
        history = [
            {"role": "user", "content": "How do I click?"},
            {"role": "assistant", "content": "Use the pinch gesture."},
        ]
        with patch("voice.ai_planner.urlopen", return_value=Response()) as urlopen:
            result = planner.interpret("What did you mean?", history=history)

        request = urlopen.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-test-key")
        self.assertEqual([item["role"] for item in body["messages"][-3:]], [
            "user", "assistant", "user"
        ])
        self.assertEqual(result.answer, "A pinch clicks the mouse.")
        self.assertEqual(result.requests, [])


class TestAssistantExecution(unittest.TestCase):
    def setUp(self):
        self.context = SimpleNamespace(
            status_queue=queue.Queue(),
            assistant_queue=queue.Queue(),
            task_cancel_event=threading.Event(),
            paused=False,
        )
        self.router = CommandRouter(
            app_context=self.context,
            process_runner=MagicMock(),
            ai_planner=None,
        )

    def test_invalid_later_step_prevents_all_execution(self):
        with patch.object(self.router.system_actions, "volume_up") as volume_up:
            success, message, _ = self.router.execute(
                "volume up and open terminal", app=self.context
            )
        self.assertFalse(success)
        self.assertIn("blocked by safety policy", message)
        volume_up.assert_not_called()

    def test_cancellation_stops_before_next_step(self):
        volume_down = MagicMock(return_value=(True, "Action: Volume Down", "Volume Down"))

        def raise_volume_and_cancel():
            self.context.task_cancel_event.set()
            return True, "Action: Volume Up", "Volume Up"

        with patch.object(
            self.router.system_actions, "volume_up", side_effect=raise_volume_and_cancel
        ), patch.object(self.router.system_actions, "volume_down", volume_down):
            success, message, _ = self.router.execute(
                "volume up and volume down", app=self.context
            )
        self.assertFalse(success)
        self.assertIn("cancelled", message.lower())
        volume_down.assert_not_called()

    def test_confirmation_denial_prevents_workstation_lock(self):
        router = CommandRouter(
            app_context=self.context,
            process_runner=MagicMock(),
            confirmation_fn=lambda prompt: False,
            ai_planner=None,
        )
        with patch.object(router.system_actions, "lock_workstation") as lock:
            success, message, _ = router.execute("lock my pc", app=self.context)
        self.assertFalse(success)
        self.assertIn("not confirmed", message)
        lock.assert_not_called()

    def test_ai_proposed_unregistered_action_is_never_executed(self):
        planner = MagicMock()
        planner.plan.return_value = [
            ActionRequest("SYSTEM", "RUN_COMMAND", {"command": "whoami"})
        ]
        router = CommandRouter(
            app_context=self.context, ai_planner=planner, process_runner=MagicMock()
        )
        success, message, _ = router.execute("do an unsupported thing", app=self.context)
        self.assertFalse(success)
        self.assertIn("No actions were executed", message)
        planner.plan.assert_called_once()

    def test_ai_knowledge_answer_does_not_trigger_a_desktop_action(self):
        planner = GeminiInterpreter("fake-test-key", client=MagicMock())
        router = CommandRouter(
            app_context=self.context, ai_planner=planner, process_runner=MagicMock()
        )
        with patch.object(
            planner,
            "interpret",
            return_value=(
                None,
                "Bluetooth devices pair through Windows Settings.",
                True,
            ),
        ) as interpret, patch.object(router.system_actions, "volume_up") as volume_up, patch.object(
            router.browser, "search_google"
        ) as search:
            success, message, label = router.execute(
                "How does Bluetooth pairing work?", app=self.context
            )

        self.assertTrue(success)
        self.assertEqual(label, "Assistant Answer")
        self.assertIn("Bluetooth", message)
        interpret.assert_called_once()
        volume_up.assert_not_called()
        search.assert_not_called()

    def test_ai_action_response_uses_registered_action_handler(self):
        planner = GeminiInterpreter("fake-test-key", client=MagicMock())
        router = CommandRouter(
            app_context=self.context, ai_planner=planner, process_runner=MagicMock()
        )
        action = ActionRequest("SYSTEM", "VOLUME_UP")
        with patch.object(
            planner,
            "interpret",
            return_value=(action, "I will raise the volume.", True),
        ), patch.object(
            router.system_actions,
            "volume_up",
            return_value=(True, "Action: Volume Up", "Volume Up"),
        ) as volume_up:
            success, message, label = router.execute(
                "Could you make it louder?", app=self.context
            )

        self.assertTrue(success)
        self.assertEqual(label, "Volume Up")
        self.assertIn("Action: Volume Up", message)
        volume_up.assert_called_once()

    def test_offline_voice_mode_disables_cloud_ai_calls(self):
        self.context.voice_mode = "offline"
        planner = GeminiInterpreter("fake-test-key", client=MagicMock())
        router = CommandRouter(
            app_context=self.context, ai_planner=planner, process_runner=MagicMock()
        )
        with patch.object(planner, "interpret") as interpret:
            success, message, _ = router.execute(
                "How does Bluetooth pairing work?", app=self.context
            )

        self.assertFalse(success)
        self.assertIn("disabled in Offline voice mode", message)
        interpret.assert_not_called()

    def test_local_capability_question_uses_live_registry(self):
        router = CommandRouter(
            app_context=self.context, process_runner=MagicMock(), ai_planner=None
        )
        success, message, label = router.execute("What voice commands are supported?")
        self.assertTrue(success)
        self.assertEqual(label, "Assistant Answer")
        self.assertIn("Search Google", message)
        success, message, _ = router.execute("What gestures are supported?")
        self.assertTrue(success)
        self.assertIn("pinch click", message.lower())
        success, message, _ = router.execute(
            "What gesture do I use for right click?"
        )
        self.assertTrue(success)
        self.assertIn("not implemented", message)
        self.assertIn("say 'right click'", message.lower())

    def test_offline_search_and_volume_alias_remain_available(self):
        with patch.object(
            self.router.browser,
            "search_google",
            return_value=(True, "Action: Search Google for 'tutorials'", "Search Google"),
        ) as search, patch.object(
            self.router.system_actions,
            "volume_up",
            return_value=(True, "Action: Volume Up", "Volume Up"),
        ) as volume_up:
            search_result = self.router.execute(
                "search for tutorials on Google", app=self.context
            )
            volume_result = self.router.execute(
                "turn the volume up", app=self.context
            )
        self.assertTrue(search_result[0])
        self.assertTrue(volume_result[0])
        search.assert_called_once_with("tutorials")
        volume_up.assert_called_once()


class TestBoundedFileSearch(unittest.TestCase):
    def test_search_is_limited_to_selected_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "resume-2026.pdf").write_text("fixture", encoding="utf-8")
            with patch(
                "actions.file_actions.KNOWN_FOLDERS",
                {
                    "documents": root,
                    "downloads": root / "downloads",
                    "desktop": root / "desktop",
                    "pictures": root / "pictures",
                    "screenshots": root / "screenshots",
                    "project": root / "project",
                },
            ):
                success, message, _ = FileActions(opener_fn=MagicMock()).find_file("resume")
            self.assertTrue(success)
            self.assertIn("resume-2026.pdf", message)

    def test_search_honors_cancellation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cancel_event = threading.Event()
            cancel_event.set()
            with patch(
                "actions.file_actions.KNOWN_FOLDERS",
                {
                    "documents": root,
                    "downloads": root,
                    "desktop": root,
                    "pictures": root,
                    "screenshots": root,
                    "project": root,
                },
            ):
                success, message, _ = FileActions().find_file(
                    "resume", cancel_event=cancel_event
                )
            self.assertFalse(success)
            self.assertIn("cancelled", message.lower())


if __name__ == "__main__":
    unittest.main()
