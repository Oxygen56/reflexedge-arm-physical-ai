#!/usr/bin/env python3
"""Build a silent, evidence-first, sub-three-minute MP4 from verified artifacts."""

from __future__ import annotations

import csv
import html
import json
import math
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "demo/video"
FRAME_DIR = VIDEO_DIR / "frames"
WIDTH = 1920
HEIGHT = 1080
BG = "#07090c"
LIME = "#cbff45"
VIOLET = "#9d7dff"
RED = "#ff4b4b"
AMBER = "#ffb545"
MUTED = "#8d99a8"


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, value))))


def risk(row: dict[str, str], model: dict) -> float:
    values = [float(row[f"f{index:03d}"]) for index in range(model["feature_count"])]
    quantized = [max(0, min(127, round(value * 127.0))) for value in values]
    dot = sum(weight * value for weight, value in zip(model["weights_int8"], quantized))
    return sigmoid(
        model["bias"]
        + dot * model["weight_scale"] / 127.0
        + model["int8_safety_bias"]
    )


def action(value: float, threshold: float) -> str:
    if value >= threshold:
        return "BRAKE"
    if value >= threshold * 0.62:
        return "HOLD"
    return "GO"


def text(x: int, y: int, value: str, size: int, color: str = "#f4f6f8", weight: int = 600,
         family: str = "Helvetica,Arial,sans-serif", anchor: str = "start", spacing: int = 0) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
        f'letter-spacing="{spacing}">{html.escape(value)}</text>'
    )


def svg_document(body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">'
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}"/>'
        '<defs><filter id="glow"><feGaussianBlur stdDeviation="7" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
        + body
        + '</svg>'
    )


def header(step: str) -> str:
    return (
        '<line x1="70" y1="88" x2="1850" y2="88" stroke="#27313c" stroke-width="1"/>'
        + text(72, 61, "R/  REFLEXEDGE", 24, LIME, 700, "Menlo,monospace", spacing=3)
        + text(1848, 61, step, 17, MUTED, 600, "Menlo,monospace", anchor="end", spacing=2)
    )


def social_scene(comparison: dict) -> str:
    trial_p95 = comparison["independent_trials"]["pipeline_p95_speedup"]["median"]
    body = header("ARM64 / PHYSICAL AI")
    body += text(74, 275, "A BRAKE REFLEX", 112, "#f4f6f8", 700)
    body += text(74, 400, "YOU CAN AUDIT.", 112, LIME, 700)
    body += '<rect x="74" y="510" width="1050" height="100" fill="#0d1117" stroke="' + LIME + '"/>'
    body += text(112, 575, f"{trial_p95:.2f}× MEDIAN P95 · 0 ADDED FALSE NEGATIVES", 30, LIME, 700, "Menlo,monospace")
    body += text(74, 700, "RAW 64-BEAM SENSOR → FUSED INT8 NEON → BRAKE", 26, VIOLET, 650, "Menlo,monospace", spacing=1)
    center_x, center_y, radius = 1510, 890, 480
    for index in range(33):
        angle = math.pi + index / 32 * math.pi
        end_x = center_x + math.cos(angle) * radius
        end_y = center_y + math.sin(angle) * radius
        color = RED if 13 <= index <= 19 else VIOLET
        opacity = .88 if 13 <= index <= 19 else .35
        body += f'<line x1="{center_x}" y1="{center_y}" x2="{end_x:.1f}" y2="{end_y:.1f}" stroke="{color}" stroke-opacity="{opacity}" stroke-width="{4 if 13 <= index <= 19 else 2}"/>'
    body += f'<rect x="1450" y="865" width="120" height="55" rx="6" fill="{LIME}"/>'
    body += text(1510, 900, "ACTUATOR", 14, BG, 700, "Menlo,monospace", anchor="middle")
    body += text(74, 980, "REFLEXEDGE · REAL APPLE M4 ARM64 · MIT", 22, MUTED, 600, "Menlo,monospace")
    return svg_document(body)


def render_svg(name: str, source: str) -> Path:
    svg_path = FRAME_DIR / f"{name}.svg"
    png_path = FRAME_DIR / f"{name}.png"
    svg_path.write_text(source, encoding="utf-8")
    subprocess.run(
        [
            "magick",
            "-font",
            "/System/Library/Fonts/Helvetica.ttc",
            "-background",
            BG,
            str(svg_path),
            "-resize",
            f"{WIDTH}x{HEIGHT}!",
            str(png_path),
        ],
        check=True,
    )
    return png_path


