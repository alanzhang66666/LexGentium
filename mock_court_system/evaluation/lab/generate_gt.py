import sys
from pathlib import Path

import yaml

_LAB_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _LAB_DIR.parent
_PROJECT_ROOT = _EVAL_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from evaluation.lab._paths import EVAL_DIR

from evaluation.converters.cd_converter import CDConverter
from evaluation.converters.ci_converter import CIConverter
from evaluation.converters.dd_converter import DDConverter


def load_config(config_path=None):
    path = Path(config_path) if config_path else EVAL_DIR / "eval_config.yaml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    config = load_config()
    paths = config["evaluation"]["paths"]

    print("Converting CD Data...")
    cd_conv = CDConverter(
        dialog_dir=paths["raw_data"]["cd_dialog"],
        doc_dir=paths["raw_data"]["cd_doc"],
    )
    cd_conv.convert(paths["ground_truth"]["cd"], "CD")

    print("Converting DD Data...")
    dd_conv = DDConverter(
        dialog_dir=paths["raw_data"]["dd_dialog"],
        doc_dir=paths["raw_data"]["dd_doc"],
    )
    dd_conv.convert(paths["ground_truth"]["dd"], "DD")

    print("Converting CI Data...")
    ci_conv = CIConverter(
        dialog_dir=paths["raw_data"]["ci_dialog"],
        doc_dir=paths["raw_data"]["ci_doc"],
    )
    ci_conv.convert(paths["ground_truth"]["ci"], "CI")

    print("All conversions completed.")


if __name__ == "__main__":
    main()
