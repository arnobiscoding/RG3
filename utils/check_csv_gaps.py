import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ParsedRow:
    period: str
    date_ordinal: int
    game_no: int
    middle: str
    line_no: int

    @property
    def serial0(self) -> int:
        # Zero-based serial index used for simple gap math.
        return self.date_ordinal * 2880 + (self.game_no - 1)


def parse_period(period: str, line_no: int) -> ParsedRow:
    raw = period.strip()
    if len(raw) < 12 or not raw.isdigit():
        raise ValueError(f"line {line_no}: invalid period format '{period}'")

    date_str = raw[:8]
    middle = raw[8:-4]
    game_str = raw[-4:]

    try:
        dt = datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"line {line_no}: invalid period date '{date_str}'") from exc

    game_no = int(game_str)
    if game_no < 1 or game_no > 2880:
        raise ValueError(f"line {line_no}: game number out of range '{game_str}'")

    return ParsedRow(
        period=raw,
        date_ordinal=dt.toordinal(),
        game_no=game_no,
        middle=middle,
        line_no=line_no,
    )


def serial_to_date_game(serial0: int) -> tuple[int, int]:
    date_ordinal = serial0 // 2880
    game_no = (serial0 % 2880) + 1
    return date_ordinal, game_no


def build_period(date_ordinal: int, middle: str, game_no: int) -> str:
    date_str = datetime.fromordinal(date_ordinal).strftime("%Y%m%d")
    return f"{date_str}{middle}{game_no:04d}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a Wingo CSV for missing period rows."
    )
    parser.add_argument("csv_path", help="Path to CSV file")
    parser.add_argument(
        "--max-missing-show",
        type=int,
        default=50,
        help="Maximum number of missing periods to print (default: 50)",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"ERROR: file not found: {csv_path}")
        return 1

    parsed_rows = []
    parse_errors = []

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if "period" not in (reader.fieldnames or []):
            print("ERROR: CSV must have a 'period' column")
            return 1

        # DictReader data starts on file line 2.
        for index, row in enumerate(reader, start=2):
            period = (row.get("period") or "").strip()
            if not period:
                parse_errors.append(f"line {index}: empty period")
                continue

            try:
                parsed_rows.append(parse_period(period, index))
            except ValueError as exc:
                parse_errors.append(str(exc))

    if not parsed_rows:
        print("ERROR: no valid rows found")
        if parse_errors:
            print(f"Parse errors: {len(parse_errors)}")
        return 1

    # Read from bottom as requested (oldest -> newest).
    bottom_up = list(reversed(parsed_rows))

    deduped = []
    seen_periods = set()
    duplicates_dropped = 0
    middle_counter = Counter()

    for row in bottom_up:
        if row.period in seen_periods:
            duplicates_dropped += 1
            continue
        seen_periods.add(row.period)
        deduped.append(row)
        middle_counter[row.middle] += 1

    dominant_middle = middle_counter.most_common(1)[0][0]

    gaps = []
    anomalies = []
    total_missing = 0
    missing_to_print = []

    for prev_row, curr_row in zip(deduped, deduped[1:]):
        diff = curr_row.serial0 - prev_row.serial0

        if diff == 1:
            continue
        if diff <= 0:
            anomalies.append(
                "Out-of-order or duplicate after dedupe: "
                f"{prev_row.period} (line {prev_row.line_no}) -> "
                f"{curr_row.period} (line {curr_row.line_no})"
            )
            continue

        missing_count = diff - 1
        total_missing += missing_count
        gaps.append(
            (
                prev_row.period,
                prev_row.line_no,
                curr_row.period,
                curr_row.line_no,
                missing_count,
            )
        )

        # Capture only first N missing periods for readable output.
        remaining_slots = max(0, args.max_missing_show - len(missing_to_print))
        if remaining_slots:
            for serial0 in range(prev_row.serial0 + 1, curr_row.serial0):
                date_ord, game_no = serial_to_date_game(serial0)
                missing_to_print.append(build_period(date_ord, dominant_middle, game_no))
                if len(missing_to_print) >= args.max_missing_show:
                    break

    print(f"File: {csv_path}")
    print(f"Rows read: {len(parsed_rows)}")
    print(f"Unique periods checked (bottom->top): {len(deduped)}")
    print(f"Duplicates dropped: {duplicates_dropped}")
    print(f"Parse errors: {len(parse_errors)}")

    if parse_errors:
        print("\nFirst parse errors:")
        for err in parse_errors[:10]:
            print(f"- {err}")

    if not gaps and not anomalies:
        print("\nResult: No gaps found. Sequence is continuous.")
        return 0

    print("\nResult: Gaps or sequence anomalies found.")

    if gaps:
        print(f"Gap segments: {len(gaps)}")
        print(f"Total missing periods: {total_missing}")
        print("\nGap details:")
        for older_period, older_line, newer_period, newer_line, missing_count in gaps[:20]:
            print(
                "- Missing "
                f"{missing_count} between {older_period} (line {older_line}) "
                f"and {newer_period} (line {newer_line})"
            )
        if len(gaps) > 20:
            print(f"- ... and {len(gaps) - 20} more gap segments")

    if missing_to_print:
        print(f"\nFirst {len(missing_to_print)} missing period values:")
        for period in missing_to_print:
            print(f"- {period}")

    if anomalies:
        print(f"\nSequence anomalies: {len(anomalies)}")
        for item in anomalies[:20]:
            print(f"- {item}")
        if len(anomalies) > 20:
            print(f"- ... and {len(anomalies) - 20} more anomalies")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
