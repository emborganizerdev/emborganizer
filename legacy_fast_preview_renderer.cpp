#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

struct RGB { unsigned char r, g, b; };
struct Segment { int x0, y0, x1, y1, r, g, b; };
struct RawPoint { float x, y; int32_t cmd; };

static inline int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }
static inline unsigned char clampu8(int v) { return (unsigned char)clampi(v, 0, 255); }

static inline void setpx(std::vector<RGB>& img, int w, int h, int x, int y, const RGB& c) {
    if ((unsigned)x < (unsigned)w && (unsigned)y < (unsigned)h) img[(size_t)y * (size_t)w + (size_t)x] = c;
}

static inline void fill_rect(std::vector<RGB>& img, int w, int h, int x0, int y0, int x1, int y1, const RGB& c) {
    x0 = clampi(x0, 0, w - 1); x1 = clampi(x1, 0, w - 1);
    y0 = clampi(y0, 0, h - 1); y1 = clampi(y1, 0, h - 1);
    if (x1 < x0 || y1 < y0) return;
    for (int y = y0; y <= y1; ++y) {
        RGB* row = img.data() + (size_t)y * (size_t)w;
        for (int x = x0; x <= x1; ++x) row[x] = c;
    }
}

static inline void fill_disc(std::vector<RGB>& img, int w, int h, int cx, int cy, int radius, const RGB& c) {
    if (radius <= 0) { setpx(img, w, h, cx, cy, c); return; }
    int r2 = radius * radius;
    int y0 = clampi(cy - radius, 0, h - 1), y1 = clampi(cy + radius, 0, h - 1);
    int x0 = clampi(cx - radius, 0, w - 1), x1 = clampi(cx + radius, 0, w - 1);
    for (int y = y0; y <= y1; ++y) {
        int dy = y - cy;
        RGB* row = img.data() + (size_t)y * (size_t)w;
        for (int x = x0; x <= x1; ++x) {
            int dx = x - cx;
            if (dx * dx + dy * dy <= r2) row[x] = c;
        }
    }
}

static inline int outcode(int x, int y, int w, int h) {
    int c = 0;
    if (x < 0) c |= 1; else if (x >= w) c |= 2;
    if (y < 0) c |= 4; else if (y >= h) c |= 8;
    return c;
}

static bool clip_line(int& x0, int& y0, int& x1, int& y1, int w, int h) {
    int c0 = outcode(x0, y0, w, h), c1 = outcode(x1, y1, w, h);
    while (true) {
        if (!(c0 | c1)) return true;
        if (c0 & c1) return false;
        int c = c0 ? c0 : c1;
        long long x = 0, y = 0;
        long long dx = (long long)x1 - x0;
        long long dy = (long long)y1 - y0;
        if (c & 8) { y = h - 1; x = x0 + dx * (y - y0) / (dy == 0 ? 1 : dy); }
        else if (c & 4) { y = 0; x = x0 + dx * (y - y0) / (dy == 0 ? 1 : dy); }
        else if (c & 2) { x = w - 1; y = y0 + dy * (x - x0) / (dx == 0 ? 1 : dx); }
        else { x = 0; y = y0 + dy * (x - x0) / (dx == 0 ? 1 : dx); }
        if (c == c0) { x0 = (int)x; y0 = (int)y; c0 = outcode(x0, y0, w, h); }
        else { x1 = (int)x; y1 = (int)y; c1 = outcode(x1, y1, w, h); }
    }
}

static void draw_line_fast(std::vector<RGB>& img, int w, int h, int x0, int y0, int x1, int y1, const RGB& c, int thickness) {
    if (!clip_line(x0, y0, x1, y1, w, h)) return;
    int radius = std::max(0, thickness / 2);
    if (x0 == x1 && y0 == y1) { fill_disc(img, w, h, x0, y0, radius, c); return; }
    if (y0 == y1) { fill_rect(img, w, h, std::min(x0, x1), y0 - radius, std::max(x0, x1), y0 + radius, c); return; }
    if (x0 == x1) { fill_rect(img, w, h, x0 - radius, std::min(y0, y1), x0 + radius, std::max(y0, y1), c); return; }

    int dx = std::abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -std::abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    while (true) {
        if (radius == 0) setpx(img, w, h, x0, y0, c);
        else fill_disc(img, w, h, x0, y0, radius, c);
        if (x0 == x1 && y0 == y1) break;
        int e2 = err << 1;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

static bool write_ppm(const std::string& path, const std::vector<RGB>& img, int w, int h) {
    std::ofstream out(path, std::ios::binary);
    if (!out) return false;
    out << "P6\n" << w << " " << h << "\n255\n";
    out.write(reinterpret_cast<const char*>(img.data()), (std::streamsize)(img.size() * sizeof(RGB)));
    return (bool)out;
}

static bool load_segments_text(const std::string& path, int& w, int& h, int& thickness, std::vector<Segment>& segs) {
    std::ifstream in(path);
    if (!in) return false;
    long long n = 0;
    in >> w >> h >> thickness >> n;
    if (w <= 0 || h <= 0 || w > 6000 || h > 6000 || n < 0 || n > 2000000) return false;
    segs.reserve((size_t)n);
    for (long long i = 0; i < n; ++i) {
        Segment s{};
        if (!(in >> s.x0 >> s.y0 >> s.x1 >> s.y1 >> s.r >> s.g >> s.b)) break;
        segs.push_back(s);
    }
    return true;
}

static bool load_segments_binary(const std::string& path, int& w, int& h, int& thickness, std::vector<Segment>& segs) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    char magic[8] = {0};
    in.read(magic, 8);
    if (!in || std::string(magic, magic + 6) != "EBSEG1") return false;
    int32_t iw = 0, ih = 0, it = 1, n = 0;
    in.read(reinterpret_cast<char*>(&iw), 4);
    in.read(reinterpret_cast<char*>(&ih), 4);
    in.read(reinterpret_cast<char*>(&it), 4);
    in.read(reinterpret_cast<char*>(&n), 4);
    if (!in || iw <= 0 || ih <= 0 || iw > 6000 || ih > 6000 || n < 0 || n > 2000000) return false;
    w = iw; h = ih; thickness = it;
    segs.resize((size_t)n);
    for (int32_t i = 0; i < n; ++i) {
        int32_t vals[7];
        in.read(reinterpret_cast<char*>(vals), sizeof(vals));
        if (!in) { segs.resize((size_t)i); break; }
        segs[(size_t)i] = Segment{vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6]};
    }
    return true;
}

