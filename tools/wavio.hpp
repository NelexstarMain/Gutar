// wavio.hpp - prosty odczyt/zapis WAV 16-bit (tylko narzędzia testowe)
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace wavio {

inline bool write16(const std::string& path, const std::vector<float>& x, int fs) {
  FILE* f = fopen(path.c_str(), "wb");
  if (!f) return false;
  const uint32_t n = (uint32_t)x.size(), dataBytes = n * 2, riff = 36 + dataBytes, rate = (uint32_t)fs, byteRate = rate * 2;
  const uint16_t fmt = 1, ch = 1, align = 2, bits = 16;
  const uint32_t fmtLen = 16;
  fwrite("RIFF", 1, 4, f); fwrite(&riff, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f); fwrite(&fmtLen, 4, 1, f);
  fwrite(&fmt, 2, 1, f); fwrite(&ch, 2, 1, f); fwrite(&rate, 4, 1, f); fwrite(&byteRate, 4, 1, f);
  fwrite(&align, 2, 1, f); fwrite(&bits, 2, 1, f); fwrite("data", 1, 4, f); fwrite(&dataBytes, 4, 1, f);
  for (float v : x) {
    float c = v > 1.f ? 1.f : (v < -1.f ? -1.f : v);
    int16_t s = (int16_t)(c * 32767.f);
    fwrite(&s, 2, 1, f);
  }
  fclose(f);
  return true;
}

inline bool read16(const std::string& path, std::vector<float>& x, int& fs) {
  FILE* f = fopen(path.c_str(), "rb");
  if (!f) return false;
  std::vector<uint8_t> b;
  uint8_t tmp[65536];
  size_t k;
  while ((k = fread(tmp, 1, sizeof tmp, f)) > 0) b.insert(b.end(), tmp, tmp + k);
  fclose(f);
  if (b.size() < 44 || memcmp(b.data(), "RIFF", 4) || memcmp(b.data() + 8, "WAVE", 4)) return false;
  size_t p = 12;
  int ch = 1, bits = 16;
  while (p + 8 <= b.size()) {
    uint32_t len;
    memcpy(&len, &b[p + 4], 4);
    if (!memcmp(&b[p], "fmt ", 4)) {
      uint16_t c, bt;
      uint32_t r;
      memcpy(&c, &b[p + 10], 2); memcpy(&r, &b[p + 12], 4); memcpy(&bt, &b[p + 22], 2);
      ch = c; fs = (int)r; bits = bt;
    } else if (!memcmp(&b[p], "data", 4)) {
      if (bits != 16) return false;
      size_t n = std::min<size_t>(len, b.size() - p - 8) / 2 / ch;
      x.resize(n);
      for (size_t i = 0; i < n; ++i) {
        int16_t s;
        memcpy(&s, &b[p + 8 + i * 2 * ch], 2);
        x[i] = s / 32768.f;
      }
      return true;
    }
    p += 8 + len + (len & 1);
  }
  return false;
}

} // namespace wavio
