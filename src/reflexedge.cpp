#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <sys/utsname.h>
#include <vector>

#if defined(__aarch64__) || defined(__arm64__)
#include <arm_neon.h>
#endif

#include "model_weights.h"

namespace {

using Clock = std::chrono::steady_clock;
constexpr std::size_t kFeatureCount = reflexedge_model::kFeatureCount;
constexpr std::size_t kBeamCount = 64;
constexpr std::size_t kSummaryFeatureCount = 16;
static_assert(kFeatureCount == kBeamCount * 2 + kSummaryFeatureCount);

struct Sample {
  std::string id;
  std::string scenario;
  int label{};
  std::array<float, kBeamCount> distances{};
  std::array<float, kBeamCount> velocities{};
  std::array<float, kFeatureCount> features{};
  std::array<std::int8_t, kFeatureCount> quantized{};
};

struct Confusion {
  std::uint64_t tp{};
  std::uint64_t fp{};
  std::uint64_t tn{};
  std::uint64_t fn{};
};

std::vector<std::string> split_csv(const std::string& line) {
  std::vector<std::string> fields;
  std::stringstream stream(line);
  std::string field;
  while (std::getline(stream, field, ',')) fields.push_back(field);
  return fields;
}

float clamp01(float value) { return std::max(0.0f, std::min(1.0f, value)); }

void encode_sensor_frame(const std::array<float, kBeamCount>& distances,
                         const std::array<float, kBeamCount>& velocities,
                         std::array<float, kFeatureCount>& features) {
  constexpr float kPi = 3.14159265358979323846f;
  std::array<float, kBeamCount> danger{};
  std::array<float, kBeamCount> proximity{};
  for (std::size_t beam = 0; beam < kBeamCount; ++beam) {
    const float angle = -kPi / 2.0f + static_cast<float>(beam) * kPi /
                                             static_cast<float>(kBeamCount - 1);
    const float ratio = angle / 0.78f;
    const float angular_weight = std::exp(-(ratio * ratio));
    const float normalized_proximity = clamp01((6.0f - distances[beam]) / 6.0f);
    const float closing = clamp01(-velocities[beam] / 6.0f);
    danger[beam] = normalized_proximity * (0.25f + 0.75f * closing) * angular_weight;
    proximity[beam] = normalized_proximity * angular_weight;
    features[beam] = danger[beam];
    features[kBeamCount + beam] = proximity[beam];
  }

  auto ordered_danger = danger;
  std::sort(ordered_danger.begin(), ordered_danger.end(), std::greater<float>());
  const auto mean_range = [](const auto& values, std::size_t begin, std::size_t end) {
    return std::accumulate(values.begin() + static_cast<std::ptrdiff_t>(begin),
                           values.begin() + static_cast<std::ptrdiff_t>(end), 0.0f) /
           static_cast<float>(end - begin);
  };
  const auto max_range = [](const auto& values, std::size_t begin, std::size_t end) {
    return *std::max_element(values.begin() + static_cast<std::ptrdiff_t>(begin),
                             values.begin() + static_cast<std::ptrdiff_t>(end));
  };
  const std::size_t offset = kBeamCount * 2;
  features[offset + 0] = ordered_danger[0];
  features[offset + 1] = ordered_danger[1];
  features[offset + 2] = mean_range(ordered_danger, 0, 4);
  features[offset + 3] = mean_range(danger, 0, kBeamCount);
  features[offset + 4] = max_range(danger, 22, 42);
  features[offset + 5] = max_range(danger, 0, 32);
  features[offset + 6] = max_range(danger, 32, kBeamCount);
  features[offset + 7] = max_range(proximity, 0, kBeamCount);
  features[offset + 8] = max_range(proximity, 22, 42);
  features[offset + 9] = mean_range(proximity, 0, kBeamCount);
  features[offset + 10] = static_cast<float>(std::count_if(
                              danger.begin(), danger.end(), [](float value) { return value >= 0.05f; })) /
                          static_cast<float>(kBeamCount);
  features[offset + 11] = static_cast<float>(std::count_if(
                              danger.begin(), danger.end(), [](float value) { return value >= 0.10f; })) /
                          static_cast<float>(kBeamCount);
  features[offset + 12] = static_cast<float>(std::count_if(
                              danger.begin(), danger.end(), [](float value) { return value >= 0.20f; })) /
                          static_cast<float>(kBeamCount);
  features[offset + 13] = mean_range(danger, 22, 42);
  features[offset + 14] =
      (std::accumulate(danger.begin(), danger.begin() + 12, 0.0f) +
       std::accumulate(danger.end() - 12, danger.end(), 0.0f)) /
      24.0f;
  features[offset + 15] = 1.0f;
}

const std::array<float, kBeamCount>& angular_weight_lut() {
  static const std::array<float, kBeamCount> weights = [] {
    constexpr float kPi = 3.14159265358979323846f;
    std::array<float, kBeamCount> values{};
    for (std::size_t beam = 0; beam < kBeamCount; ++beam) {
      const float angle = -kPi / 2.0f + static_cast<float>(beam) * kPi /
                                               static_cast<float>(kBeamCount - 1);
      const float ratio = angle / 0.78f;
      values[beam] = std::exp(-(ratio * ratio));
    }
    return values;
  }();
  return weights;
}

void encode_sensor_frame_fast(const std::array<float, kBeamCount>& distances,
                              const std::array<float, kBeamCount>& velocities,
                              std::array<float, kFeatureCount>& features) {
  std::array<float, kBeamCount> danger{};
  std::array<float, kBeamCount> proximity{};
  std::array<float, 4> top_danger{};
  const auto& angular_weights = angular_weight_lut();
  for (std::size_t beam = 0; beam < kBeamCount; ++beam) {
    const float normalized_proximity = clamp01((6.0f - distances[beam]) / 6.0f);
    const float closing = clamp01(-velocities[beam] / 6.0f);
    const float danger_value =
        normalized_proximity * (0.25f + 0.75f * closing) * angular_weights[beam];
    const float proximity_value = normalized_proximity * angular_weights[beam];
    danger[beam] = danger_value;
    proximity[beam] = proximity_value;
    features[beam] = danger_value;
    features[kBeamCount + beam] = proximity_value;
    for (std::size_t position = 0; position < top_danger.size(); ++position) {
      if (danger_value > top_danger[position]) {
        for (std::size_t shift = top_danger.size() - 1; shift > position; --shift)
          top_danger[shift] = top_danger[shift - 1];
        top_danger[position] = danger_value;
        break;
      }
    }
  }

  const auto mean_range = [](const auto& values, std::size_t begin, std::size_t end) {
    return std::accumulate(values.begin() + static_cast<std::ptrdiff_t>(begin),
                           values.begin() + static_cast<std::ptrdiff_t>(end), 0.0f) /
           static_cast<float>(end - begin);
  };
  const auto max_range = [](const auto& values, std::size_t begin, std::size_t end) {
    return *std::max_element(values.begin() + static_cast<std::ptrdiff_t>(begin),
                             values.begin() + static_cast<std::ptrdiff_t>(end));
  };
  const std::size_t offset = kBeamCount * 2;
  features[offset + 0] = top_danger[0];
  features[offset + 1] = top_danger[1];
  features[offset + 2] =
      std::accumulate(top_danger.begin(), top_danger.end(), 0.0f) / top_danger.size();
  features[offset + 3] = mean_range(danger, 0, kBeamCount);
  features[offset + 4] = max_range(danger, 22, 42);
  features[offset + 5] = max_range(danger, 0, 32);
  features[offset + 6] = max_range(danger, 32, kBeamCount);
  features[offset + 7] = max_range(proximity, 0, kBeamCount);
  features[offset + 8] = max_range(proximity, 22, 42);
  features[offset + 9] = mean_range(proximity, 0, kBeamCount);
  features[offset + 10] = static_cast<float>(std::count_if(
                              danger.begin(), danger.end(), [](float value) { return value >= 0.05f; })) /
                          static_cast<float>(kBeamCount);
  features[offset + 11] = static_cast<float>(std::count_if(
                              danger.begin(), danger.end(), [](float value) { return value >= 0.10f; })) /
                          static_cast<float>(kBeamCount);
  features[offset + 12] = static_cast<float>(std::count_if(
                              danger.begin(), danger.end(), [](float value) { return value >= 0.20f; })) /
                          static_cast<float>(kBeamCount);
  features[offset + 13] = mean_range(danger, 22, 42);
  features[offset + 14] =
      (std::accumulate(danger.begin(), danger.begin() + 12, 0.0f) +
       std::accumulate(danger.end() - 12, danger.end(), 0.0f)) /
      24.0f;
  features[offset + 15] = 1.0f;
}

void quantize_features(const std::array<float, kFeatureCount>& features,
                       std::array<std::int8_t, kFeatureCount>& quantized) {
  for (std::size_t index = 0; index < kFeatureCount; ++index) {
    quantized[index] = static_cast<std::int8_t>(
        std::max(0, std::min(127, static_cast<int>(std::lround(features[index] * 127.0f)))));
  }
}

void quantize_features_fast(const std::array<float, kFeatureCount>& features,
                            std::array<std::int8_t, kFeatureCount>& quantized) {
#if defined(__aarch64__) || defined(__arm64__)
  for (std::size_t index = 0; index < kFeatureCount; index += 16) {
    const int32x4_t q0 = vcvtnq_s32_f32(vmulq_n_f32(vld1q_f32(features.data() + index), 127.0f));
    const int32x4_t q1 = vcvtnq_s32_f32(vmulq_n_f32(vld1q_f32(features.data() + index + 4), 127.0f));
    const int32x4_t q2 = vcvtnq_s32_f32(vmulq_n_f32(vld1q_f32(features.data() + index + 8), 127.0f));
    const int32x4_t q3 = vcvtnq_s32_f32(vmulq_n_f32(vld1q_f32(features.data() + index + 12), 127.0f));
    const int16x8_t h0 = vcombine_s16(vqmovn_s32(q0), vqmovn_s32(q1));
    const int16x8_t h1 = vcombine_s16(vqmovn_s32(q2), vqmovn_s32(q3));
    vst1q_s8(quantized.data() + index,
             vcombine_s8(vqmovn_s16(h0), vqmovn_s16(h1)));
  }
#else
  quantize_features(features, quantized);
#endif
}

std::vector<Sample> load_dataset(const std::string& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open dataset: " + path);
  std::string line;
  std::getline(input, line);
  auto header = split_csv(line);
  if (header.size() != 5 + kBeamCount * 2 + kFeatureCount)
    throw std::runtime_error("unexpected raw sensor or feature count");
  std::vector<Sample> samples;
  while (std::getline(input, line)) {
    if (line.empty()) continue;
    auto fields = split_csv(line);
    if (fields.size() != header.size()) throw std::runtime_error("malformed CSV row");
    Sample sample;
    sample.id = fields[0];
    sample.scenario = fields[2];
    sample.label = std::stoi(fields[3]);
    for (std::size_t beam = 0; beam < kBeamCount; ++beam) {
      sample.distances[beam] = std::stof(fields[5 + beam]);
      sample.velocities[beam] = std::stof(fields[5 + kBeamCount + beam]);
    }
    encode_sensor_frame(sample.distances, sample.velocities, sample.features);
    for (std::size_t index = 0; index < kFeatureCount; ++index) {
      const float stored = std::stof(fields[5 + kBeamCount * 2 + index]);
      if (std::abs(stored - sample.features[index]) > 2e-5f)
        throw std::runtime_error("raw sensor encoding does not match stored feature evidence");
    }
    quantize_features(sample.features, sample.quantized);
    std::array<float, kFeatureCount> fast_features{};
    std::array<std::int8_t, kFeatureCount> fast_quantized{};
    encode_sensor_frame_fast(sample.distances, sample.velocities, fast_features);
    quantize_features_fast(fast_features, fast_quantized);
    for (std::size_t index = 0; index < kFeatureCount; ++index) {
      if (std::abs(fast_features[index] - sample.features[index]) > 2e-6f)
        throw std::runtime_error("optimized sensor encoder diverges from reference encoder");
      if (fast_quantized[index] != sample.quantized[index])
        throw std::runtime_error("optimized sensor quantizer diverges from reference quantizer");
    }
    samples.push_back(std::move(sample));
  }
  if (samples.empty()) throw std::runtime_error("dataset is empty");
  return samples;
}

float sigmoid(float value) {
  if (value >= 0.0f) {
    const float z = std::exp(-std::min(value, 60.0f));
    return 1.0f / (1.0f + z);
  }
  const float z = std::exp(std::max(value, -60.0f));
  return z / (1.0f + z);
}

float infer_scalar_features(const std::array<float, kFeatureCount>& features) {
  float dot = 0.0f;
#if defined(__clang__)
#pragma clang loop vectorize(disable)
#pragma clang loop interleave(disable)
#endif
  for (std::size_t index = 0; index < kFeatureCount; ++index) {
    dot += features[index] * reflexedge_model::kWeightsFloat[index];
  }
  return sigmoid(reflexedge_model::kBias + dot);
}

[[maybe_unused]] std::int32_t dot_int8_portable(const std::int8_t* left, const std::int8_t* right) {
  std::int32_t dot = 0;
  for (std::size_t index = 0; index < kFeatureCount; ++index) dot += left[index] * right[index];
  return dot;
}

std::int32_t dot_int8_neon(const std::int8_t* left, const std::int8_t* right) {
#if (defined(__aarch64__) || defined(__arm64__)) && defined(__ARM_FEATURE_DOTPROD)
  int32x4_t accumulator = vdupq_n_s32(0);
  for (std::size_t index = 0; index < kFeatureCount; index += 16) {
    accumulator = vdotq_s32(accumulator, vld1q_s8(left + index), vld1q_s8(right + index));
  }
  return vaddvq_s32(accumulator);
#elif defined(__aarch64__) || defined(__arm64__)
  int32x4_t accumulator = vdupq_n_s32(0);
  for (std::size_t index = 0; index < kFeatureCount; index += 16) {
    const int8x16_t lhs = vld1q_s8(left + index);
    const int8x16_t rhs = vld1q_s8(right + index);
    const int16x8_t low = vmull_s8(vget_low_s8(lhs), vget_low_s8(rhs));
    const int16x8_t high = vmull_s8(vget_high_s8(lhs), vget_high_s8(rhs));
    accumulator = vpadalq_s16(accumulator, low);
    accumulator = vpadalq_s16(accumulator, high);
  }
  return vaddvq_s32(accumulator);
#else
  return dot_int8_portable(left, right);
#endif
}

float infer_optimized_features(const std::array<std::int8_t, kFeatureCount>& quantized) {
  const std::int32_t dot = dot_int8_neon(quantized.data(), reflexedge_model::kWeightsInt8);
  const float restored = static_cast<float>(dot) * reflexedge_model::kWeightScale / 127.0f;
  return sigmoid(reflexedge_model::kBias + restored + reflexedge_model::kInt8SafetyBias);
}

float infer_scalar(const Sample& sample) { return infer_scalar_features(sample.features); }

float infer_optimized(const Sample& sample) {
  return infer_optimized_features(sample.quantized);
}

enum class Action : std::uint8_t { Go = 0, Hold = 1, Brake = 2 };

Action classify_action(float probability) {
  if (probability >= reflexedge_model::kThreshold) return Action::Brake;
  if (probability >= reflexedge_model::kThreshold * 0.62f) return Action::Hold;
  return Action::Go;
}

const char* action_name(Action value) {
  switch (value) {
    case Action::Brake:
      return "BRAKE";
    case Action::Hold:
      return "HOLD";
    case Action::Go:
      return "GO";
  }
  return "UNKNOWN";
}

double percentile(std::vector<double> values, double fraction) {
  if (values.empty()) return 0.0;
  std::sort(values.begin(), values.end());
  const double position = fraction * static_cast<double>(values.size() - 1);
  const auto lower = static_cast<std::size_t>(std::floor(position));
  const auto upper = static_cast<std::size_t>(std::ceil(position));
  const double weight = position - static_cast<double>(lower);
  return values[lower] * (1.0 - weight) + values[upper] * weight;
}

double cpu_seconds() {
  rusage usage{};
  getrusage(RUSAGE_SELF, &usage);
  return usage.ru_utime.tv_sec + usage.ru_utime.tv_usec / 1e6 + usage.ru_stime.tv_sec +
         usage.ru_stime.tv_usec / 1e6;
}

std::uint64_t peak_rss_bytes() {
  rusage usage{};
  getrusage(RUSAGE_SELF, &usage);
#if defined(__APPLE__)
  return static_cast<std::uint64_t>(usage.ru_maxrss);
#else
  return static_cast<std::uint64_t>(usage.ru_maxrss) * 1024ULL;
#endif
}

std::string machine_architecture() {
  utsname value{};
  if (uname(&value) != 0) return "unknown";
  return value.machine;
}

std::string engine_name() {
#if defined(REFLEXEDGE_OPTIMIZED)
  return "int8_arm_neon";
#else
  return "fp32_scalar";
#endif
}

float infer_selected(const Sample& sample) {
#if defined(REFLEXEDGE_OPTIMIZED)
  return infer_optimized(sample);
#else
  return infer_scalar(sample);
#endif
}

float infer_pipeline_selected(const Sample& sample) {
  std::array<float, kFeatureCount> features{};
#if defined(REFLEXEDGE_OPTIMIZED)
  encode_sensor_frame_fast(sample.distances, sample.velocities, features);
  std::array<std::int8_t, kFeatureCount> quantized{};
  quantize_features_fast(features, quantized);
  const float probability = infer_optimized_features(quantized);
#else
  encode_sensor_frame(sample.distances, sample.velocities, features);
  const float probability = infer_scalar_features(features);
#endif
  const float action_token = static_cast<float>(classify_action(probability));
  return probability + action_token;
}

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (char character : value) {
    if (character == '\\' || character == '"') out << '\\';
    out << character;
  }
  return out.str();
}

