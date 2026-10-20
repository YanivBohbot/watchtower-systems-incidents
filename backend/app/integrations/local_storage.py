"""Evidence, videos and documents stored as files under one root directory."""

from pathlib import Path


class LocalStorage:
    """Keys are server-generated UUID paths, never client-provided filenames."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root) or target == self.root:
            raise ValueError("Invalid storage key")
        return target

    def put(self, key: str, content: bytes) -> None:
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_bytes(content)
        temp.replace(target)

    def put_file(self, key: str, source: Path) -> None:
        """Move an already written file into storage (same filesystem, atomic replace)."""
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        Path(source).replace(target)

    def read(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def local_copy(self, key: str, destination: Path) -> Path:
        return self.path(key)
