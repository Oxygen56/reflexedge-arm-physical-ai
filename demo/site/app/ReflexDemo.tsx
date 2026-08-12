"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { evidence } from "./evidence";
import styles from "./reflex.module.css";

type Frame = (typeof evidence.frames)[number];

const scenarioLabels: Record<string, string> = {
  safe: "Clear path",
  crossing: "Crossing object",
  "frontal approach": "Frontal approach",
  "sudden intrusion": "Sudden intrusion",
  dropout: "Sensor dropout",
};

function compact(value: number) {
  return new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

function drawRadar(canvas: HTMLCanvasElement, frame: Frame) {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(320, Math.floor(rect.width));
  const height = Math.max(320, Math.floor(rect.height));
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.scale(ratio, ratio);
  context.clearRect(0, 0, width, height);

  const centerX = width / 2;
  const centerY = height * 0.83;
  const maxRadius = Math.min(width * 0.45, height * 0.75);

  context.strokeStyle = "rgba(203, 255, 69, 0.12)";
  context.lineWidth = 1;
  for (let ring = 1; ring <= 4; ring += 1) {
    context.beginPath();
    context.arc(centerX, centerY, (maxRadius * ring) / 4, Math.PI, Math.PI * 2);
    context.stroke();
  }
  context.beginPath();
  context.moveTo(centerX - maxRadius, centerY);
  context.lineTo(centerX + maxRadius, centerY);
  context.stroke();

  frame.proximity.forEach((proximity, index) => {
    const fraction = index / (frame.proximity.length - 1);
    const angle = Math.PI + fraction * Math.PI;
    const danger = frame.danger[index];
    const radius = maxRadius * (0.22 + (1 - Math.min(0.96, proximity * 1.1)) * 0.78);
    const endX = centerX + Math.cos(angle) * radius;
    const endY = centerY + Math.sin(angle) * radius;
    const hot = danger > 0.18 || proximity > 0.55;
    const warm = danger > 0.08 || proximity > 0.28;
    context.strokeStyle = hot
      ? "rgba(255, 75, 75, 0.86)"
      : warm
        ? "rgba(255, 181, 69, 0.62)"
        : "rgba(203, 255, 69, 0.20)";
    context.lineWidth = hot ? 2.4 : warm ? 1.5 : 0.7;
    context.beginPath();
    context.moveTo(centerX, centerY);
    context.lineTo(endX, endY);
    context.stroke();
    if (proximity > 0.06) {
      context.fillStyle = hot ? "#ff4b4b" : warm ? "#ffb545" : "#cbff45";
      context.beginPath();
      context.arc(endX, endY, hot ? 4.2 : 2.2, 0, Math.PI * 2);
      context.fill();
    }
  });

  context.fillStyle = frame.action === "BRAKE" ? "#ff4b4b" : "#cbff45";
  context.fillRect(centerX - 24, centerY - 9, 48, 18);
  context.fillStyle = "#07090c";
  context.font = "600 9px ui-monospace, monospace";
  context.textAlign = "center";
  context.fillText("ACTUATOR", centerX, centerY + 3);
}

export function ReflexDemo() {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frame = evidence.frames[index];
  const scenarioIndexes = useMemo(() => {
    const map = new Map<string, number>();
    evidence.frames.forEach((item, itemIndex) => {
      if (!map.has(item.scenario)) map.set(item.scenario, itemIndex);
    });
    return [...map.entries()];
  }, []);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(
      () => setIndex((current) => (current + 1) % evidence.frames.length),
      1400,
    );
    return () => window.clearInterval(timer);
  }, [playing]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    drawRadar(canvas, frame);
    const redraw = () => drawRadar(canvas, frame);
    window.addEventListener("resize", redraw);
    return () => window.removeEventListener("resize", redraw);
  }, [frame]);

  const actionClass =
    frame.action === "BRAKE"
      ? styles.brake
      : frame.action === "HOLD"
        ? styles.hold
        : styles.go;

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <a className={styles.brand} href="#top" aria-label="ReflexEdge home">
          <span className={styles.brandMark} aria-hidden="true">R/</span>
          REFLEXEDGE
        </a>
        <div className={styles.headerStatus}>
          <span className={styles.liveDot} aria-hidden="true" />
          VERIFIED ARM64 RUN
        </div>
        <a
          className={styles.challengeLink}
          href="https://arm-ai-optimization-challenge.devpost.com/"
          target="_blank"
          rel="noreferrer"
        >
          ARM CREATE 2026 ↗
        </a>
      </header>

      <section className={styles.hero} id="top">
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>PHYSICAL AI · SENSOR → INFERENCE → ACTION</p>
          <h1>A brake reflex<br />you can audit.</h1>
          <p className={styles.lede}>
            ReflexEdge turns a raw 64-beam distance and radial-velocity frame into a learned collision-risk
            score and a deterministic actuator command. Every speed and safety
            claim replays from raw evidence on real Arm hardware.
          </p>
          <div className={styles.pipeline} aria-label="Inference pipeline">
            <span>01 / RAW SENSOR</span><b>→</b><span>02 / FUSED INT8 NEON</span><b>→</b><span>03 / BRAKE</span>
          </div>
          <div className={styles.hardwareStrip}>
            <span>{evidence.hardware.chip}</span>
            <span>{evidence.hardware.architecture}</span>
            <span>NEON {evidence.hardware.neon ? "ON" : "OFF"}</span>
            <span>DOTPROD {evidence.hardware.dotProduct ? "ON" : "OFF"}</span>
          </div>
        </div>

        <div className={styles.livePanel}>
          <div className={styles.panelTop}>
            <div>
              <span className={styles.panelLabel}>DETERMINISTIC REPLAY</span>
              <strong>{scenarioLabels[frame.scenario] ?? frame.scenario}</strong>
            </div>
            <button
              className={styles.playButton}
              onClick={() => setPlaying((value) => !value)}
              aria-label={playing ? "Pause replay" : "Resume replay"}
            >
              {playing ? "Ⅱ PAUSE" : "▶ PLAY"}
            </button>
          </div>
          <div className={styles.radarWrap}>
            <canvas
              ref={canvasRef}
              className={styles.radar}
              aria-label={`64-beam range replay for ${frame.scenario}`}
            />
            <div className={`${styles.actionCard} ${actionClass}`}>
              <span>ACTION</span>
              <strong>{frame.action}</strong>
              <small>{(frame.optimizedRisk * 100).toFixed(1)}% risk</small>
            </div>
          </div>
          <div className={styles.scenarioNav} aria-label="Replay scenarios">
            {scenarioIndexes.map(([scenario, frameIndex]) => (
              <button
                key={scenario}
                className={frame.scenario === scenario ? styles.activeScenario : ""}
                onClick={() => {
                  setIndex(frameIndex);
                  setPlaying(false);
                }}
              >
                {scenarioLabels[scenario] ?? scenario}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.metricBand} aria-label="Verified benchmark results">
        <div className={styles.metricLead}>
          <span>VERIFIED DELTA</span>
          <strong>{evidence.benchmark.pairedTrialMedian.p95Speedup.toFixed(2)}×</strong>
          <p>median p95 · raw sensor → action</p>
        </div>
        <Metric
          label="P95 · FINAL RUN"
          before={`${evidence.benchmark.baseline.p95Ns.toFixed(2)} ns`}
          after={`${evidence.benchmark.optimized.p95Ns.toFixed(2)} ns`}
        />
        <Metric
          label="THROUGHPUT · FINAL RUN"
          before={`${compact(evidence.benchmark.baseline.throughput)}/s`}
          after={`${compact(evidence.benchmark.optimized.throughput)}/s`}
        />
        <Metric
          label="MODEL BYTES"
          before={`${evidence.benchmark.baseline.modelBytes} B`}
          after={`${evidence.benchmark.optimized.modelBytes} B`}
        />
        <Metric
          label="ACCURACY"
          before={`${(evidence.benchmark.baseline.accuracy * 100).toFixed(2)}%`}
          after={`${(evidence.benchmark.optimized.accuracy * 100).toFixed(2)}%`}
        />
        <div className={styles.safetyMetric}>
          <span>ADDED GROUND-TRUTH FALSE NEGATIVES</span>
          <strong>{evidence.benchmark.additionalFalseNegativesVsScalar}</strong>
          <p>
            {evidence.benchmark.threeStateActionDisagreements} full action changes ·{" "}
            {evidence.benchmark.brakeDecisionDisagreements} BRAKE-boundary ·{" "}
            {evidence.benchmark.int8BrakeFalseNegativeDisagreementsVsScalar} missed scalar BRAKE ·{" "}
            {evidence.benchmark.int8AdditionalBrakeDecisionsVsScalar} additional int8 BRAKE
          </p>
        </div>
      </section>

      <section className={styles.proof} id="evidence">
        <div className={styles.sectionHead}>
          <p>THE EVIDENCE CONTRACT</p>
          <h2>Optimization is only real<br />when safety survives it.</h2>
        </div>
        <div className={styles.proofGrid}>
          <ProofCard
            number="01"
            title="Freeze the baseline"
            text={`${evidence.benchmark.rows.toLocaleString()} unseen test frames. ${evidence.benchmark.trialCount} independent alternating-order paired trials plus a ${evidence.benchmark.repeats.toLocaleString()}-pass final run. Same threshold and actuator policy.`}
          />
          <ProofCard
            number="02"
            title="Change one mechanism"
            text="Reference feature encoding and scalar FP32 become LUT + one-pass summaries, vectorized quantization, and an Arm NEON dot-product kernel. A validation-only safety bias favors an extra brake over a missed brake."
          />
          <ProofCard
            number="03"
            title="Retain raw proof"
            text={`Dataset ${evidence.benchmark.datasetSha256.slice(0, 12)}… · ${evidence.dataset.license} synthetic corpus · hardware identifiers removed.`}
          />
        </div>
      </section>

      <section className={styles.reproduce} id="reproduce">
        <div>
          <p className={styles.eyebrow}>JUDGE-READY OFFLINE PATH</p>
          <h2>One command.<br />No cloud. No secrets.</h2>
        </div>
        <div className={styles.commandCard}>
          <div className={styles.commandTop}><span>REPRODUCE THE FULL CLAIM</span><span>MIT</span></div>
          <code>./scripts/reproduce.sh</code>
          <ul>
            <li>Regenerates the rights-clean sensor corpus</li>
            <li>Trains and freezes the FP32 model</li>
            <li>Builds scalar and Arm NEON engines</li>
            <li>Runs safety, performance, rights, and negative-control gates</li>
          </ul>
        </div>
      </section>

      <section className={styles.boundary}>
        <p>CLAIM BOUNDARY</p>
        <div>
          <strong>Measured locally, not generalized globally.</strong>
          <span>
            CPU time per inference is an energy proxy, not joules. Synthetic
            frames prove deterministic regression behavior, not field safety certification.
          </span>
        </div>
      </section>

      <footer className={styles.footer}>
        <span>REFLEXEDGE / ARM PHYSICAL AI</span>
        <span>REAL HARDWARE · RAW EVIDENCE · HONEST BOUNDARIES</span>
        <span>2026 / MIT</span>
      </footer>
    </main>
  );
}

function Metric({ label, before, after }: { label: string; before: string; after: string }) {
  return (
    <div className={styles.metric}>
      <span>{label}</span>
      <div><del>{before}</del><strong>{after}</strong></div>
    </div>
  );
}

function ProofCard({ number, title, text }: { number: string; title: string; text: string }) {
  return (
    <article className={styles.proofCard}>
      <span>{number}</span>
      <h3>{title}</h3>
      <p>{text}</p>
    </article>
  );
}
