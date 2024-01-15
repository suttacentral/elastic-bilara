from enum import Enum


class TextType(Enum):
    ROOT = "root"
    HTML = "html"
    TRANSLATION = "translation"
    COMMENT = "comment"
    REFERENCE = "reference"
    VARIANT = "variant"
