import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class RowInfo:
    period: str
    serial0: int
    line_no: int
    row: dict[str, str]


def period_to_serial(period: str, line_no: int) -> int:
    raw = period.strip()
    if len(raw) < 12 or not raw.isdigit():
        raise ValueError(f"line {line_no}: invalid period format '{period}'")

    date_str = raw[:8]
    game_no = int(raw[-4:])

    try:
        dt = datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError(f"line {line_no}: invalid date in period '{period}'") from exc

    if game_no < 1 or game_no > 2880:
        raise ValueError(f"line {line_no}: game number out of range in period '{period}'")

    return dt.toordinal() * 2880 + (game_no - 1)


def sort_data_upto_missing_period(input_csv: Path, output_csv: Path) -> tuple[int, int, int, str | None]:
    parsed: list[RowInfo] = []
    parse_errors = 0

    with input_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "period" not in reader.fieldnames:
            raise ValueError("CSV must contain a 'period' column")

        for line_no, row in enumerate(reader, start=2):
            period = (row.get("period") or "").strip()
            if not period:
                parse_errors += 1
                continue

            try:
                parsed.append(
                    RowInfo(
                        period=period,
                        serial0=period_to_serial(period, line_no),
                        line_no=line_no,
                        row=row,
                    )
                )
            except ValueError:
                parse_errors += 1

    if not parsed:
        raise ValueError("No valid rows found in input CSV")

    # Input file is newest->oldest, so reverse to process from oldest->newest.
    oldest_to_newest = list(reversed(parsed))

    # Keep first occurrence while scanning oldest->newest to avoid duplicate period noise.
    deduped: list[RowInfo] = []
    seen = set()
    duplicates_dropped = 0
    for item in oldest_to_newest:
        if item.period in seen:
            duplicates_dropped += 1
            continue
        seen.add(item.period)
        deduped.append(item)

    if not deduped:
        raise ValueError("No rows left after deduplication")

    contiguous: list[RowInfo] = [deduped[0]]
    first_gap_after: str | None = None

    for prev_item, curr_item in zip(deduped, deduped[1:]):
        diff = curr_item.serial0 - prev_item.serial0
        if diff == 1:
            contiguous.append(curr_item)
            continue

        first_gap_after = prev_item.period
        break

    # Ensure explicit sort by period sequence in ascending order.
    contiguous_sorted = sorted(contiguous, key=lambda x: x.serial0)

    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["period", "number", "color"])
        writer.writeheader()
        for item in contiguous_sorted:
            writer.writerow(
                {
                    "period": item.row.get("period", "").strip(),
                    "number": item.row.get("number", "").strip(),
                    "color": item.row.get("color", "").strip(),
                }
            )

    return len(parsed), len(contiguous_sorted), duplicates_dropped, first_gap_after


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sort CSV from oldest records up to first missing period and drop date_folder column."
    )
    parser.add_argument("input_csv", help="Input CSV path")
    parser.add_argument(
        "--output",
        help="Output CSV path (default: <input_stem>_sorted_upto_gap.csv in same folder)",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    if not input_csv.exists():
        print(f"ERROR: input file not found: {input_csv}")
        return 1

    if args.output:
        output_csv = Path(args.output)
    else:
        output_csv = input_csv.with_name(f"{input_csv.stem}_sorted_upto_gap.csv")

    try:
        rows_read, rows_written, duplicates_dropped, first_gap_after = sort_data_upto_missing_period(
            input_csv=input_csv,
            output_csv=output_csv,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Input: {input_csv}")
    print(f"Rows read: {rows_read}")
    print(f"Duplicates dropped: {duplicates_dropped}")
    print(f"Rows written: {rows_written}")
    if first_gap_after:
        print(f"Stopped at first gap after period: {first_gap_after}")
    else:
        print("No gap found; wrote all rows.")
    print(f"Output: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
