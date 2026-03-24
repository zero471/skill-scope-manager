from __future__ import annotations

from _scope_lib import REGISTRY_MD, REGISTRY_YAML, load_registry, save_registry_markdown


def main() -> None:
    registry = load_registry(REGISTRY_YAML)
    save_registry_markdown(registry, REGISTRY_MD)
    print(REGISTRY_MD)


if __name__ == "__main__":
    main()
