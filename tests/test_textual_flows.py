from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

try:
    from textual.css.query import NoMatches
    from textual.widgets import Button, Input, TabbedContent
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional UI deps in base env
    raise unittest.SkipTest("textual nao esta instalado neste ambiente") from exc

from fh_admin_tui.diagnostics import configure_logging
from fh_admin_tui.mutations import get_actor
from fh_admin_tui.textual_app import FearHungerTextualApp
from fh_admin_tui.ui.screens import ChoiceScreen, ReviewScreen, TextInputScreen
from tests.fixtures.helpers import build_fake_repository, build_test_catalog


class TextualFlowTests(unittest.IsolatedAsyncioTestCase):
    async def _wait_until(self, predicate, timeout: float = 5.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while not predicate():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail("Timeout aguardando estado da interface")
            await asyncio.sleep(0.05)

    def _review_confirm_ready(self, app: FearHungerTextualApp) -> bool:
        if not app.screen_stack or not isinstance(app.screen_stack[-1], ReviewScreen):
            return False
        try:
            app.screen_stack[-1].query_one("#confirm", Button)
        except NoMatches:
            return False
        return True

    async def test_item_and_skill_search_modals_accept_keyboard_input(self) -> None:
        configure_logging()
        with tempfile.TemporaryDirectory(prefix="fh-textual-test-") as temp_dir:
            repo = build_fake_repository(Path(temp_dir))
            app = FearHungerTextualApp(repo=repo, catalog=build_test_catalog())
            async with app.run_test(size=(140, 45)) as pilot:
                await self._wait_until(lambda: app.session is not None and not app.operation_in_progress)
                assert app.session is not None

                app.query_one("#tabs", TabbedContent).active = "items"
                await asyncio.sleep(0.1)
                app.query_one("#action-add", Button).press()
                await self._wait_until(
                    lambda: isinstance(app.screen, TextInputScreen) and isinstance(app.focused, Input)
                )
                self.assertTrue(app.screen.query_one("#prompt-input", Input).has_focus)
                await pilot.press("9", "4", "enter")
                await self._wait_until(lambda: isinstance(app.screen, ChoiceScreen))
                await pilot.press("enter")
                await self._wait_until(
                    lambda: isinstance(app.screen, TextInputScreen) and isinstance(app.focused, Input)
                )
                self.assertTrue(app.screen.query_one("#prompt-input", Input).has_focus)
                await pilot.press("enter")
                await self._wait_until(lambda: not app.operation_in_progress)
                self.assertTrue(app.session.dirty)

                actor_id = app._actor_list()[0]
                known_skills = set(get_actor(app.session.data, actor_id)["_skills"]["@a"])
                skill_id = next(skill_id for skill_id in app.catalog.skills if skill_id not in known_skills)
                app.actor_selection = actor_id
                app.query_one("#tabs", TabbedContent).active = "actors"
                app._update_actions_visibility()
                await asyncio.sleep(0.1)
                app.query_one("#action-skill", Button).press()
                await self._wait_until(lambda: app.operation_in_progress)
                await self._wait_until(
                    lambda: isinstance(app.screen, TextInputScreen) and isinstance(app.focused, Input)
                )
                self.assertTrue(app.screen.query_one("#prompt-input", Input).has_focus)
                await pilot.press(*list(str(skill_id)), "enter")
                await self._wait_until(lambda: isinstance(app.screen, ChoiceScreen))
                await pilot.press("enter")
                await self._wait_until(lambda: not app.operation_in_progress)
                self.assertIn(skill_id, get_actor(app.session.data, actor_id)["_skills"]["@a"])

                app.query_one("#action-skill", Button).press()
                await self._wait_until(lambda: app.operation_in_progress)
                await pilot.press("escape")
                await self._wait_until(lambda: not app.operation_in_progress)

    async def test_apply_flow_requires_review_and_creates_backup(self) -> None:
        configure_logging()
        with tempfile.TemporaryDirectory(prefix="fh-textual-apply-test-") as temp_dir:
            repo = build_fake_repository(Path(temp_dir))
            app = FearHungerTextualApp(repo=repo, catalog=build_test_catalog())
            async with app.run_test(size=(140, 45)) as pilot:
                await self._wait_until(lambda: app.session is not None and not app.operation_in_progress)
                assert app.session is not None
                slot = app._selected_slot()
                assert slot is not None
                self.assertEqual(repo.list_backups(slot), [])

                app.query_one("#tabs", TabbedContent).active = "items"
                await asyncio.sleep(0.1)
                app.query_one("#action-add", Button).press()
                await self._wait_until(
                    lambda: isinstance(app.screen, TextInputScreen) and isinstance(app.focused, Input)
                )
                await pilot.press("9", "4", "enter")
                await self._wait_until(lambda: isinstance(app.screen, ChoiceScreen))
                await pilot.press("enter")
                await self._wait_until(
                    lambda: isinstance(app.screen, TextInputScreen) and isinstance(app.focused, Input)
                )
                await pilot.press("2", "enter")
                await self._wait_until(lambda: app.session is not None and app.session.dirty)

                app.query_one("#action-apply", Button).press()
                await self._wait_until(lambda: self._review_confirm_ready(app))
                app.screen_stack[-1].query_one("#confirm", Button).press()
                await self._wait_until(lambda: app.session is not None and not app.session.dirty)

                backups = repo.list_backups(slot)
                self.assertEqual(len(backups), 1)
                self.assertTrue(backups[0].is_file())