struct Measurement {
  std::vector<double> batch_latency_ns;
  std::uint64_t inferences{};
  double wall_seconds{};
  double cpu_seconds{};
  float sink{};
};

template <typename Function>
Measurement measure(const std::vector<Sample>& samples, std::size_t repeats, Function function) {
  for (int warmup = 0; warmup < 3; ++warmup) {
    volatile float warmup_sink = 0.0f;
    for (const auto& sample : samples) warmup_sink += function(sample);
    (void)warmup_sink;
  }

  constexpr std::size_t kBatchSize = 32;
  Measurement result;
  result.batch_latency_ns.reserve(repeats * ((samples.size() + kBatchSize - 1) / kBatchSize));
  volatile float sink = 0.0f;
  const double cpu_start = cpu_seconds();
  const auto wall_start = Clock::now();
  for (std::size_t repeat = 0; repeat < repeats; ++repeat) {
    for (std::size_t begin = 0; begin < samples.size(); begin += kBatchSize) {
      const std::size_t end = std::min(samples.size(), begin + kBatchSize);
      const auto start = Clock::now();
      for (std::size_t index = begin; index < end; ++index) sink += function(samples[index]);
      const auto stop = Clock::now();
      const double elapsed = std::chrono::duration<double, std::nano>(stop - start).count();
      result.batch_latency_ns.push_back(elapsed / static_cast<double>(end - begin));
      result.inferences += end - begin;
    }
  }
  const auto wall_stop = Clock::now();
  const double cpu_stop = cpu_seconds();
  result.wall_seconds = std::chrono::duration<double>(wall_stop - wall_start).count();
  result.cpu_seconds = cpu_stop - cpu_start;
  result.sink = sink;
  return result;
}

