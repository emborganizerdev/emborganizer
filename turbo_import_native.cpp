#include <algorithm>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <vector>

static std::string lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c){ return (char)std::tolower(c); });
    return s;
}

static std::set<std::string> parse_exts(const std::string& csv) {
    std::set<std::string> out;
    std::stringstream ss(csv);
    std::string item;
    while (std::getline(ss, item, ',')) {
        item = lower(item);
        if (!item.empty() && item[0] != '.') item = "." + item;
        if (!item.empty()) out.insert(item);
    }
    return out;
}

int main(int argc, char** argv) {
    if (argc >= 2 && std::string(argv[1]) == "--version") {
        std::cout << "TurboImport v1 native extension scanner\n";
        return 0;
    }
    if (argc < 3 || std::string(argv[1]) != "--filter") {
        std::cerr << "usage: turbo_import_native --filter .dst,.pes < suffixes.txt\n";
        return 2;
    }
    const auto supported = parse_exts(argv[2]);
    std::string suffix;
    long long idx = 0;
    while (std::getline(std::cin, suffix)) {
        suffix = lower(suffix);
        if (supported.find(suffix) != supported.end()) std::cout << idx << "\n";
        ++idx;
    }
    return 0;
}
