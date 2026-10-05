from .manifest import Manifest, load_manifest

__all__ = ["Manifest", "LoadedProject", "ProjectError", "load_manifest", "load_project"]


def __getattr__(name: str):
    if name in {"LoadedProject", "ProjectError", "load_project"}:
        from . import loader

        return getattr(loader, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
