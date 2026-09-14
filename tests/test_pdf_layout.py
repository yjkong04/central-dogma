from ingest.pdf.layout import map_label


def test_map_label_normalizes_model_classes_to_our_kinds():
    assert map_label("Picture") == "figure"
    assert map_label("Figure") == "figure"
    assert map_label("Table") == "table"
    assert map_label("Title") == "title"
    assert map_label("Section-header") == "title"
    assert map_label("Caption") == "caption"
    assert map_label("Text") == "text"
    assert map_label("List-item") == "list"
    assert map_label("something-unknown") == "text"  # safe default