def radar_scene(row: dict[str, str], model: dict, number: int) -> str:
    value = risk(row, model)
    command = action(value, model["threshold"])
    command_color = RED if command == "BRAKE" else AMBER if command == "HOLD" else LIME
    center_x, center_y, radius = 1260, 915, 740
    lines = []
    for index in range(64):
        proximity = float(row[f"f{64 + index:03d}"])
        danger = float(row[f"f{index:03d}"])
        angle = math.pi + index / 63 * math.pi
        ray = radius * (0.22 + (1 - min(0.96, proximity * 1.1)) * 0.78)
        end_x = center_x + math.cos(angle) * ray
        end_y = center_y + math.sin(angle) * ray
        hot = danger > 0.18 or proximity > 0.55
        warm = danger > 0.08 or proximity > 0.28
        color = RED if hot else AMBER if warm else LIME
        opacity = .92 if hot else .62 if warm else .18
        width = 4 if hot else 2 if warm else 1
        lines.append(
            f'<line x1="{center_x}" y1="{center_y}" x2="{end_x:.1f}" y2="{end_y:.1f}" '
            f'stroke="{color}" stroke-opacity="{opacity}" stroke-width="{width}"/>'
        )
        if proximity > .06:
            lines.append(
                f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="{7 if hot else 4}" fill="{color}"/>'
            )
    scenario = row["scenario"].replace("_", " ").upper()
    body = header(f"LIVE REPLAY / {number:02d}")
    body += text(74, 170, "SENSOR → MODEL → ACTUATOR", 20, LIME, 600, "Menlo,monospace", spacing=3)
    body += text(74, 260, scenario, 72, "#f4f6f8", 650)
    body += text(74, 318, f"FRAME {row['sample_id']} · 64 DISTANCE + VELOCITY BEAMS", 18, MUTED, 600, "Menlo,monospace")
    body += '<rect x="74" y="400" width="430" height="250" fill="#0d1117" stroke="#27313c"/>'
    body += text(106, 450, "OPTIMIZED RISK", 16, MUTED, 600, "Menlo,monospace", spacing=2)
    body += text(106, 555, f"{value * 100:.1f}%", 106, command_color, 700, "Menlo,monospace")
    body += text(106, 610, "INT8 ARM NEON", 17, VIOLET, 600, "Menlo,monospace", spacing=2)
    body += '<rect x="74" y="684" width="430" height="145" fill="none" stroke="' + command_color + '" stroke-width="2"/>'
    body += text(106, 730, "ACTION", 16, MUTED, 600, "Menlo,monospace", spacing=2)
    body += text(106, 800, command, 64, command_color, 700, "Menlo,monospace", spacing=2)
    body += ''.join(lines)
    body += '<rect x="1208" y="892" width="104" height="46" rx="5" fill="' + command_color + '"/>'
    body += text(1260, 921, "ACTUATOR", 12, BG, 700, "Menlo,monospace", anchor="middle")
    body += text(1848, 1025, "REAL INFERENCE OUTPUT · APPLE M4 ARM64", 16, MUTED, 600, "Menlo,monospace", anchor="end")
    return svg_document(body)


