"""Program-wide utilities.

Copyright © 2017 Wren Powell <wrenp@duck.com>

This file is part of skiddie.

skiddie is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

skiddie is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with skiddie.  If not, see <http://www.gnu.org/licenses/>.
"""
import abc
import itertools
import os
import random
import sys
import shutil
import pkg_resources
from typing import Sequence, Iterator, List, TypeVar

import six
from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.validation import Validator
from prompt_toolkit import print_formatted_text, prompt
from prompt_toolkit.layout import Float, Layout, FormattedTextControl, Window

# The relative path to the directory containing the instructions for each game.
INSTRUCTIONS_DIR = "descriptions"

T = TypeVar("T")


def _format_banner(message: str, padding_char="=") -> str:
    """Format a banner message that is centered in the window.

    Args:
        message: The message to format.
        padding_char: The character to pad the message with.

    Returns:
        The formatted banner message.
    """
    term_width = shutil.get_terminal_size().columns
    return "{0:{1}^{2}}".format(" {} ".format(message), padding_char, term_width)


def print_banner(message: str, padding_char: str = "=", style: str = "") -> None:
    """Print a banner message that is centered in the window.

    Args:
        message: The message to print.
        padding_char: The character to pad the message with.
        style: A space-separated string of styles to apply to the message.
    """
    banner = _format_banner(message, padding_char)

    if sys.stdout.isatty():
        print_formatted_text(FormattedText([(style, banner)]))
    else:
        print(banner)


class LateInit:
    """Raise an exception if the attribute is unset.

    Args:
        message: The message passed to the exception when the value is accessed before it is set.
    """
    def __init__(self, message: str = "this value must not be None") -> None:
        self._value = None
        self._message = message

    def __get__(self, instance, owner):
        if self._value is None:
            raise ValueError(self._message)
        return self._value

    def __set__(self, instance, value):
        self._value = value


def get_description(file_name: str) -> str:
    """Get the descriptions of a game.

    Args:
        file_name: The name of the text file containing the description relative to INSTRUCTIONS_DIR.
    """
    relative_path = os.path.join(INSTRUCTIONS_DIR, file_name)
    return pkg_resources.resource_string(__name__, relative_path).decode("utf-8")


def bool_prompt(message: str, default: bool = False) -> bool:
    """Prompt the user to answer yes or no.

    This accepts the same arguments as prompt_toolkit.PromptSession.

    Returns:
        The user's choice.
    """
    true_answers = ["y", "yes"]
    false_answers = ["n", "no"]

    validator = Validator.from_callable(
        lambda x: not x or x.lower() in true_answers + false_answers,
        error_message="Answer must be \"yes\" or \"no\"",
        move_cursor_to_end=True,
    )
    answer = prompt(message=message, validator=validator, validate_while_typing=False)

    if answer:
        return answer.lower() in true_answers
    else:
        return default


def format_duration(seconds: float) -> str:
    """Return a formatted string representing a duration in seconds.

    A duration of 63.29 seconds would be formatted as "1m 3.3s".
    """
    minutes, seconds = divmod(seconds, 60)
    return "{0:.0f}m {1:.1f}s".format(minutes, seconds)


def format_bytes(num_bytes: int, decimal_places: int = 1) -> str:
    """Format a number of bytes as a human-readable string."""
    remaining_bytes = num_bytes
    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB"]:
        if remaining_bytes < 1024:
            return "{0:.{1}f}{2}".format(remaining_bytes, decimal_places, unit)
        remaining_bytes /= 1024

    return "{0:.{1}f}YiB".format(remaining_bytes, decimal_places, unit)


