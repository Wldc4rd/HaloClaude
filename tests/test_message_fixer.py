"""Tests for the message fixer module."""

import pytest
from proxy.message_fixer import MessageFixer


@pytest.fixture
def fixer():
    return MessageFixer()


class TestMessageFixer:
    """Tests for MessageFixer."""
    
    def test_empty_messages(self, fixer):
        """Empty message list should be returned unchanged."""
        result = fixer.fix_messages([])
        assert result == []
    
    def test_valid_messages_unchanged(self, fixer):
        """Valid messages should not be modified."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]
        result = fixer.fix_messages(messages)
        assert result == messages
    
    def test_fix_empty_content(self, fixer):
        """Empty content should be replaced with placeholder."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": ""},
        ]
        result = fixer.fix_messages(messages)
        assert result[1]["content"] == fixer.EMPTY_CONTENT_REPLACEMENT
    
    def test_fix_none_content(self, fixer):
        """None content should be replaced with placeholder."""
        messages = [
            {"role": "user", "content": None},
        ]
        result = fixer.fix_messages(messages)
        assert result[0]["content"] == fixer.EMPTY_CONTENT_REPLACEMENT
    
    def test_fix_assistant_ending(self, fixer):
        """Conversations ending with assistant should get user message appended."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = fixer.fix_messages(messages)
        assert len(result) == 3
        assert result[-1]["role"] == "user"
        assert result[-1]["content"] == fixer.ASSISTANT_ENDING_APPEND
    
    def test_user_ending_unchanged(self, fixer):
        """Conversations ending with user should not be modified."""
        messages = [
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "Hello"},
        ]
        result = fixer.fix_messages(messages)
        assert len(result) == 2
        assert result[-1]["role"] == "user"
        assert result[-1]["content"] == "Hello"
    
    def test_combined_fixes(self, fixer):
        """Both fixes should be applied when needed."""
        messages = [
            {"role": "system", "content": "Instructions"},
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "Response"},
        ]
        result = fixer.fix_messages(messages)

        # Empty content should be fixed
        assert result[1]["content"] == fixer.EMPTY_CONTENT_REPLACEMENT

        # User message should be appended
        assert len(result) == 4
        assert result[-1]["role"] == "user"

    def test_original_not_mutated(self, fixer):
        """Original messages should not be modified."""
        messages = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "Response"},
        ]
        original_len = len(messages)
        original_content = messages[0]["content"]

        result = fixer.fix_messages(messages)

        # Original should be unchanged
        assert len(messages) == original_len
        assert messages[0]["content"] == original_content

        # Result should be different
        assert len(result) == original_len + 1
        assert result[0]["content"] == fixer.EMPTY_CONTENT_REPLACEMENT
