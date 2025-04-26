import glob
import os
from typing import List, Optional

from ilio import write

from .component_types import Component
from .constants import *


def generate_skaffolds(components: List[Component]):
    global_skaffold_paths = []
    for component in components:
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

