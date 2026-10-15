"""Regression: ignored best-limit placeholders cannot break standard watch."""
from copy import deepcopy
import pytest
from pydara.tse._core.exceptions import DataQualityError
from test_market_extension import sample_market_client, fixtures


def test_invalid_book_placeholder_is_ignored_for_plain_market_watch():
    fake = deepcopy(fixtures()['market.watch'])
    row = fake['marketwatch'][0]
    row['blDs'] = [{'n': 0, 'pmd': 0, 'pmo': 0, 'qmd': 0, 'qmo': 0, 'zmd': 0, 'zmo': 0}]
    with sample_market_client(responses={'market.watch': fake}) as client:
        result = client.get_market_watch()
    assert not result.empty
    assert result.attrs['pydara']['order_book_rows'] == 0


def test_invalid_book_placeholder_still_rejected_when_requested():
    fake = deepcopy(fixtures()['market.watch'])
    fake['marketwatch'][0]['blDs'] = [{'n': 0, 'pmd': 0, 'pmo': 0, 'qmd': 0, 'qmo': 0, 'zmd': 0, 'zmo': 0}]
    with sample_market_client(responses={'market.watch': fake}) as client:
        with pytest.raises(DataQualityError, match='best-limit depth'):
            client.get_market_watch(include_order_book=True)
