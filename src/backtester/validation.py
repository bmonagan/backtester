"""Chronological data splitting helpers for out-of-sample validation."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class WalkForwardFold:
    """One expanding-training, forward validation and test fold."""

    index: int
    train: tuple[object, ...]
    validation: tuple[object, ...]
    test: tuple[object, ...]


def walk_forward_splits(
    timestamps: Iterable[object],
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    step_size: int | None = None,
) -> tuple[WalkForwardFold, ...]:
    """Build expanding chronological folds from unique ordered timestamps.

    Duplicate timestamps, such as one timestamp per symbol in a multi-asset
    feed, are collapsed while preserving order. Training windows expand by
    ``step_size`` on each fold; validation and test windows retain fixed sizes.
    Test windows do not overlap.
    """
    for name, value in (
        ("train_size", train_size),
        ("validation_size", validation_size),
        ("test_size", test_size),
    ):
        _validate_positive_integer(name, value)
    if step_size is None:
        step_size = test_size
    _validate_positive_integer("step_size", step_size)
    if step_size < test_size:
        raise ValueError("step_size must be greater than or equal to test_size")

    ordered = []
    seen = set()
    for timestamp in timestamps:
        try:
            if timestamp in seen:
                continue
            if ordered and timestamp < ordered[-1]:
                raise ValueError("timestamps must be in chronological order")
            seen.add(timestamp)
        except TypeError as error:
            raise ValueError("timestamps must be hashable and mutually comparable") from error
        ordered.append(timestamp)

    folds = []
    offset = 0
    while True:
        train_end = train_size + offset
        validation_end = train_end + validation_size
        test_end = validation_end + test_size
        if test_end > len(ordered):
            break
        folds.append(
            WalkForwardFold(
                index=len(folds),
                train=tuple(ordered[:train_end]),
                validation=tuple(ordered[train_end:validation_end]),
                test=tuple(ordered[validation_end:test_end]),
            )
        )
        offset += step_size

    if not folds:
        required = train_size + validation_size + test_size
        raise ValueError(
            f"at least {required} unique timestamps are required for one fold"
        )
    return tuple(folds)


def _validate_positive_integer(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
