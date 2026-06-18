// imgs_engine.cpp
// IMGS Engine native first-pass scorer for EMBORGANIZER Image Searcher.
// Reads a plain text batch and returns candidate scores quickly.
// Format:
//   <dimension>\n
//   <query vector values separated by spaces>\n
//   <candidate_id>\t<target vector values separated by spaces>\n
// Output:
//   <candidate_id>\t<score 0-100>\n
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

static std::vector<double> parse_vec(const std::string &line, int expected) {
    std::vector<double> out;
    out.reserve(expected > 0 ? expected : 256);
    std::istringstream ss(line);
    double v;
    while (ss >> v) out.push_back(v);
    return out;
}

static double score_l1(const std::vector<double> &a, const std::vector<double> &b) {
    if (a.empty() || b.empty()) return 0.0;
    const size_t n = std::min(a.size(), b.size());
    if (n == 0) return 0.0;
    double total = 0.0;
    for (size_t i = 0; i < n; ++i) {
        total += std::fabs(a[i] - b[i]);
    }
    total += std::fabs(static_cast<double>(a.size()) - static_cast<double>(b.size())) * 0.05;
    double dist = total / std::max<size_t>(1, n);
    if (dist < 0.0) dist = 0.0;
    if (dist > 1.0) dist = 1.0;
    return (1.0 - dist) * 100.0;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string line;
    if (!std::getline(std::cin, line)) return 1;
    int dim = std::atoi(line.c_str());
    if (dim <= 0 || dim > 100000) return 2;

    if (!std::getline(std::cin, line)) return 3;
    std::vector<double> query = parse_vec(line, dim);
    if (query.empty()) return 4;

    std::cout.setf(std::ios::fixed);
    std::cout << std::setprecision(4);

    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        std::string id;
        std::string vec_text;
        size_t tab = line.find('\t');
        if (tab == std::string::npos) continue;
        id = line.substr(0, tab);
        vec_text = line.substr(tab + 1);
        std::vector<double> target = parse_vec(vec_text, dim);
        if (target.empty()) continue;
        double score = score_l1(query, target);
        std::cout << id << '\t' << score << '\n';
    }
    return 0;
}
