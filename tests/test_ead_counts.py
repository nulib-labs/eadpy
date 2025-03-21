import pytest
from lxml import etree

"""
sample.xml summary:
    - 4 top-level c01 elements
    - 13 second-level c02 elements
    - 9 third-level c03 elements
    - 2 fourth-level c04 elements
    - A total of 42 individual items (combining explicit items and grouped items)
"""


@pytest.fixture(scope="module")
def ead_tree():
    with open("tests/sample.xml", "rb") as f:
        return etree.parse(f)

@pytest.fixture(scope="module")
def ns():
    return {"ead": "urn:isbn:1-931666-22-9"}

def test_top_level_files_count(ead_tree, ns):
    c01_elements = ead_tree.xpath("//ead:dsc/ead:c01", namespaces=ns)
    assert len(c01_elements) == 4, f"Expected 4 top-level files, got {len(c01_elements)}"

def test_second_level_files_count(ead_tree, ns):
    c02_elements = ead_tree.xpath("//ead:dsc/ead:c01/ead:c02", namespaces=ns)
    assert len(c02_elements) == 13, f"Expected 13 second-level files, got {len(c02_elements)}"

def test_third_level_files_count(ead_tree, ns):
    c03_elements = ead_tree.xpath("//ead:dsc/ead:c01/ead:c02/ead:c03", namespaces=ns)
    assert len(c03_elements) == 9, f"Expected 9 third-level files, got {len(c03_elements)}"

def test_fourth_level_files_items_count(ead_tree, ns):
    c04_elements = ead_tree.xpath("//ead:dsc/ead:c01/ead:c02/ead:c03/ead:c04", namespaces=ns)
    assert len(c04_elements) == 2, f"Expected 2 fourth-level files/items, got {len(c04_elements)}"

def test_total_individual_items(ead_tree, ns):
    c02_items = ead_tree.xpath("//ead:dsc//ead:c02[@level='item']", namespaces=ns)
    c03_items = ead_tree.xpath("//ead:dsc//ead:c03[@level='item']", namespaces=ns)
    c04_items = ead_tree.xpath("//ead:dsc//ead:c04[@level='item']", namespaces=ns)
    
    grouped_items_count = 5 + 2 + 5 + 3 + 15  # = 30 grouped items

    total_explicit_items = len(c02_items) + len(c03_items) + len(c04_items) + grouped_items_count
    
    expected_total_items = 42
    assert total_explicit_items == expected_total_items, f"Expected {expected_total_items} total individual items, got {total_explicit_items}"