def format_table(rows: Sequence[Sequence[str]], separator: str = "  ", align_right: bool = False) -> str:
    """Return the given data in a formatted table.

    Args:
        rows: The rows of data to print.
        separator: The string used to separate each column.
        align_right: Align each column to the right instead of to the left.

    Returns:
        The formatted table.
    """
    # Get the length of the longest string in each column.
    column_lengths = [0 for _ in range(len(max(rows, key=len)))]
    for row in rows:
        for i, item in enumerate(row):
            column_lengths[i] = max(len(item), column_lengths[i])

    format_string = "{0:>{1}}" if align_right else "{0:{1}}"

    # Pad and align each row.
    output = "\n".join(
        separator.join(
            format_string.format(item, column_lengths[i])
            for i, item in enumerate(row)
        )
        for row in rows
    )

    return output


def get_random_cycle(sequence: Sequence[T]) -> Iterator[T]:
    """Return a randomized cycle of the given sequence."""
    random_sequence = list(sequence)
    random.shuffle(random_sequence)
    return itertools.cycle(random_sequence)


def take_random_cycle(sequence: Sequence[T], items: int) -> List[T]:
    """Take a given number of elements from a random cycle."""
    random_cycle = get_random_cycle(sequence)
    return [next(random_cycle) for _ in range(items)]


class Screen(abc.ABC):
    """A screen in a graphical terminal application.

    Args:
        multi_screen: A reference to the MultiScreenApp containing this instance.

    Attributes:
        multi_screen: A reference to the MultiScreenApp containing this instance.
    """
    def __init__(self, multi_screen: "MultiScreenApp") -> None:
        self.multi_screen = multi_screen

    @abc.abstractmethod
    def get_root_container(self):
        """Get the top-level container for the screen."""


class MultiScreenApp:
    """A graphical terminal application that supports switching between multiple screens.

    Args:
        app: The application instance to use. This should not define a layout.
        default_screen: The screen that shows by default when the application starts.

    Attributes:
        app: The application instance to use.
        _screen_history: A list that keeps track of which screens have been visited.
    """
    def __init__(self, app: Application, default_screen: Screen) -> None:
        self.app = app
        self.app.layout = Layout(container=default_screen.get_root_container())

        self._screen_history = [default_screen]

    def set_screen(self, screen: Screen) -> None:
        """Set the active screen.

        Args:
            screen: The screen to set as active.
        """
        root_container = screen.get_root_container()
        self.app.layout.container = root_container
        self.app.layout.focus(root_container)
        self._screen_history.append(screen)

    def set_previous(self) -> None:
        """Set the active screen to the previous screen."""
        self._screen_history.pop()
        self.set_screen(self._screen_history.pop())

    def add_floating_screen(self, screen: Screen) -> None:
        """Add a screen to the layout as a floating window.

        Args:
            screen: The screen to add.
        """
        root_container = screen.get_root_container()
        self.app.layout.container.floats.append(Float(root_container))
        self.app.layout.focus(root_container)

    def clear_floating(self) -> None:
        """Remove all floating windows."""
        self.app.layout.container.floats.clear()
        self.app.layout.focus(self.app.layout.container)


class SelectableLabel:
    """A selectable text label.

    This is different from the `Button` classs included with prompt_toolkit in that the contents of the button are
    left-aligned and there are no angle brackets framing the text.

    Args:
        text: The text to display in the label.
        handler: The function to call when the label is selected.
    """
    def __init__(self, text: six.text_type, handler=None) -> None:
        self.text = text
        self.handler = handler

        self.control = FormattedTextControl(
            self.text,
            key_bindings=self._get_key_bindings(),
            focusable=True
        )

        def get_style():
            if get_app().layout.has_focus(self):
                return 'class:selectable-label.focused'
            else:
                return 'class:selectable-label'

        self.window = Window(
            self.control,
            style=get_style,
            dont_extend_width=False,
            dont_extend_height=True,
            always_hide_cursor=True,
        )

    def _get_key_bindings(self) -> KeyBindings:
        bindings = KeyBindings()

        @bindings.add(" ")
        @bindings.add("enter")
        def _handle(_):
            if self.handler is not None:
                self.handler()

        return bindings

    def __pt_container__(self):
        return self.window
