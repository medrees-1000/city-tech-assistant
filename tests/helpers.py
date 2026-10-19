"""Small fakes shared by several test files."""

from types import SimpleNamespace


class Model:
    """A chat client that always replies with `content` (10 prompt and 5 completion tokens)."""

    def __init__(self, content):
        self.content = content
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        msg = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)
