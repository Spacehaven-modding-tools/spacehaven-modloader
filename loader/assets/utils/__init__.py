import os

from lxml import etree


def create_xml_parser(*, recover=False) -> etree.XMLParser:
    return etree.XMLParser(recover=recover, resolve_entities=False, no_network=True, encoding=os.environ.get('FORCE_PARSER_ENCODING'), remove_comments=True)
