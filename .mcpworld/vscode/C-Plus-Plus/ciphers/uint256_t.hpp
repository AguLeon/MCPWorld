#pragma once

#include <array>
#include <cstdint>
#include <ostream>

namespace ciphers {

struct uint256_t {
    std::array<uint64_t, 4> words{};

    uint256_t() = default;
    explicit uint256_t(uint64_t value) {
        words[0] = value;
    }

    friend std::ostream &operator<<(std::ostream &os, const uint256_t &value) {
        os << "0x";
        for (auto it = value.words.rbegin(); it != value.words.rend(); ++it) {
            os << std::hex << *it;
        }
        return os;
    }
};

} // namespace ciphers
