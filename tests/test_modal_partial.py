import pytest
from flask import render_template


def test_modal_partial_contains_required_elements(app):
    """Test that the _poem_modal.html partial contains all required elements."""
    with app.app_context():
        html = render_template("_poem_modal.html")

        # Check for modal container
        assert 'class="modal"' in html
        assert 'hidden' in html

        # Check for modal elements
        assert 'data-modal-title' in html
        assert 'data-modal-body' in html
        assert '<pre' in html

        # Check for buttons
        assert 'modal__copy-button' in html
        assert 'modal__close-button' in html
        assert 'Copy' in html
        assert 'Close' in html

        # Check for overlay
        assert 'modal__overlay' in html


def test_search_page_includes_modal_and_script(client):
    """Test that search.html includes the modal partial and script tag."""
    response = client.get("/")
    assert response.status_code == 200

    html = response.get_data(as_text=True)

    # Check for modal inclusion
    assert 'class="modal"' in html
    assert 'data-modal-title' in html
    assert 'data-modal-body' in html

    # Check for script tag
    assert 'search.js' in html
    assert '<script' in html
