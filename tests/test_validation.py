import pytest

from backtester.validation import WalkForwardFold, walk_forward_splits


def test_walk_forward_splits_use_expanding_train_and_forward_test_windows():
    folds = walk_forward_splits(
        range(12),
        train_size=4,
        validation_size=2,
        test_size=2,
    )

    assert folds == (
        WalkForwardFold(
            index=0,
            train=(0, 1, 2, 3),
            validation=(4, 5),
            test=(6, 7),
        ),
        WalkForwardFold(
            index=1,
            train=(0, 1, 2, 3, 4, 5),
            validation=(6, 7),
            test=(8, 9),
        ),
        WalkForwardFold(
            index=2,
            train=(0, 1, 2, 3, 4, 5, 6, 7),
            validation=(8, 9),
            test=(10, 11),
        ),
    )


def test_walk_forward_splits_collapse_duplicate_multi_asset_timestamps():
    folds = walk_forward_splits(
        ["d1", "d1", "d2", "d2", "d3", "d3", "d4", "d5"],
        train_size=2,
        validation_size=1,
        test_size=1,
    )

    assert folds[0].train == ("d1", "d2")
    assert folds[0].validation == ("d3",)
    assert folds[0].test == ("d4",)
    assert folds[1].test == ("d5",)


def test_walk_forward_test_windows_do_not_overlap():
    folds = walk_forward_splits(
        range(16),
        train_size=3,
        validation_size=2,
        test_size=2,
        step_size=3,
    )

    test_timestamps = [timestamp for fold in folds for timestamp in fold.test]
    assert len(test_timestamps) == len(set(test_timestamps))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("train_size", 0),
        ("train_size", True),
        ("validation_size", -1),
        ("test_size", 1.5),
        ("step_size", 0),
    ],
)
def test_walk_forward_rejects_invalid_window_sizes(name, value):
    kwargs = {"train_size": 2, "validation_size": 1, "test_size": 1}
    kwargs[name] = value

    with pytest.raises(ValueError, match="positive integer"):
        walk_forward_splits(range(10), **kwargs)


def test_walk_forward_rejects_overlapping_test_windows():
    with pytest.raises(ValueError, match="step_size"):
        walk_forward_splits(
            range(10),
            train_size=2,
            validation_size=1,
            test_size=3,
            step_size=2,
        )


def test_walk_forward_rejects_unordered_timestamps():
    with pytest.raises(ValueError, match="chronological order"):
        walk_forward_splits(
            [1, 3, 2, 4],
            train_size=1,
            validation_size=1,
            test_size=1,
        )


def test_walk_forward_rejects_insufficient_unique_timestamps():
    with pytest.raises(ValueError, match="at least 4 unique timestamps"):
        walk_forward_splits(
            [1, 1, 2, 3],
            train_size=2,
            validation_size=1,
            test_size=1,
        )
