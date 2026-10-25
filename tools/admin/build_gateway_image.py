"""Prepare or explicitly build the fixed guarded nginx image from one wheel.

Image building is separate from deployment: it never contacts a daemon unless
--build was explicitly requested, and it does not start containers or networks.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


def prepare(wheel, base_image, output):
    wheel, output = Path(wheel), Path(output)
    if not re.fullmatch(r"(?:docker\.io/library/)?nginx@sha256:[0-9a-f]{64}", base_image):
        raise ValueError("Select an exact official nginx Alpine image digest")
    if not wheel.is_file() or not re.fullmatch(r"infra_local_hand-[A-Za-z0-9_.+-]+\.whl", wheel.name):
        raise ValueError("Use the selected infra-local-hand four-package wheel")
    # Validate, copy and report one bounded byte snapshot. Reopening the source
    # for each phase could bind a later file to an earlier copied wheel.
    with wheel.open("rb") as stream:
        raw = stream.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError("Selected wheel exceeds the fixed build input bound")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        required = {package + "/__init__.py" for package in
                    ("local_hand", "local_hand_connect", "local_hand_jobs", "local_hand_mcp")}
        required.add("local_hand_mcp/gateway_guard.py")
        if not required <= set(names) or len(names) != len(set(names)):
            raise ValueError("Wheel is missing the guarded gateway release")
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise ValueError("Invalid wheel member")
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        (output / "wheels").mkdir(mode=0o700)
        (output / "wheels" / wheel.name).write_bytes(raw)
        dockerfile = Path(__file__).resolve().parents[2] / "containers/gateway/Dockerfile"
        shutil.copyfile(dockerfile, output / "Dockerfile")
        record = {"schema": "local-hand-gateway-build/v1", "base_image": base_image,
                  "wheel": wheel.name, "wheel_sha256": hashlib.sha256(raw).hexdigest(),
                  "dockerfile_sha256": hashlib.sha256(dockerfile.read_bytes()).hexdigest()}
        (output / "build-inputs.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
        return record
    except BaseException:
        # Keep the failed context for inspection; never overwrite another build.
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--base-image", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--tag", default="local-hand-guarded-gateway:local")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]*(?::[A-Za-z0-9_.-]+)?", args.tag):
        parser.error("invalid local image tag")
    record = prepare(args.wheel, args.base_image, args.output)
    if args.build:
        subprocess.run(["docker", "build", "--build-arg", "NGINX_BASE_IMAGE=" + args.base_image,
                        "--tag", args.tag, "--iidfile", str(Path(args.output) / "image-id"), args.output], check=True)
    print(json.dumps({"prepared": True, "built": args.build, "inputs": record}, sort_keys=True))


if __name__ == "__main__":
    main()
