import glob
import os
import yaml
from typing import List, Optional, Set

from ilio import write

from .component_types import Component
from .constants import *


def _get_component_id(component: Component) -> str:
    """Create unique identifier using slug, namespace, dir_name, and fleet_name"""
    return f"{component.slug}:{component.namespace}:{component.dir_name}:{component.fleet_name}"


def _resolve_dependencies(components: List[Component]) -> List[Component]:
    """
    Resolve component dependencies to ensure each component appears only once
    and dependencies are properly ordered.
    """
    resolved_components = []
    visited = set()

    def visit_component(component: Component):
        component_id = _get_component_id(component)
        if component_id in visited:
            return

        # First visit all dependencies
        if component.depends_on:
            for dependency in component.depends_on:
                visit_component(dependency)

        # Then add the component itself
        if component_id not in visited:
            resolved_components.append(component)
            visited.add(component_id)

    # Visit all components to ensure all are included
    for component in components:
        visit_component(component)

    return resolved_components


def generate_skaffolds(components: List[Component]):
    # Resolve dependencies to get the correct order and avoid duplicates
    resolved_components = _resolve_dependencies(components)

    print(f"components: {[_get_component_id(c) for c in components]}")
    print(f"resolved_components: {[_get_component_id(c) for c in resolved_components]}")
    global_skaffold_paths = []
    for component in resolved_components:
        dir_name = component.dir_name
        if dir_name == "":
            continue

        skaffold_paths = []
        for filepath in sorted(glob.glob(f"{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}/**/*.*", recursive=True),
                               key=lambda x: (-1 if "operator" in x else 1) * len(x), reverse=False):
            if "/skaffold-" in filepath and "/skaffold-with-build-" not in filepath:
                skaffold_paths.append({
                    "path": filepath.replace(f"{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}/", "./")
                })

        if not os.path.isfile(f"{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}/skaffold.yaml"):
            write(f"{GENERATED_SKAFFOLD_TMP_DIR}/{dir_name}/skaffold.yaml", yaml.dump({
                "apiVersion": "skaffold/v3",
                "kind": "Config",
                "requires": skaffold_paths,
            }))

        global_skaffold_paths.append({
            "path": f"{dir_name}/skaffold.yaml"
        })
    # Determine the output path for the main skaffold file
    main_skaffold_dir = GENERATED_SKAFFOLD_TMP_DIR
    write(f"{main_skaffold_dir}/skaffold--main--all.yaml", yaml.dump({
        "apiVersion": "skaffold/v3",
        "kind": "Config",
        "requires": global_skaffold_paths,
    }))

