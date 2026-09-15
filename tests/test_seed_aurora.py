from scripts.seed_aurora import split_records


def test_split_records_groups_text_and_figures():
    recs = [
        {"paper_id": "A", "source_id": "A:c0", "modality": "text",
         "text": "t", "embedding": [0.0]},
        {"paper_id": "A", "source_id": "A:fig0", "modality": "figure",
         "figure_label": "Figure 1", "image_uri": "u", "text": "cap",
         "embedding": [0.0]},
    ]
    text, figs = split_records(recs)
    assert [r["source_id"] for r in text] == ["A:c0"]
    assert [r["source_id"] for r in figs] == ["A:fig0"]
    assert figs[0]["figure_label"] == "Figure 1"