void write_result(const std::string& path, const std::string& dataset_path,
                  const std::vector<Sample>& samples, std::size_t repeats) {
  constexpr std::size_t kBatchSize = 32;
  const Measurement kernel = measure(samples, repeats, infer_selected);
  const Measurement pipeline = measure(samples, repeats, infer_pipeline_selected);

  Confusion confusion;
  std::uint64_t three_state_action_disagreements = 0;
  std::uint64_t brake_decision_disagreements = 0;
  std::uint64_t int8_brake_false_negative_disagreements = 0;
  std::uint64_t int8_additional_brake_decisions = 0;
  std::uint64_t added_false_negatives = 0;
  for (const auto& sample : samples) {
    const float probability = infer_selected(sample);
    const bool prediction = probability >= reflexedge_model::kThreshold;
    confusion.tp += prediction && sample.label == 1;
    confusion.fp += prediction && sample.label == 0;
    confusion.tn += !prediction && sample.label == 0;
    confusion.fn += !prediction && sample.label == 1;
    const Action scalar_action = classify_action(infer_scalar(sample));
    const Action optimized_action = classify_action(infer_optimized(sample));
    const bool scalar_brake = scalar_action == Action::Brake;
    const bool optimized_brake = optimized_action == Action::Brake;
    three_state_action_disagreements += scalar_action != optimized_action;
    brake_decision_disagreements += scalar_brake != optimized_brake;
    int8_brake_false_negative_disagreements += scalar_brake && !optimized_brake;
    int8_additional_brake_decisions += !scalar_brake && optimized_brake;
    added_false_negatives += scalar_brake && !optimized_brake && sample.label == 1;
  }
  const double accuracy = static_cast<double>(confusion.tp + confusion.tn) / samples.size();
  const double precision = static_cast<double>(confusion.tp) / std::max<std::uint64_t>(1, confusion.tp + confusion.fp);
  const double recall = static_cast<double>(confusion.tp) / std::max<std::uint64_t>(1, confusion.tp + confusion.fn);
  const double f1 = 2.0 * precision * recall / std::max(1e-12, precision + recall);
  const std::uint64_t model_bytes =
#if defined(REFLEXEDGE_OPTIMIZED)
      kFeatureCount * sizeof(std::int8_t) + sizeof(float) * 4;
#else
      kFeatureCount * sizeof(float) + sizeof(float) * 2;
#endif

  std::ostringstream json;
  json << std::fixed << std::setprecision(9);
  json << "{\n"
       << "  \"engine\": \"" << engine_name() << "\",\n"
       << "  \"architecture\": \"" << machine_architecture() << "\",\n"
       << "  \"dataset\": \"" << json_escape(dataset_path) << "\",\n"
       << "  \"rows\": " << samples.size() << ",\n"
       << "  \"repeats\": " << repeats << ",\n"
       << "  \"inferences\": " << kernel.inferences << ",\n"
       << "  \"batch_size\": " << kBatchSize << ",\n"
       << "  \"timed_batches\": " << kernel.batch_latency_ns.size() << ",\n"
       << "  \"latency_scope\": \"model inference only; features are pre-encoded and CSV loading is excluded\",\n"
       << "  \"latency_ns\": {\"p50\": " << percentile(kernel.batch_latency_ns, 0.50)
       << ", \"p95\": " << percentile(kernel.batch_latency_ns, 0.95)
       << ", \"p99\": " << percentile(kernel.batch_latency_ns, 0.99) << "},\n"
       << "  \"throughput_per_second\": " << kernel.inferences / kernel.wall_seconds << ",\n"
       << "  \"wall_seconds\": " << kernel.wall_seconds << ",\n"
       << "  \"cpu_seconds\": " << kernel.cpu_seconds << ",\n"
       << "  \"cpu_ns_per_inference_energy_proxy\": " << kernel.cpu_seconds * 1e9 / kernel.inferences << ",\n"
       << "  \"end_to_end\": {\n"
       << "    \"scope\": \"raw 64-beam distance and velocity input through feature encoding, quantization when applicable, model inference, and GO/HOLD/BRAKE policy\",\n"
       << "    \"inferences\": " << pipeline.inferences << ",\n"
       << "    \"latency_ns\": {\"p50\": " << percentile(pipeline.batch_latency_ns, 0.50)
       << ", \"p95\": " << percentile(pipeline.batch_latency_ns, 0.95)
       << ", \"p99\": " << percentile(pipeline.batch_latency_ns, 0.99) << "},\n"
       << "    \"throughput_per_second\": " << pipeline.inferences / pipeline.wall_seconds << ",\n"
       << "    \"wall_seconds\": " << pipeline.wall_seconds << ",\n"
       << "    \"cpu_seconds\": " << pipeline.cpu_seconds << ",\n"
       << "    \"cpu_ns_per_inference_energy_proxy\": " << pipeline.cpu_seconds * 1e9 / pipeline.inferences << ",\n"
       << "    \"sink\": " << pipeline.sink << "\n"
       << "  },\n"
       << "  \"peak_rss_bytes\": " << peak_rss_bytes() << ",\n"
       << "  \"model_bytes\": " << model_bytes << ",\n"
       << "  \"threshold\": " << reflexedge_model::kThreshold << ",\n"
       << "  \"quality\": {\"accuracy\": " << accuracy << ", \"precision\": " << precision
       << ", \"recall\": " << recall << ", \"f1\": " << f1
       << ", \"false_negative\": " << confusion.fn << "},\n"
       << "  \"action_disagreement_scope\": \"full three-state GO/HOLD/BRAKE command equality\",\n"
       << "  \"scalar_vs_int8_action_disagreements\": " << three_state_action_disagreements << ",\n"
       << "  \"scalar_vs_int8_brake_decision_disagreements\": " << brake_decision_disagreements << ",\n"
       << "  \"int8_brake_false_negative_disagreements_vs_scalar\": "
       << int8_brake_false_negative_disagreements << ",\n"
       << "  \"int8_additional_brake_decisions_vs_scalar\": " << int8_additional_brake_decisions << ",\n"
       << "  \"additional_false_negatives_vs_scalar\": " << added_false_negatives << ",\n"
       << "  \"direct_energy_joules\": null,\n"
       << "  \"direct_energy_status\": \"not_measured_requires_supported_meter\",\n"
       << "  \"sink\": " << kernel.sink << "\n"
       << "}\n";
  std::ofstream output(path);
  if (!output) throw std::runtime_error("cannot write result: " + path);
  output << json.str();
  std::cout << json.str();
}

