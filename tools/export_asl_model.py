import json
import sys
from pathlib import Path

import h5py
import numpy as np


def rounded_nested(array: np.ndarray) -> list:
    return np.round(array.astype(np.float32), 7).tolist()


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: export_asl_model.py <model.h5> <classes.npy> <output.json>")
        return 1

    model_path = Path(sys.argv[1])
    classes_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    classes = np.load(classes_path, allow_pickle=True).tolist()

    with h5py.File(model_path, "r") as handle:
        model_config = handle.attrs["model_config"]
        config_text = model_config if isinstance(model_config, str) else model_config.decode("utf-8")
        config = json.loads(config_text)

        dense_layers = []
        for layer in config["config"]["layers"]:
            if layer["class_name"] != "Dense":
                continue

            layer_name = layer["config"]["name"]
            layer_group = handle["model_weights"][layer_name]["sequential"][layer_name]
            dense_layers.append(
                {
                    "name": layer_name,
                    "units": int(layer["config"]["units"]),
                    "activation": layer["config"]["activation"],
                    "kernel_shape": list(layer_group["kernel"].shape),
                    "bias_shape": list(layer_group["bias"].shape),
                    "kernel": rounded_nested(layer_group["kernel"][()]),
                    "bias": rounded_nested(layer_group["bias"][()]),
                }
            )

    payload = {
        "format": "emaa-dense-model",
        "source_model": model_path.name,
        "classes_source": classes_path.name,
        "input_size": 63,
        "classes": classes,
        "layers": dense_layers,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Exported model to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
