#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
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

struct Sample {
  std::string id;
  std::string scenario;
  int label{};
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

std::vector<Sample> load_dataset(const std::string& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open dataset: " + path);
  std::string line;
  std::getline(input, line);
  auto header = split_csv(line);
  if (header.size() != 5 + kFeatureCount) {
    throw std::runtime_error("unexpected dataset feature count");
  }
  std::vector<Sample> samples;
  while (std::getline(input, line)) {
    if (line.empty()) continue;
    auto fields = split_csv(line);
    if (fields.size() != header.size()) throw std::runtime_error("malformed CSV row");
    Sample sample;
    sample.id = fields[0];
    sample.scenario = fields[2];
    sample.label = std::stoi(fields[3]);
    for (std::size_t index = 0; index < kFeatureCount; ++index) {
      const float value = std::stof(fields[index + 5]);
      sample.features[index] = value;
      sample.quantized[index] = static_cast<std::int8_t>(
          std::max(0, std::min(127, static_cast<int>(std::lround(value * 127.0f)))));
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

float infer_scalar(const Sample& sample) {
  float dot = 0.0f;
#if defined(__clang__)
#pragma clang loop vectorize(disable)
#pragma clang loop interleave(disable)
#endif
  for (std::size_t index = 0; index < kFeatureCount; ++index) {
    dot += sample.features[index] * reflexedge_model::kWeightsFloat[index];
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

float infer_optimized(const Sample& sample) {
  const std::int32_t dot = dot_int8_neon(sample.quantized.data(), reflexedge_model::kWeightsInt8);
  const float restored = static_cast<float>(dot) * reflexedge_model::kWeightScale / 127.0f;
  return sigmoid(reflexedge_model::kBias + restored + reflexedge_model::kInt8SafetyBias);
}

const char* action(float probability) {
  if (probability >= reflexedge_model::kThreshold) return "BRAKE";
  if (probability >= reflexedge_model::kThreshold * 0.62f) return "HOLD";
  return "GO";
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

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (char character : value) {
    if (character == '\\' || character == '"') out << '\\';
    out << character;
  }
  return out.str();
}

void write_result(const std::string& path, const std::string& dataset_path,
                  const std::vector<Sample>& samples, std::size_t repeats) {
  for (int warmup = 0; warmup < 3; ++warmup) {
    volatile float sink = 0.0f;
    for (const auto& sample : samples) sink += infer_selected(sample);
    (void)sink;
  }

  constexpr std::size_t kBatchSize = 32;
  std::vector<double> batch_latency_ns;
  batch_latency_ns.reserve(repeats * (samples.size() / kBatchSize + 1));
  volatile float sink = 0.0f;
  const double cpu_start = cpu_seconds();
  const auto wall_start = Clock::now();
  std::uint64_t inferences = 0;
  for (std::size_t repeat = 0; repeat < repeats; ++repeat) {
    for (std::size_t begin = 0; begin < samples.size(); begin += kBatchSize) {
      const std::size_t end = std::min(samples.size(), begin + kBatchSize);
      const auto start = Clock::now();
      for (std::size_t index = begin; index < end; ++index) sink += infer_selected(samples[index]);
      const auto stop = Clock::now();
      const double elapsed = std::chrono::duration<double, std::nano>(stop - start).count();
      batch_latency_ns.push_back(elapsed / static_cast<double>(end - begin));
      inferences += end - begin;
    }
  }
  const auto wall_stop = Clock::now();
  const double cpu_stop = cpu_seconds();
  const double wall_seconds = std::chrono::duration<double>(wall_stop - wall_start).count();

  Confusion confusion;
  std::uint64_t action_disagreements = 0;
  std::uint64_t added_false_negatives = 0;
  for (const auto& sample : samples) {
    const float probability = infer_selected(sample);
    const bool prediction = probability >= reflexedge_model::kThreshold;
    confusion.tp += prediction && sample.label == 1;
    confusion.fp += prediction && sample.label == 0;
    confusion.tn += !prediction && sample.label == 0;
    confusion.fn += !prediction && sample.label == 1;
    const bool scalar_action = infer_scalar(sample) >= reflexedge_model::kThreshold;
    const bool optimized_action = infer_optimized(sample) >= reflexedge_model::kThreshold;
    action_disagreements += scalar_action != optimized_action;
    added_false_negatives += scalar_action && !optimized_action && sample.label == 1;
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
       << "  \"inferences\": " << inferences << ",\n"
       << "  \"latency_ns\": {\"p50\": " << percentile(batch_latency_ns, 0.50)
       << ", \"p95\": " << percentile(batch_latency_ns, 0.95)
       << ", \"p99\": " << percentile(batch_latency_ns, 0.99) << "},\n"
       << "  \"throughput_per_second\": " << inferences / wall_seconds << ",\n"
       << "  \"wall_seconds\": " << wall_seconds << ",\n"
       << "  \"cpu_seconds\": " << cpu_stop - cpu_start << ",\n"
       << "  \"cpu_ns_per_inference_energy_proxy\": " << (cpu_stop - cpu_start) * 1e9 / inferences << ",\n"
       << "  \"peak_rss_bytes\": " << peak_rss_bytes() << ",\n"
       << "  \"model_bytes\": " << model_bytes << ",\n"
       << "  \"threshold\": " << reflexedge_model::kThreshold << ",\n"
       << "  \"quality\": {\"accuracy\": " << accuracy << ", \"precision\": " << precision
       << ", \"recall\": " << recall << ", \"f1\": " << f1
       << ", \"false_negative\": " << confusion.fn << "},\n"
       << "  \"scalar_vs_int8_action_disagreements\": " << action_disagreements << ",\n"
       << "  \"additional_false_negatives_vs_scalar\": " << added_false_negatives << ",\n"
       << "  \"direct_energy_joules\": null,\n"
       << "  \"direct_energy_status\": \"not_measured_requires_supported_meter\",\n"
       << "  \"sink\": " << sink << "\n"
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
              << std::setprecision(5) << probability << ",\"action\":\"" << action(probability)
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