void demo(const std::vector<Sample>& samples, std::size_t count) {
  count = std::min(count, samples.size());
  for (std::size_t index = 0; index < count; ++index) {
    const float probability = infer_selected(samples[index]);
    std::cout << "{\"sample\":\"" << json_escape(samples[index].id) << "\",\"scenario\":\""
              << json_escape(samples[index].scenario) << "\",\"risk\":" << std::fixed
              << std::setprecision(5) << probability << ",\"action\":\""
              << action_name(classify_action(probability))
              << "\",\"truth_brake\":" << samples[index].label << "}\n";
  }
}

}  // namespace

int main(int argc, char** argv) {
  try {
    std::string dataset = "data/processed/test.csv";
    std::string output = "reports/benchmark.json";
    std::size_t repeats = 200;
    std::size_t demo_count = 0;
    for (int index = 1; index < argc; ++index) {
      const std::string argument = argv[index];
      if (argument == "--dataset" && index + 1 < argc) dataset = argv[++index];
      else if (argument == "--output" && index + 1 < argc) output = argv[++index];
      else if (argument == "--repeat" && index + 1 < argc) repeats = std::stoul(argv[++index]);
      else if (argument == "--demo" && index + 1 < argc) demo_count = std::stoul(argv[++index]);
      else if (argument == "--help") {
        std::cout << "Usage: reflexedge [--dataset PATH] [--output PATH] [--repeat N] [--demo N]\n";
        return 0;
      } else {
        throw std::runtime_error("unknown argument: " + argument);
      }
    }
    const auto samples = load_dataset(dataset);
    if (demo_count > 0) {
      demo(samples, demo_count);
      return 0;
    }
    write_result(output, dataset, samples, repeats);
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "reflexedge: " << error.what() << '\n';
    return 2;
  }
}