static void draw_background(std::vector<RGB>& img, int w, int h) {
    // TURBOEMB v0.8.3: clean catalog background. Avoid grey borders in final previews
    // so the DST stitch paths look sharper and more like an exported design image.
    img.assign((size_t)w * (size_t)h, RGB{255, 255, 255});
}

static int cmdv(int raw, int mask) { return raw & mask; }

static bool load_raw_points(const std::string& path, int& size, int& line_width, int& max_segments, int& mask,
                            int& st, int& jump, int& trim, int& stop, int& color_change,
                            std::vector<RGB>& palette, std::vector<RawPoint>& pts) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    char magic[8] = {0};
    in.read(magic, 8);
    if (!in || std::string(magic, magic + 6) != "EBRAW1") return false;
    int32_t header[9] = {0};
    in.read(reinterpret_cast<char*>(header), sizeof(header));
    if (!in) return false;
    size = header[0]; line_width = header[1]; max_segments = header[2];
    mask = header[3]; st = header[4]; jump = header[5]; trim = header[6]; stop = header[7]; color_change = header[8];
    int32_t color_count = 0;
    in.read(reinterpret_cast<char*>(&color_count), 4);
    if (!in || color_count < 0 || color_count > 256) return false;
    palette.clear();
    palette.reserve((size_t)color_count);
    for (int32_t i = 0; i < color_count; ++i) {
        int32_t rgb[3];
        in.read(reinterpret_cast<char*>(rgb), sizeof(rgb));
        if (!in) return false;
        palette.push_back(RGB{clampu8(rgb[0]), clampu8(rgb[1]), clampu8(rgb[2])});
    }
    int32_t n = 0;
    in.read(reinterpret_cast<char*>(&n), 4);
    if (!in || size <= 0 || size > 6000 || n < 0 || n > 5000000) return false;
    pts.resize((size_t)n);
    for (int32_t i = 0; i < n; ++i) {
        float xy[2]; int32_t cmd;
        in.read(reinterpret_cast<char*>(xy), sizeof(xy));
        in.read(reinterpret_cast<char*>(&cmd), 4);
        if (!in) { pts.resize((size_t)i); break; }
        pts[(size_t)i] = RawPoint{xy[0], xy[1], cmd};
    }
    return true;
}