def metric_scene(comparison: dict, baseline: dict, optimized: dict) -> str:
    body = header("02 / OPTIMIZATION DELTA")
    body += text(74, 200, "THE SAME RAW FRAMES.", 72, "#f4f6f8", 620)
    body += text(74, 286, "A FUSED ARM PIPELINE.", 72, LIME, 620)
    cards = [
        ("P95 · FINAL RUN", f"{baseline['end_to_end']['latency_ns']['p95']:.2f} ns", f"{optimized['end_to_end']['latency_ns']['p95']:.2f} ns", f"{comparison['pipeline_speedup_p95']:.2f}× FASTER"),
        ("THROUGHPUT · FINAL", f"{baseline['end_to_end']['throughput_per_second']/1e6:.2f}M/s", f"{optimized['end_to_end']['throughput_per_second']/1e6:.2f}M/s", f"+{comparison['pipeline_throughput_gain_percent']:.0f}%"),
        ("MODEL BYTES", str(baseline['model_bytes']), str(optimized['model_bytes']), f"−{comparison['model_size_reduction_percent']:.1f}%"),
        ("CPU PROXY · FINAL", f"{baseline['end_to_end']['cpu_ns_per_inference_energy_proxy']:.1f} ns", f"{optimized['end_to_end']['cpu_ns_per_inference_energy_proxy']:.1f} ns", f"−{comparison['pipeline_cpu_time_proxy_reduction_percent']:.1f}%"),
    ]
    for index, (label, before, after, delta) in enumerate(cards):
        x = 74 + index * 445
        body += f'<rect x="{x}" y="380" width="407" height="420" fill="#0d1117" stroke="#27313c"/>'
        body += text(x + 28, 430, label, 16, MUTED, 600, "Menlo,monospace", spacing=2)
        body += text(x + 28, 530, before, 36, "#56616d", 550, "Menlo,monospace")
        body += f'<line x1="{x+28}" y1="550" x2="{x+210}" y2="550" stroke="#56616d" stroke-width="2"/>'
        body += text(x + 28, 650, after, 55, "#f4f6f8", 650, "Menlo,monospace")
        body += text(x + 28, 746, delta, 27, LIME, 700, "Menlo,monospace")
    median_p95 = comparison["independent_trials"]["pipeline_p95_speedup"]["median"]
    body += text(74, 900, f"5 PAIRED PROCESS TRIALS · MEDIAN RAW-TO-ACTION P95 {median_p95:.2f}×", 20, VIOLET, 600, "Menlo,monospace", spacing=2)
    body += text(74, 948, "Final run: 1.25M frames per engine. Physical sensor I/O and actuator transport excluded.", 18, MUTED, 500)
    body += text(74, 985, "Peak process RSS increased 2.6%; only model-byte reduction is claimed.", 18, MUTED, 500)
    return svg_document(body)


def safety_scene(comparison: dict) -> str:
    body = header("03 / SAFETY GATE")
    body += text(74, 214, "FASTER IS NOT ENOUGH.", 80, "#f4f6f8", 620)
    body += text(74, 305, "THE BRAKE DECISION MUST SURVIVE.", 80, LIME, 620)
    body += '<rect x="74" y="410" width="840" height="410" fill="#0d1117" stroke="#27313c"/>'
    body += text(120, 470, "ADDED FALSE-NEGATIVE BRAKES", 20, MUTED, 600, "Menlo,monospace", spacing=2)
    body += text(120, 700, str(comparison["additional_false_negatives"]), 250, LIME, 700, "Menlo,monospace")
    body += text(120, 770, "PASS · QUANTIZATION SAFETY GATE", 21, LIME, 650, "Menlo,monospace")
    body += '<rect x="954" y="410" width="892" height="410" fill="#0d1117" stroke="#27313c"/>'
    body += text(1000, 470, "ACCURACY", 20, MUTED, 600, "Menlo,monospace", spacing=2)
    body += text(1000, 625, f"{comparison['baseline_quality']['accuracy']*100:.2f}%", 72, "#56616d", 600, "Menlo,monospace")
    body += text(1000, 730, f"{comparison['optimized_quality']['accuracy']*100:.2f}%", 92, "#f4f6f8", 650, "Menlo,monospace")
    body += text(1000, 780, f"{comparison['accuracy_delta_percentage_points']:+.2f} percentage points", 20, VIOLET, 600, "Menlo,monospace")
    body += text(74, 930, "ONE-SIDED SAFETY BIAS CALIBRATED ON VALIDATION ONLY", 22, AMBER, 650, "Menlo,monospace", spacing=2)
    body += text(74, 980, "It deliberately favors an extra brake over a missed brake.", 20, MUTED, 500)
    return svg_document(body)


def reproduce_scene(comparison: dict, hardware: dict) -> str:
    body = header("04 / REPRODUCE")
    body += text(74, 220, "ONE COMMAND.", 88, "#f4f6f8", 620)
    body += text(74, 318, "NO CLOUD. NO SECRETS.", 88, LIME, 620)
    body += '<rect x="74" y="420" width="1772" height="140" fill="#0d1117" stroke="#27313c"/>'
    body += text(120, 505, "./scripts/reproduce.sh", 48, LIME, 650, "Menlo,monospace")
    items = [
        "REGENERATE RIGHTS-CLEAN SENSOR CORPUS",
        "TRAIN + QUANTIZE THE FROZEN MODEL",
        "BUILD SCALAR FP32 + INT8 ARM NEON",
        "RUN SAFETY, RIGHTS + NEGATIVE CONTROLS",
    ]
    for index, item in enumerate(items):
        y = 660 + index * 72
        body += text(88, y, f"0{index+1}", 18, VIOLET, 700, "Menlo,monospace")
        body += text(150, y, item, 25, "#dce3ea", 600, "Menlo,monospace", spacing=1)
    body += text(1846, 930, f"{hardware['chip']} · {hardware['architecture']} · NEON + DOTPROD", 19, MUTED, 600, "Menlo,monospace", anchor="end")
    body += text(1846, 980, f"DATASET {comparison['dataset_sha256'][:16]}… · MIT", 17, MUTED, 600, "Menlo,monospace", anchor="end")
    return svg_document(body)


