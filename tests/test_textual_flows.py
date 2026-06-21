from __future__ import annotations

import asyncio
import unittest

from textual.widgets import Button, Input, TabbedContent

from fh_admin_tui.diagnostics import configure_logging
from fh_admin_tui.mutations import get_actor
from fh_admin_tui.textual_app import ChoiceScreen, FearHungerTextualApp, TextInputScreen


class TextualFlowTests(unittest.IsolatedAsyncioTestCase):
    async def _wait_until(self, predicate, timeout: float = 5.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while not predicate():
            if asyncio.get_running_loop().time() >= deadline:
                self.fail("Timeout aguardando estado da interface")
            await asyncio.sleep(0.05)

    async def test_item_and_skill_search_modals_accept_keyboard_input(self) -> None:
        configure_logging()
        app = FearHungerTextualApp()
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
