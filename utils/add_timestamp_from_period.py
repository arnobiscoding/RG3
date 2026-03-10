import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path


def period_to_utc_timestamp(period: str, line_no: int) -> datetime:
    raw = period.strip()
    if len(raw) < 12 or not raw.isdigit():
        raise ValueError(f"line {line_no}: invalid period format '{period}'")

    date_str = raw[:8]
    round_no = int(raw[-4:])

    if round_no < 1 or round_no > 2880:
        raise ValueError(f"line {line_no}: round number out of range '{round_no:04d}'")

    try:
        date_utc = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"line {line_no}: invalid date in period '{date_str}'") from exc

    # Round 0001 is 00:00:00 UTC; each next round is +30 seconds.
    offset_seconds = (round_no - 1) * 30
    return date_utc + timedelta(seconds=offset_seconds)


def add_timestamp_column(input_csv: Path, output_csv: Path) -> tuple[int, int]:
    rows_written = 0
    bad_rows = 0

    with input_csv.open("r", encoding="utf-8", newline="") as in_fh:
        reader = csv.DictReader(in_fh)
        if not reader.fieldnames or "period" not in reader.fieldnames:
            raise ValueError("CSV must contain a 'period' column")

        output_fields = list(reader.fieldnames)
        if "timestamp" not in output_fields:
            output_fields.append("timestamp")

        with output_csv.open("w", encoding="utf-8", newline="") as out_fh:
            writer = csv.DictWriter(out_fh, fieldnames=output_fields)
            writer.writeheader()

            for line_no, row in enumerate(reader, start=2):
                period = (row.get("period") or "").strip()
                if not period:
                    bad_rows += 1
                    continue

                try:
                    ts_utc = period_to_utc_timestamp(period, line_no)
                except ValueError:
                    bad_rows += 1
                    continue

                row_out = dict(row)
                # ISO-8601 UTC timestamp with Z suffix.
                row_out["timestamp"] = ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                writer.writerow(row_out)
                rows_written += 1

    return rows_written, bad_rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add UTC timestamp column to CSV based on period date + round number."
    )
    parser.add_argument("input_csv", help="Input CSV path")
    parser.add_argument(
        "--output",
        help="Output CSV path (default: <input_stem>_with_timestamp.csv in same folder)",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    if not input_csv.exists():
        print(f"ERROR: input file not found: {input_csv}")
        return 1

    if args.output:
        output_csv = Path(args.output)
    else:
        output_csv = input_csv.with_name(f"{input_csv.stem}_with_timestamp.csv")

    try:
        rows_written, bad_rows = add_timestamp_column(input_csv=input_csv, output_csv=output_csv)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Input: {input_csv}")
    print(f"Rows written: {rows_written}")
    print(f"Rows skipped (invalid period): {bad_rows}")
    print(f"Output: {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
