"""The tab icons must be valid files: a browser refuses to draw an SVG that is not well-formed XML
(an XML comment may not hold a double hyphen; that broke the first icon). Standard library only."""

import re
import struct
import xml.etree.ElementTree as ET  # noqa: S405 - our own committed file, not untrusted input

from cta.settings import ROOT

APP = ROOT / "web" / "app"


def test_icon_svg_is_well_formed_xml_with_an_svg_root():
    root = ET.parse(APP / "icon.svg").getroot()  # raises ParseError on any XML error
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["viewBox"] == "0 0 64 64"


def test_icon_svg_keeps_the_design_and_has_no_text_or_image_elements():
    root = ET.parse(APP / "icon.svg").getroot()
    ns = "{http://www.w3.org/2000/svg}"
    tags = {el.tag.removeprefix(ns) for el in root.iter()}
    assert tags == {"svg", "rect", "g", "path", "circle"}
    fills = {el.attrib.get("fill") for el in root.iter() if "fill" in el.attrib}
    assert {"#007fa3", "#ffb35c"} <= fills


def test_no_comment_in_the_svg_holds_a_double_hyphen():
    text = (APP / "icon.svg").read_text(encoding="utf-8")
    for comment in re.findall(r"<!--(.*?)-->", text, re.S):
        assert "--" not in comment


def test_apple_icon_is_a_180_pixel_png():
    data = (APP / "apple-icon.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (180, 180)
