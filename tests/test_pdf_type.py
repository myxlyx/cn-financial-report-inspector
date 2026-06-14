from fri_pdf.pdf_type import _classify_from_metrics


def test_text_based_classification():
    assert _classify_from_metrics(0.95, 800, 0) == "text_based"


def test_mixed_classification():
    assert _classify_from_metrics(0.5, 80, 0) == "mixed"


def test_scanned_classification():
    assert _classify_from_metrics(0.05, 10, 0) == "scanned_or_image_based"
