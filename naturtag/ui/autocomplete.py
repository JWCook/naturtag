# Generic/reusable autocomplete components
# Ideas for autocomplete layout originally taken from:
# https://www.reddit.com/r/kivy/comments/99n2ct/anyone_having_idea_for_autocomplete_feature_in/e4phtf8/
from collections.abc import Mapping
from logging import getLogger

from kivy.clock import Clock
from kivy.properties import BooleanProperty, DictProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import FocusBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recycleview.layout import LayoutSelectionBehavior

from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField

from naturtag.constants import AUTOCOMPLETE_DELAY, AUTOCOMPLETE_MIN_CHARS

# Set dropdown size large enough for 10 results; if there are any more than that, use scrollbar
DROPDOWN_ITEM_SIZE = 22
MAX_DROPDOWN_SIZE = 10 * 22 + 50

logger = getLogger().getChild(__name__)


class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior, RecycleBoxLayout):
    """ Class that adds selection and focus behaviour to a dropdown list """


class AutocompleteSearch(MDBoxLayout):
    """
    Layout class containing components needed for autocomplete search.
    This manages an input field and a dropdown, so they don't interact with each other directly.
    Also includes rate-limited trigger for input delay (so we don't spam searches on every keypress).

    Must be inherited by a subclass that implements :py:meth:`get_autocomplete`.
    """
    input = ObjectProperty()
    dropdown = ObjectProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.trigger = Clock.create_trigger(self.callback, AUTOCOMPLETE_DELAY)
        # Define a callback to trigger external changes on selection
        # TODO: This is probably not the kivy way of doing things; not sure how to define a custom event to bind to
        self.selection_callback = lambda *x: x

    def callback(self, *args):
        """ Autocompletion callback, rate-limited by ``AUTOCOMPLETE_DELAY`` milliseconds """
        seatch_str = self.input.text
        if len(seatch_str) < AUTOCOMPLETE_MIN_CHARS:
            return

        def get_row(item):
            """ Return a row for dropdown list; use optional metadata if provided """
            if isinstance(item, Mapping):
                return item
            return {'text': item, 'suggestion_text': item, 'metadata': {}}

        matches = self.get_autocomplete(seatch_str)
        logger.info(f'Found {len(matches)} matches for search string "{seatch_str}"')
        self.dropdown.data = [get_row(i) for i in matches]
        self.height = min(MAX_DROPDOWN_SIZE, (len(matches) * DROPDOWN_ITEM_SIZE) + 50)

    # TODO: formatting for suggestion_text; smaller text + different color
    def update_selection(self, suggestion_text, metadata):
        """ Intermediate handler to update suggestion text based on dropdown selection """
        logger.info(f'Updating selection: {suggestion_text}')
        self.input.suggestion_text = '    ' + suggestion_text
        self.selection_callback(metadata)

    def get_autocomplete(self, search_str):
        """
        Autocompletion behavior to be implemented by a subclass. There are two return format options:

        1. Just return a list of strings representing match text to display
        2. Return a dict with additional info:
            * The text to display in the dropdown
            * The text to place in ``suggestion_text`` when selected
            * A dict of additional metadata to be retrieved when selected

        Example::

            [
                {'text': display_text, 'suggestion_text': suggestion_text, 'metadata': metadata},
            ]

        Args:
            search_str (str): Search string to fetch matches for

        Returns:
            list: List of either match strings, or dicts with additional metadata
        """
        raise NotImplementedError


class DropdownItem(RecycleDataViewBehavior, MDLabel):
    """
    A label representing a dropdown item, which handles click events.
    Optionally contains additional metadata to associate with the item.
    """
    index = None
    selectable = True
    is_selected = BooleanProperty(False)
    suggestion_text = StringProperty()
    metadata = DictProperty()

    def refresh_view_attrs(self, rv, index, data):
        """ Catch and handle view changes """
        self.index = index
        return super().refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        """ Add selection on click """
        if super().on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, dropdown, index, is_selected):
        """ Respond to the selection of items in the view """
        self.is_selected = is_selected
        # TODO: Is there a better way of referencing AutocompleteSearch than parent.parent.parent?
        if is_selected:
            self.parent.parent.parent.update_selection(self.suggestion_text, self.metadata)


class SearchInput(MDTextField):
    """ A text input field for autocomplete search. """
    def on_text(self, instance, value):
        """ Trigger an autocomplete query, unless one has been triggered immediately prior """
        self.parent.trigger()

    # TODO: Not yet working as intended
    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        """ Select an autocomplete match with the tab key """
        if self.suggestion_text and keycode[1] == 'tab':
            self.insert_text(self.suggestion_text + ' ')
            return True
        return super().keyboard_on_key_down(window, keycode, text, modifiers)
