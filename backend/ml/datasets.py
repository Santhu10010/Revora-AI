"""Load and validate the official SemEval-2020 Task 9 Hinglish splits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import io
import zipfile


LABEL_MAP = {
    "positive": "pos",
    "negative": "neg",
    "neutral": "neu",
}
SUPPORTED_SPLITS = ("train", "validation", "test")


@dataclass(frozen=True)
class SentimentExample:
    example_id: str
    text: str
    label: str
    source: str = "SemEval-2020 Task 9"
    language: str = "hinglish"
    original_split: str = ""


def _read_archive_member(archive_path: Path, member: str) -> str:
    if not archive_path.is_file():
        raise FileNotFoundError(f"Dataset archive not found: {archive_path}")
    with zipfile.ZipFile(archive_path) as archive:
        try:
            return archive.read(member).decode("utf-8")
        except KeyError as exc:
            raise ValueError(f"Dataset member not found: {member}") from exc


def _parse_conll_records(content: str, split: str) -> list[SentimentExample]:
    examples: list[SentimentExample] = []
    for block in content.replace("\r\n", "\n").split("\n\n"):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        metadata = lines[0].split("\t")
        if metadata[0] != "meta" or len(metadata) < 2:
            raise ValueError(f"Malformed {split} record metadata: {lines[0]!r}")
        example_id = metadata[1]
        label = LABEL_MAP.get(metadata[2]) if len(metadata) >= 3 else None
        if label is None:
            raise ValueError(f"Missing or unsupported label for {split} example {example_id}")
        tokens = [line.split("\t", 1)[0] for line in lines[1:] if "\t" in line]
        text = " ".join(token for token in tokens if token).strip()
        if not text:
            raise ValueError(f"Empty text for {split} example {example_id}")
        examples.append(
            SentimentExample(
                example_id=example_id,
                text=text,
                label=label,
                original_split=split,
            )
        )
    return examples


def _parse_test_records(content: str, labels_content: str) -> list[SentimentExample]:
    labels = {}
    for row in csv.DictReader(io.StringIO(labels_content)):
        if not row.get("Uid") or not row.get("Sentiment"):
            raise ValueError("Malformed Hinglish test label row")
        mapped = LABEL_MAP.get(row["Sentiment"].strip().lower())
        if mapped is None:
            raise ValueError(f"Unsupported Hinglish test label: {row['Sentiment']!r}")
        labels[row["Uid"]] = mapped

    examples: list[SentimentExample] = []
    for block in content.replace("\r\n", "\n").split("\n\n"):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        metadata = lines[0].split("\t")
        if metadata[0] != "meta" or len(metadata) != 2:
            raise ValueError(f"Malformed test record metadata: {lines[0]!r}")
        example_id = metadata[1]
        if example_id not in labels:
            raise ValueError(f"Test example has no official label: {example_id}")
        tokens = [line.split("\t", 1)[0] for line in lines[1:] if "\t" in line]
        text = " ".join(token for token in tokens if token).strip()
        if not text:
            raise ValueError(f"Empty text for test example {example_id}")
        examples.append(
            SentimentExample(
                example_id=example_id,
                text=text,
                label=labels[example_id],
                original_split="test",
            )
        )
    if len(examples) != len(labels):
        raise ValueError("Official test text and label counts differ")
    return examples


def load_hinglish_split(archive_path: str | Path, split: str) -> list[SentimentExample]:
    """Load one official split without changing its membership or ordering."""
    if split not in SUPPORTED_SPLITS:
        raise ValueError(f"Unsupported split {split!r}; expected one of {SUPPORTED_SPLITS}")
    archive_path = Path(archive_path)
    prefix = "Semeval_2020_task9_data/Hinglish/"
    if split == "train":
        member = prefix + "Hinglish_train_14k_split_conll.txt"
        return _parse_conll_records(_read_archive_member(archive_path, member), split)
    if split == "validation":
        member = prefix + "Hinglish_dev_3k_split_conll.txt"
        return _parse_conll_records(_read_archive_member(archive_path, member), split)
    return _parse_test_records(
        _read_archive_member(archive_path, prefix + "Hinglish_test_unalbelled_conll_updated.txt"),
        _read_archive_member(archive_path, prefix + "Hinglish_test_labels.txt"),
    )


def validate_split_integrity(splits: dict[str, list[SentimentExample]]) -> None:
    """Reject duplicate IDs or any train/evaluation ID overlap."""
    for split, examples in splits.items():
        ids = [example.example_id for example in examples]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate example IDs in {split} split")
    train_ids = {example.example_id for example in splits.get("train", [])}
    for split in ("validation", "test"):
        overlap = train_ids.intersection(example.example_id for example in splits.get(split, []))
        if overlap:
            raise ValueError(f"Training/evaluation leakage detected in {split}: {sorted(overlap)[:3]}")