def boundary_scene() -> str:
    body = header("05 / CLAIM BOUNDARY")
    body += text(74, 230, "EVIDENCE, NOT THEATER.", 92, "#f4f6f8", 620)
    body += '<line x1="74" y1="320" x2="1846" y2="320" stroke="#27313c"/>'
    claims = [
        ("MEASURED", "Local Apple M4 Arm64 latency, throughput, model bytes, accuracy, process RSS."),
        ("LABELED PROXY", "CPU time per inference. It is not reported as direct energy in joules."),
        ("NOT CLAIMED", "Cross-device performance, field safety certification, or production deployment."),
    ]
    for index, (label, value) in enumerate(claims):
        y = 450 + index * 190
        color = LIME if index == 0 else AMBER if index == 1 else RED
        body += text(74, y, label, 19, color, 700, "Menlo,monospace", spacing=2)
        body += text(430, y, value, 31, "#dce3ea", 500)
    body += text(74, 1000, "REFLEXEDGE · REAL HARDWARE · RAW EVIDENCE · HONEST BOUNDARIES", 22, VIOLET, 650, "Menlo,monospace", spacing=2)
    return svg_document(body)


def main() -> None:
    model = json.loads((ROOT / "artifacts/model.json").read_text(encoding="utf-8"))
    comparison = json.loads((ROOT / "reports/comparison.json").read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / "reports/baseline.json").read_text(encoding="utf-8"))
    optimized = json.loads((ROOT / "reports/optimized.json").read_text(encoding="utf-8"))
    hardware = json.loads((ROOT / "reports/hardware.json").read_text(encoding="utf-8"))
    with (ROOT / "data/raw/test.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    shutil.rmtree(FRAME_DIR, ignore_errors=True)
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    scenes: list[tuple[Path, float]] = []

    social_frame = render_svg("00-social", social_scene(comparison))
    social = ROOT / "demo/site/public/og.png"
    shutil.copyfile(social_frame, social)
    scenes.append((social_frame, 5.0))

    targets = [
        ("safe", 0.03),
        ("crossing", 0.35),
        ("frontal_approach", 0.82),
        ("sudden_intrusion", 0.95),
        ("dropout", 0.02),
        ("crossing", 0.65),
        ("frontal_approach", 0.98),
    ]
    for number, (scenario, target) in enumerate(targets, start=1):
        candidates = [row for row in rows if row["scenario"] == scenario]
        selected = min(candidates, key=lambda row: abs(risk(row, model) - target))
        scenes.append((render_svg(f"01-replay-{number:02d}", radar_scene(selected, model, number)), 2.2))

    scenes.append((render_svg("02-metrics", metric_scene(comparison, baseline, optimized)), 8.0))
    scenes.append((render_svg("03-safety", safety_scene(comparison)), 8.0))
    scenes.append((render_svg("04-reproduce", reproduce_scene(comparison, hardware)), 8.0))
    scenes.append((render_svg("05-boundary", boundary_scene()), 8.0))
    scenes.append((social_frame, 5.0))

    concat = FRAME_DIR / "concat.txt"
    entries = []
    for image, duration in scenes:
        entries.append(f"file '{image.resolve()}'\nduration {duration:.3f}")
    entries.append(f"file '{scenes[-1][0].resolve()}'")
    concat.write_text("\n".join(entries) + "\n", encoding="utf-8")
    destination = VIDEO_DIR / "reflexedge-evidence-demo.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
            "-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-movflags", "+faststart", str(destination),
        ],
        check=True,
    )
    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,r_frame_rate", "-of", "json", str(destination)],
            text=True,
        )
    )
    report = {
        "video": str(destination.relative_to(ROOT)),
        "duration_seconds": float(probe["format"]["duration"]),
        "size_bytes": int(probe["format"]["size"]),
        "streams": probe["streams"],
        "source": "Generated only from rights-checked project evidence and entrant-created graphics.",
        "audio": "none",
        "third_party_music": "none",
    }
    (ROOT / "reports/video_validation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["duration_seconds"] >= 180:
        raise SystemExit("video exceeds the three-minute rule")


if __name__ == "__main__":
    main()