static bool render_raw(const std::string& raw_path, const std::string& ppm_path, const std::string& meta_path) {
    int size = 560, line_width = 1, max_segments = 18000, mask = 0xff;
    int STITCH = 0, JUMP = 1, TRIM = 2, STOP = 3, COLOR_CHANGE = 5;
    std::vector<RGB> file_palette;
    std::vector<RawPoint> pts;
    if (!load_raw_points(raw_path, size, line_width, max_segments, mask, STITCH, JUMP, TRIM, STOP, COLOR_CHANGE, file_palette, pts)) return false;

    float minx = std::numeric_limits<float>::infinity(), miny = std::numeric_limits<float>::infinity();
    float maxx = -std::numeric_limits<float>::infinity(), maxy = -std::numeric_limits<float>::infinity();
    long long stitch_count = 0, jump_count = 0, trim_count = 0, color_changes = 0, segment_count = 0;
    bool have_last = false;
    for (const RawPoint& p : pts) {
        int c = cmdv(p.cmd, mask);
        if (c == STITCH) {
            stitch_count++;
            minx = std::min(minx, p.x); maxx = std::max(maxx, p.x);
            miny = std::min(miny, p.y); maxy = std::max(maxy, p.y);
            if (have_last) segment_count++;
            have_last = true;
        } else if (c == JUMP) { jump_count++; have_last = false; }
        else if (c == TRIM) { trim_count++; have_last = false; }
        else if (c == COLOR_CHANGE || c == STOP) { color_changes++; have_last = false; }
        else { have_last = false; }
    }
    if (stitch_count < 2 || !std::isfinite(minx) || maxx <= minx || maxy <= miny) return false;

    const int w = size, h = size;
    int margin = std::max(22, (int)(size * 0.07));
    float scale = std::min((size - margin * 2) / (maxx - minx), (size - margin * 2) / (maxy - miny));
    if (!std::isfinite(scale) || scale <= 0) return false;
    int draw_step = std::max(1, (int)std::ceil((double)std::max<long long>(1, segment_count) / (double)std::max(1, max_segments)));

    static const RGB default_palette[] = {
        {8,47,73},{220,38,38},{8,145,178},{22,163,74},{245,158,11},{124,58,237},
        {219,39,119},{15,23,42},{14,165,233},{249,115,22},{20,184,166},{190,24,93},
        {37,99,235},{132,204,22},{217,70,239},{120,113,108}
    };
    const bool has_file_palette = !file_palette.empty();

    std::vector<RGB> img;
    draw_background(img, w, h);
    int t = clampi(line_width, 1, 8);
    bool have_prev = false;
    float px = 0, py = 0;
    int color_idx = 0;
    long long seg_i = 0, drawn = 0;
    for (const RawPoint& p : pts) {
        int c = cmdv(p.cmd, mask);
        if (c == STITCH) {
            if (have_prev) {
                seg_i++;
                if (((seg_i - 1) % draw_step) == 0) {
                    int x0 = (int)((px - minx) * scale + margin + 0.5f);
                    int y0 = (int)((py - miny) * scale + margin + 0.5f);
                    int x1 = (int)((p.x - minx) * scale + margin + 0.5f);
                    int y1 = (int)((p.y - miny) * scale + margin + 0.5f);
                    const RGB& cc = has_file_palette ? file_palette[(size_t)(color_idx % (int)file_palette.size())] : default_palette[color_idx % (sizeof(default_palette)/sizeof(default_palette[0]))];
                    draw_line_fast(img, w, h, x0, y0, x1, y1, cc, t);
                    drawn++;
                }
            }
            px = p.x; py = p.y; have_prev = true;
        } else if (c == COLOR_CHANGE || c == STOP) { color_idx++; have_prev = false; }
        else { have_prev = false; }
    }
    if (!write_ppm(ppm_path, img, w, h)) return false;

    std::ofstream meta(meta_path);
    if (meta) {
        meta << "{\n";
        meta << "\"stitches\":" << stitch_count << ",\n";
        meta << "\"jumps\":" << jump_count << ",\n";
        meta << "\"trims\":" << trim_count << ",\n";
        meta << "\"color_changes\":" << color_changes << ",\n";
        meta << "\"colors\":" << std::max<long long>(1, color_changes + 1) << ",\n";
        meta << std::fixed << std::setprecision(1);
        meta << "\"width_mm\":" << ((maxx - minx) / 10.0) << ",\n";
        meta << "\"height_mm\":" << ((maxy - miny) / 10.0) << ",\n";
        meta << "\"segments\":" << segment_count << ",\n";
        meta << "\"drawn_segments\":" << drawn << ",\n";
        meta << "\"max_segments\":" << max_segments << ",\n";
        meta << "\"palette_from_file\":" << (has_file_palette ? "true" : "false") << ",\n";
        meta << "\"engine\":\"turboemb_cpp_raw_v083_clean_accuracy\"\n";
        meta << "}\n";
    }
    return true;
}

static bool render_segments(const std::string& input, const std::string& output, bool binary) {
    int w = 0, h = 0, thickness = 1;
    std::vector<Segment> segs;
    bool ok = binary ? load_segments_binary(input, w, h, thickness, segs) : load_segments_text(input, w, h, thickness, segs);
    if (!ok) return false;
    std::vector<RGB> img;
    draw_background(img, w, h);
    const int t = clampi(thickness, 1, 8);
    for (const Segment& s : segs) {
        RGB c{clampu8(s.r), clampu8(s.g), clampu8(s.b)};
        draw_line_fast(img, w, h, s.x0, s.y0, s.x1, s.y1, c, t);
    }
    return write_ppm(output, img, w, h);
}

int main(int argc, char** argv) {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    if (argc == 5 && std::string(argv[1]) == "--raw") {
        return render_raw(argv[2], argv[3], argv[4]) ? 0 : 6;
    }
    bool binary = false;
    std::string input, output;
    if (argc == 4 && std::string(argv[1]) == "--bin") { binary = true; input = argv[2]; output = argv[3]; }
    else if (argc == 3) { input = argv[1]; output = argv[2]; }
    else { std::cerr << "usage: fast_preview_renderer [--bin] segments output.ppm OR --raw input.ebraw output.ppm output.json\n"; return 2; }
    return render_segments(input, output, binary) ? 0 : 5;
}
