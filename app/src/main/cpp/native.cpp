#include <jni.h>
#include <android/log.h>
#include <chrono>
#include <cstdint>
#include <thread>
#include <vector>
#include <sstream>
#include <algorithm>

extern "C" uint64_t asm_integer_bench(uint64_t iterations);
extern "C" float asm_neon_bench(uint64_t iterations);

extern "C" JNIEXPORT jstring JNICALL
Java_com_meysam_cputestasm_MainActivity_runBenchmark(JNIEnv* env, jobject, jint workers, jlong iterations) {
    workers = std::max(1, std::min(workers, 8));
    const uint64_t count = static_cast<uint64_t>(iterations);
    std::vector<uint64_t> ints(workers);
    std::vector<float> vectors(workers);
    auto start = std::chrono::steady_clock::now();
    std::vector<std::thread> pool;
    for (int i = 0; i < workers; ++i) pool.emplace_back([&, i] {
        ints[i] = asm_integer_bench(count);
        vectors[i] = asm_neon_bench(count);
    });
    for (auto& t : pool) t.join();
    auto end = std::chrono::steady_clock::now();
    double ms = std::chrono::duration<double, std::milli>(end - start).count();
    uint64_t checksum = 0; float fsum = 0;
    for (int i = 0; i < workers; ++i) { checksum ^= ints[i]; fsum += vectors[i]; }
    std::ostringstream out;
    out << "ARM64 Assembly benchmark complete\n\nWorkers: " << workers
        << "\nIterations / worker / kernel: " << count
        << "\nElapsed: " << ms << " ms\nInteger checksum: " << checksum
        << "\nNEON checksum: " << fsum
        << "\n\nNative code: ARM64 .S + C++ JNI\nABI: arm64-v8a\n\nThis is a throughput stress test, not a power meter. Results vary with temperature, DVFS and thermal throttling.";
    std::string s = out.str();
    return env->NewStringUTF(s.c_str());
}
