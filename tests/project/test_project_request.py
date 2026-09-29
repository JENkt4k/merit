from __future__ import annotations

from pathlib import Path

import pytest

from merit.project.project_request import (
    PROJECT_REQUEST_MAGIC,
    ProjectRequest,
    ProjectRequestError,
    ProjectRequestUnit,
    decode_project_request,
    encode_project_request,
)
from merit.project.replacement_loader import load_replacement_project


def test_replacement_loader_transports_bytes_without_source_discovery(tmp_path: Path) -> None:
    root = tmp_path / "transport"
    (root / "src").mkdir(parents=True)
    (root / "Merit.toml").write_text(
        '[package]\nname="transport"\nentry="src/main.mrt"\nsources=["src/**/*.mrt"]\n',
        encoding="utf-8",
    )
    raw = b"not parsed by the host\x00\xff"
    (root / "src" / "main.mrt").write_bytes(raw)

    project = load_replacement_project(root / "Merit.toml")

    assert len(project.units) == 1
    assert project.units[0].source == raw


def test_project_request_round_trips_ordered_utf8_metadata_and_arbitrary_source() -> None:
    request = ProjectRequest(
        package="demo",
        entry="src/main.mrt",
        units=(
            ProjectRequestUnit("src/helper.mrt", b"module helper\n"),
            ProjectRequestUnit("src/main.mrt", b"module main\n\x00\xff"),
        ),
    )
    encoded = encode_project_request(request)
    assert encoded.startswith(PROJECT_REQUEST_MAGIC)
    assert decode_project_request(encoded) == request


@pytest.mark.parametrize(
    "project_request, message",
    [
        (ProjectRequest("demo", "../main.mrt", (ProjectRequestUnit("../main.mrt", b"x"),)), "canonical"),
        (
            ProjectRequest(
                "demo",
                "src/main.mrt",
                (
                    ProjectRequestUnit("src/main.mrt", b"x"),
                    ProjectRequestUnit("src/helper.mrt", b"y"),
                ),
            ),
            "path-sorted",
        ),
        (ProjectRequest("demo", "src/main.mrt", (ProjectRequestUnit("src/other.mrt", b"x"),)), "entry"),
    ],
)
def test_project_request_encoder_fails_closed_for_noncanonical_transport(
    project_request: ProjectRequest, message: str,
) -> None:
    with pytest.raises(ProjectRequestError, match=message):
        encode_project_request(project_request)


def test_project_request_decoder_rejects_truncation_and_trailing_data() -> None:
    encoded = encode_project_request(
        ProjectRequest("demo", "main.mrt", (ProjectRequestUnit("main.mrt", b"source"),))
    )
    with pytest.raises(ProjectRequestError, match="truncated"):
        decode_project_request(encoded[:-1])
    with pytest.raises(ProjectRequestError, match="trailing"):
        decode_project_request(encoded + b"x")
