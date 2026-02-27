#!/usr/bin/env python3
import argparse
import csv
import html
import random
import shutil
from pathlib import Path
from urllib.parse import quote


# -----------------------------
# Helpers
# -----------------------------

def safe_copy(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)
        return dst
    stem, suf = dst.stem, dst.suffix
    k = 1
    while True:
        cand = dst.with_name(f"{stem}__{k}{suf}")
        if not cand.exists():
            shutil.copy2(src, cand)
            return cand
        k += 1


def make_audio_url(base: str, rel_path: Path) -> str:
    parts = [quote(p) for p in rel_path.as_posix().split('/') if p != '']
    if not base.endswith('/'):
        base += '/'
    return base + '/'.join(parts)


def write_html(out_path: Path, wav_list: list, set_size: int = 5):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Intelligibility Test</title>
<style>
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }
h1 { margin: 0 0 12px; }
h2 { margin: 24px 0 8px; }
table.tests { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
.tests td, .tests th { border: 1px solid #ddd; padding: 8px; vertical-align: middle; }
.tests tr:nth-child(even){ background: #fafafa; }
.tests th { background: #f2f2f2; text-align: left; }
audio { width: 260px; }
.select-cell select { width: 160px; }
.center { text-align: center; }
.muted { color: #666; font-size: 0.95rem; }
.hr { height: 1px; background: #eee; margin: 16px 0; }
.note { background: #fff9c4; padding: 8px 12px; border-radius: 8px; }
</style>
</head>
<body>
<h1>Intelligibility Test</h1>
<p class="note">For each question, listen to both clips and decide which one is more intelligible (easier to understand). Then mark your confidence.</p>
<div class="hr"></div>
""")
        num_sets = len(wav_list) // set_size
        for i in range(num_sets):
            f.write(f"<h2>Set {i+1}</h2>\n")
            f.write('<table class="tests">\n')
            f.write("\t<thead>\n\t\t<tr>\n")
            headers = [
                "QID", "  Clip A  ", "  Clip B  ", "Which is more intelligible?",
                "Not at all confident", "|", "Somewhat confident", "|",
                "Quite a bit confident", "|", "Extremely confident"
            ]
            for h in headers:
                f.write(f"\t\t\t<th>{html.escape(h)}</th>\n")
            f.write("\t\t</tr>\n\t</thead>\n\t<tbody>\n")

            for j in range(set_size):
                index = i * set_size + j
                row = wav_list[index]
                wav_id = row["id"]
                wav_a = row["wav_fpath_a"]
                wav_b = row["wav_fpath_b"]

                f.write("\t\t<tr>\n")
                f.write(f"\t\t\t<td>Q{index+1}</td>\n")

                # Clip A
                f.write("\t\t\t<td>\n\t\t\t\t<audio controls preload=\"none\">\n")
                f.write(f"\t\t\t\t\t<source preload=\"none\" src=\"{html.escape(wav_a)}\" type=\"audio/wav\" />\n")
                f.write("\t\t\t\t</audio>\n\t\t\t</td>\n")

                # Clip B
                f.write("\t\t\t<td>\n\t\t\t\t<audio controls preload=\"none\">\n")
                f.write(f"\t\t\t\t\t<source preload=\"none\" src=\"{html.escape(wav_b)}\" type=\"audio/wav\" />\n")
                f.write("\t\t\t\t</audio>\n\t\t\t</td>\n")

                # A or B dropdown
                f.write('\t\t\t<td class="select-cell">\n')
                f.write(f'\t\t\t\t<select class="form-control overall" name="{html.escape(wav_id)}_Answer_overall">\n')
                f.write('\t\t\t\t\t<option selected value="0">- select one -</option>\n')
                f.write('\t\t\t\t\t<option value="1">Clip A</option>\n')
                f.write('\t\t\t\t\t<option value="-1">Clip B</option>\n')
                f.write('\t\t\t\t</select>\n')
                f.write("\t\t\t</td>\n")

                # Confidence scale 1..7
                for val in range(1, 8):
                    f.write(f'\t\t\t<td class="center"><input name="{html.escape(wav_id)}" type="radio" value="{val}" /></td>\n')

                f.write("\t\t</tr>\n")
            f.write("\t</tbody>\n</table>\n")

        f.write("""<p class="muted">Generated automatically.</p>
</body>
</html>""")


def main():
    parser = argparse.ArgumentParser(description="Build Intelligibility A/B HTML from CSV and copy audio samples.")
    parser.add_argument("--csv", type=Path, required=True,
                        help="Path to CSV with columns: tvtsyn, ours")
    parser.add_argument("--out_dir", type=Path, default=Path("."),
                        help="Directory in which to write index.html")
    parser.add_argument("--samples_root", type=Path, default=Path("../Samples/Intelligibility"),
                        help="Where to copy audio samples")
    parser.add_argument("--public_base", type=str, required=True,
                        help="Base URL that maps to samples_root on GitHub Pages, e.g., "
                             "'https://anonymized0826.github.io/perceptual_test/UserStudy/IS26/Samples/Intelligibility/'")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--set_size", type=int, default=5, help="Questions per set/section")
    args = parser.parse_args()

    random.seed(args.seed)

    samples_root = args.samples_root.resolve()
    tvtsyn_dir = samples_root / "vc" / "TVTSyn"
    ours_dir = samples_root / "vc" / "Ours"

    wav_list = []

    with args.csv.open("r", encoding="utf-8") as fin:
        reader = csv.DictReader(fin)
        for row in reader:
            tvtsyn_path = Path(row["TVTSyn"]).expanduser()
            ours_path = Path(row["Ours"]).expanduser()

            if not tvtsyn_path.exists():
                raise FileNotFoundError(f"Missing TVTSyn file: {tvtsyn_path}")
            if not ours_path.exists():
                raise FileNotFoundError(f"Missing Ours file: {ours_path}")

            tvtsyn_dst = safe_copy(tvtsyn_path, tvtsyn_dir / tvtsyn_path.name)
            ours_dst = safe_copy(ours_path, ours_dir / ours_path.name)

            url_tvtsyn = make_audio_url(args.public_base, tvtsyn_dst.relative_to(samples_root))
            url_ours = make_audio_url(args.public_base, ours_dst.relative_to(samples_root))

            # Randomly assign TVTSyn/Ours to A/B to avoid order bias.
            # wav_id encodes the assignment: TAO = TVTSyn→A, Ours→B; OAT = Ours→A, TVTSyn→B
            if random.random() < 0.5:
                url_a, url_b = url_tvtsyn, url_ours
                wav_id = f"INT_TAO_{tvtsyn_path.stem}"
            else:
                url_a, url_b = url_ours, url_tvtsyn
                wav_id = f"INT_OAT_{ours_path.stem}"

            wav_list.append({
                "id": wav_id,
                "wav_fpath_a": url_a,
                "wav_fpath_b": url_b,
            })

    random.shuffle(wav_list)
    out_html = args.out_dir / "index.html"
    write_html(out_html, wav_list, set_size=args.set_size)

    print(f"Wrote HTML: {out_html}")
    print(f"Samples root: {samples_root}")
    print(f"Total questions: {len(wav_list)} | Sets of {args.set_size}: {len(wav_list)//args.set_size}")


if __name__ == "__main__":
    main()
