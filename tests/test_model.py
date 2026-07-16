import pandas as pd
import pytest

from anime_stackviz.model import chronological_split


def test_chronological_split_preserves_order():
    frame = pd.DataFrame({"value": range(10)})
    train, test = chronological_split(frame)
    assert train["value"].tolist() == list(range(8))
    assert test["value"].tolist() == [8, 9]


def test_chronological_split_rejects_invalid_fraction():
    with pytest.raises(ValueError):
        chronological_split(pd.DataFrame({"value": range(10)}), train_fraction=1)
