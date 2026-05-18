from datetime import date

import pytest

from dou_classifier.collect.inlabs_client import (
    InlabsClient,
    InvalidSectionError,
    build_resource,
    normalize_section,
)


def test_build_resource_uses_official_xml_zip_pattern():
    resource = build_resource(date(2025, 5, 16), "do1")

    assert resource.section == "DO1"
    assert resource.filename == "2025-05-16-DO1.zip"
    assert (
        resource.url
        == "https://inlabs.in.gov.br/index.php?p=2025-05-16&dl=2025-05-16-DO1.zip"
    )


def test_normalize_section_accepts_extra_section():
    assert normalize_section("do1e") == "DO1E"


def test_normalize_section_rejects_non_xml_section_for_this_project():
    with pytest.raises(InvalidSectionError):
        normalize_section("DO2")


class FakeSession:
    def __init__(self):
        self.get_kwargs = None

    def get(self, url, **kwargs):
        self.get_kwargs = kwargs
        return object()


def test_get_zip_follows_redirects_like_official_examples():
    session = FakeSession()
    client = InlabsClient(session=session)

    client.get_zip(date(2025, 5, 16), "DO1")

    assert session.get_kwargs["allow_redirects"] is True
