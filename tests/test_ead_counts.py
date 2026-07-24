from pathlib import Path

import pytest
from eadpy import from_path

"""
sample.xml summary:
    - 4 top-level c01 elements
    - 13 second-level c02 elements
    - 9 third-level c03 elements
    - 2 fourth-level c04 elements
    - 17 components representing individual items (leaf components plus
      components explicitly marked level="item"). The collection-level extent
      says "42 items" because some item-level components group multiple
      physical items (e.g. "5 photographs").
"""

@pytest.fixture(scope="module")
def ead_instance():
    """
    Creates and returns an EAD instance from the sample XML file.

    Returns
    -------
    EAD
        An instance of the EAD class initialized with test data.
    """
    # Use the package-level from_path function instead of class method
    return from_path(str(Path(__file__).parent / "sample.xml"))

def test_top_level_files_count(ead_instance):
    # Count top-level components
    top_level_components = ead_instance.data["components"]
    assert len(top_level_components) == 4, f"Expected 4 top-level files, got {len(top_level_components)}"

def test_second_level_files_count(ead_instance):
    # Count second-level components across all top-level components
    second_level_count = 0
    for component in ead_instance.data["components"]:
        if "components" in component:
            second_level_count += len(component["components"])
    
    assert second_level_count == 13, f"Expected 13 second-level files, got {second_level_count}"

def test_third_level_files_count(ead_instance):
    # Count third-level components
    third_level_count = 0
    for top_component in ead_instance.data["components"]:
        if "components" in top_component:
            for second_component in top_component["components"]:
                if "components" in second_component:
                    third_level_count += len(second_component["components"])
    
    assert third_level_count == 9, f"Expected 9 third-level files, got {third_level_count}"

def test_fourth_level_files_items_count(ead_instance):
    # Count fourth-level components
    fourth_level_count = 0
    for top_component in ead_instance.data["components"]:
        if "components" in top_component:
            for second_component in top_component["components"]:
                if "components" in second_component:
                    for third_component in second_component["components"]:
                        if "components" in third_component:
                            fourth_level_count += len(third_component["components"])
    
    assert fourth_level_count == 2, f"Expected 2 fourth-level files/items, got {fourth_level_count}"

def test_item_level_components(ead_instance):
    """Test that components with level='item' are correctly identified"""
    # Count all components with level='item' at any level of hierarchy
    item_count = 0
    
    def count_items(component):
        nonlocal item_count
        if component.get("level") == "item":
            item_count += 1
        if "components" in component:
            for child in component["components"]:
                count_items(child)
    
    # Start with the top-level components
    for component in ead_instance.data["components"]:
        count_items(component)
    
    # The actual count of explicit items will depend on how many are tagged with level="item"
    # This is a placeholder assertion - adjust based on your sample.xml content
    assert item_count > 0, f"Expected to find some items, got {item_count}"

def test_total_individual_items(ead_instance):
    """
    Test the total count of individual item components in the sample document.

    Counts components explicitly marked level="item" plus leaf components
    without that level. The result (17) is intentionally lower than the "42
    items" in the collection-level extent text, because some item-level
    components group multiple physical items (e.g. "5 photographs").
    """
    leaf_count = 0
    item_count = 0
    
    def count_leaves_and_items(component):
        nonlocal leaf_count, item_count
        
        is_leaf = "components" not in component or not component["components"]
        is_item = component.get("level") == "item"
        
        if is_item:
            item_count += 1
        
        if is_leaf and not is_item:
            leaf_count += 1
        
        if not is_leaf:
            for child in component["components"]:
                count_leaves_and_items(child)
    
    # Process all components
    for component in ead_instance.data["components"]:
        count_leaves_and_items(component)
    
    total_items = leaf_count + item_count
    expected_items = 17  # Actual number of individual components in the hierarchy
    
    assert total_items == expected_items, \
        f"Expected {expected_items} individual items, got {total_items}"