#include <iostream>
#include <string>
#include <unordered_set>

int main(int argc, char** argv) {
    if (argc >= 2 && std::string(argv[1]) == "--version") {
        std::cout << "TurboSync v1 native helper\n";
        return 0;
    }
    if (argc >= 2 && std::string(argv[1]) == "--dedupe") {
        std::unordered_set<std::string> seen;
        std::string key;
        long long idx = 0;
        while (std::getline(std::cin, key)) {
            if (seen.find(key) == seen.end()) {
                seen.insert(key);
                std::cout << idx << "\n";
            }
            ++idx;
        }
        return 0;
    }
    std::cerr << "usage: sync_native --dedupe < keys.txt\n";
    return 2;
}
