import os
import io
from tensorboard.backend.event_processing import event_accumulator
from PIL import Image

import argparse

ROOT = os.path.dirname(os.path.dirname(__file__))

parser = argparse.ArgumentParser()
parser.add_argument('--runs-dir', default=os.path.join(ROOT, 'runs'))
args = parser.parse_args()
RUNS_DIR = args.runs_dir
OUT_DIR = os.path.join(ROOT, 'reports')
IM_DIR = os.path.join(OUT_DIR, 'images')
os.makedirs(IM_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

report_lines = []
report_lines.append('# TensorBoard Report')
report_lines.append('')
report_lines.append('Generated from runs under `runs/`')
report_lines.append('')

if not os.path.isdir(RUNS_DIR):
    report_lines.append('No `runs/` directory found.')
else:
    runs = [d for d in os.listdir(RUNS_DIR) if os.path.isdir(os.path.join(RUNS_DIR, d))]
    if not runs:
        report_lines.append('No runs found in `runs/`.')
    for run in runs:
        run_path = os.path.join(RUNS_DIR, run)
        report_lines.append(f'## Run: {run}')
        report_lines.append('')
        # find event files
        event_files = [os.path.join(run_path, f) for f in os.listdir(run_path) if f.startswith('events')]
        if not event_files:
            report_lines.append('_No event files found in this run._')
            continue
        # use EventAccumulator on run_path
        ea = event_accumulator.EventAccumulator(run_path, size_guidance={
            event_accumulator.COMPRESSED_HISTOGRAMS: 0,
            event_accumulator.IMAGES: 0,
            event_accumulator.AUDIO: 0,
            event_accumulator.SCALARS: 0,
            event_accumulator.HISTOGRAMS: 0,
            })
        try:
            ea.Reload()
        except Exception as e:
            report_lines.append(f'Failed to load events: {e}')
            continue
        tags = ea.Tags()
        scalars = tags.get('scalars', [])
        images = tags.get('images', [])
        report_lines.append('### Scalars')
        if not scalars:
            report_lines.append('_No scalar tags found._')
        else:
            for tag in scalars:
                try:
                    vals = ea.Scalars(tag)
                    if vals:
                        last = vals[-1]
                        report_lines.append(f'- `{tag}`: step={last.step}, value={last.value:.6g}')
                except Exception:
                    report_lines.append(f'- `{tag}`: failed to read')
        report_lines.append('')
        report_lines.append('### Images')
        if not images:
            report_lines.append('_No image tags found._')
        else:
            for tag in images:
                try:
                    img_events = ea.Images(tag)
                    for i,ev in enumerate(img_events[:3]):
                        b = ev.encoded_image_string
                        try:
                            im = Image.open(io.BytesIO(b))
                            outname = f'{run}_{tag.replace("/","__")}_{i}.png'
                            outpath = os.path.join(IM_DIR, outname)
                            im.save(outpath)
                            report_lines.append(f'- `{tag}` image #{i}: ![img]({os.path.relpath(outpath, ROOT)})')
                        except Exception as e:
                            report_lines.append(f'- `{tag}` image #{i}: failed to decode ({e})')
                except Exception as e:
                    report_lines.append(f'- `{tag}`: failed to read images ({e})')
        report_lines.append('')

# list model files
report_lines.append('## Model files')
models = [f for f in os.listdir(ROOT) if f.endswith('.pth') or f.endswith('.pt')]
if models:
    for m in models:
        report_lines.append(f'- {m}')
else:
    report_lines.append('_No model files found in project root._')

report_md = os.path.join(OUT_DIR, 'report.md')
with open(report_md, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report_lines))

print('Report written to', report_md)
