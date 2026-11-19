//! Fast physics for Pawn Engine. A line-by-line port of engine/physics.py, plus a grid so each body only
//! looks at the solids near it. The Python version stays as the reference and the fallback.
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use std::collections::HashMap;

const GRAVITY: f64 = 1800.0;
const MAX_FALL: f64 = 1500.0;
const SUBSTEP: f64 = 1.0 / 120.0;
const MAX_SUBSTEPS: i64 = 12;
const BOUNCE_MIN_SPEED: f64 = 80.0;
const ONE_WAY_GRACE: f64 = 6.0;
const SLOPE_SNAP: f64 = 14.0;
const CELL: f64 = 64.0;
const MARGIN: f64 = 40.0;

#[derive(Clone, Copy)]
struct Solid { x: f64, y: f64, w: f64, h: f64, id: i64, group: i64, mask: i64, up_right: bool }

struct Grid { cells: HashMap<(i32, i32), Vec<u32>>, items: Vec<Solid> }

fn cell(v: f64) -> i32 { (v / CELL).floor() as i32 }

impl Grid {
    fn new(items: Vec<Solid>) -> Self {
        let mut cells: HashMap<(i32, i32), Vec<u32>> = HashMap::new();
        for (i, s) in items.iter().enumerate() {
            let (x0, x1) = (cell(s.x - s.w / 2.0), cell(s.x + s.w / 2.0));
            let (y0, y1) = (cell(s.y - s.h / 2.0), cell(s.y + s.h / 2.0));
            for cx in x0..=x1 { for cy in y0..=y1 { cells.entry((cx, cy)).or_default().push(i as u32); } }
        }
        Grid { cells, items }
    }
    /// Indices (ascending, so results match the Python order) of solids that may touch the box.
    fn query(&self, x0: f64, y0: f64, x1: f64, y1: f64, out: &mut Vec<u32>) {
        out.clear();
        for cx in cell(x0)..=cell(x1) {
            for cy in cell(y0)..=cell(y1) {
                if let Some(v) = self.cells.get(&(cx, cy)) { out.extend_from_slice(v); }
            }
        }
        out.sort_unstable();
        out.dedup();
    }
}

fn overlap(ax: f64, ay: f64, aw: f64, ah: f64, bx: f64, by: f64, bw: f64, bh: f64) -> bool {
    (ax - bx).abs() * 2.0 < aw + bw - 0.01 && (ay - by).abs() * 2.0 < ah + bh - 0.01
}

fn rebound(speed: f64, bounce: f64) -> f64 {
    if bounce > 0.0 && speed.abs() * bounce >= BOUNCE_MIN_SPEED / 2.0 { -speed * bounce } else { 0.0 }
}

fn slope_surface(up_right: bool, sx: f64, sy: f64, sw: f64, sh: f64, x: f64) -> Option<f64> {
    let (left, right) = (sx - sw / 2.0, sx + sw / 2.0);
    if x < left || x > right { return None; }
    let bottom = sy + sh / 2.0;
    let t = if up_right { (x - left) / sw } else { (right - x) / sw };
    Some(bottom - t * sh)
}

struct Body { id: i64, x: f64, y: f64, px: f64, py: f64, w: f64, h: f64, vx: f64, vy: f64, bounce: f64,
              friction: f64, on_ground: bool, group: i64, mask: i64 }

fn agree(b: &Body, s: &Solid) -> bool {
    s.id != b.id && ((b.mask >> (s.group - 1)) & 1 == 1) && ((s.mask >> (b.group - 1)) & 1 == 1)
}

fn unpack(flat: &[f64], ramps: bool) -> Vec<Solid> {
    let stride = 8;
    flat.chunks_exact(stride).map(|c| Solid { x: c[0], y: c[1], w: c[2], h: c[3], id: c[4] as i64,
        group: (c[5] as i64).clamp(1, 32), mask: c[6] as i64, up_right: ramps && c[7] > 0.5 }).collect()
}

/// blocks / platforms / ramps: flat lists, 8 numbers each: x y w h id group mask slope(1 = up-right).
/// bodies: flat list, 14 numbers each: id x y prev_x prev_y w h vx vy bounce friction on_ground group mask.
/// Returns 5 numbers per body: x y vx vy on_ground.
#[pyfunction]
fn step(blocks: Vec<f64>, platforms: Vec<f64>, ramps: Vec<f64>, bodies: Vec<f64>, dt: f64) -> Vec<f64> {
    let blocks = Grid::new(unpack(&blocks, false));
    let platforms = Grid::new(unpack(&platforms, false));
    let ramps = Grid::new(unpack(&ramps, true));
    let n = ((dt / SUBSTEP).ceil() as i64).clamp(1, MAX_SUBSTEPS);
    let sub = dt / n as f64;
    let mut out = Vec::with_capacity(bodies.len() / 14 * 5);
    let mut cand: Vec<u32> = Vec::new();
    for c in bodies.chunks_exact(14) {
        let mut b = Body { id: c[0] as i64, x: c[1], y: c[2], px: c[3], py: c[4], w: c[5], h: c[6], vx: c[7], vy: c[8],
            bounce: c[9], friction: c[10], on_ground: c[11] > 0.5,
            group: (c[12] as i64).clamp(1, 32), mask: c[13] as i64 };
        let (px, py) = (b.px, b.py);
        let mut x = b.x + b.vx * dt;
        let mut y = b.y;
        // everything this body could touch this frame
        let vmax = b.vy.abs().max(MAX_FALL) * dt.max(sub) + b.vx.abs() * dt;
        let (qx0, qx1) = (x.min(px).min(b.x) - b.w - MARGIN, x.max(px).max(b.x) + b.w + MARGIN);
        let (qy0, qy1) = (y.min(py) - vmax - b.h - MARGIN, y.max(py) + vmax + b.h + MARGIN);
        let mut hit_side = false;

        blocks.query(qx0, qy0, qx1, qy1, &mut cand);
        let blk: Vec<Solid> = cand.iter().map(|&i| blocks.items[i as usize]).filter(|s| agree(&b, s)).collect();
        for s in &blk {
            if overlap(x, py, b.w, b.h, s.x, s.y, s.w, s.h) {
                if x > px { x = s.x - s.w / 2.0 - b.w / 2.0; hit_side = true; }
                else if x < px { x = s.x + s.w / 2.0 + b.w / 2.0; hit_side = true; }
            }
        }
        ramps.query(qx0, qy0, qx1, qy1, &mut cand);
        let rmp: Vec<Solid> = cand.iter().map(|&i| ramps.items[i as usize]).filter(|s| agree(&b, s)).collect();
        for s in &rmp {
            let high_right = s.up_right;
            let edge = if high_right { s.x + s.w / 2.0 } else { s.x - s.w / 2.0 };
            if !overlap(x, py, b.w, b.h, s.x, s.y, s.w, s.h) { continue; }
            if let Some(surf) = slope_surface(s.up_right, s.x, s.y, s.w, s.h, edge) {
                let feet = py + b.h / 2.0;
                if feet > surf + SLOPE_SNAP {
                    if high_right && x < px && x < edge + b.w / 2.0 && px >= edge { x = edge + b.w / 2.0; hit_side = true; }
                    else if !high_right && x > px && x > edge - b.w / 2.0 && px <= edge { x = edge - b.w / 2.0; hit_side = true; }
                }
            }
        }
        if hit_side { b.vx = rebound(b.vx, b.bounce); }
        if b.on_ground && b.friction > 0.0 && b.vx != 0.0 {
            b.vx -= b.vx * (b.friction * dt).min(1.0);
            if b.vx.abs() < 1.0 { b.vx = 0.0; }
        }
        platforms.query(qx0, qy0, qx1, qy1, &mut cand);
        let plt: Vec<Solid> = cand.iter().map(|&i| platforms.items[i as usize]).filter(|s| agree(&b, s)).collect();

        let mut grounded = false;
        for _ in 0..n {
            b.vy = (b.vy + GRAVITY * sub).min(MAX_FALL);
            let feet_before = y + b.h / 2.0;
            let mut ny = y + b.vy * sub;
            grounded = false;
            for s in &blk {
                if overlap(x, ny, b.w, b.h, s.x, s.y, s.w, s.h) {
                    if b.vy > 0.0 {
                        ny = s.y - s.h / 2.0 - b.h / 2.0;
                        b.vy = rebound(b.vy, b.bounce);
                        grounded = b.vy == 0.0;
                    } else {
                        ny = s.y + s.h / 2.0 + b.h / 2.0;
                        b.vy = rebound(b.vy, b.bounce);
                    }
                }
            }
            if b.vy >= 0.0 {
                for s in &plt {
                    let top = s.y - s.h / 2.0;
                    if overlap(x, ny, b.w, b.h, s.x, s.y, s.w, s.h) && feet_before <= top + ONE_WAY_GRACE && ny + b.h / 2.0 > top {
                        ny = top - b.h / 2.0;
                        b.vy = rebound(b.vy, b.bounce);
                        grounded = grounded || b.vy == 0.0;
                    }
                }
                for s in &rmp {
                    if let Some(surf) = slope_surface(s.up_right, s.x, s.y, s.w, s.h, x) {
                        let feet = ny + b.h / 2.0;
                        if feet >= surf && feet_before <= surf + SLOPE_SNAP {
                            ny = surf - b.h / 2.0;
                            b.vy = rebound(b.vy, b.bounce);
                            grounded = grounded || b.vy == 0.0;
                        }
                    }
                }
            }
            y = ny;
        }
        out.extend_from_slice(&[x, y, b.vx, b.vy, if grounded { 1.0 } else { 0.0 }]);
    }
    out
}

/// Turns particles into GPU instances (16 f32 each) as raw bytes.
/// parts: [x, y, vx, vy, age, life, rot, spin, size, seed] each. look: see engine/particles.py `look()`.
#[pyfunction]
fn pack_particles<'py>(py: Python<'py>, parts: Vec<Vec<f64>>, look: Vec<f64>, ox: f64, oy: f64) -> Bound<'py, PyBytes> {
    let (r0, g0, b0, a0, r1, g1, b1, a1) = (look[0], look[1], look[2], look[3], look[4], look[5], look[6], look[7]);
    let (size_end, opacity, kind) = (look[8], look[9], look[10]);
    let (u0, v0, u1, v1) = (look[11], look[12], look[13], look[14]);
    let cols = (look[15] as i64).max(1);
    let rows = (look[16] as i64).max(1);
    let cells = cols * rows;
    let mut out: Vec<f32> = Vec::with_capacity(parts.len() * 16);
    for p in &parts {
        if p.len() < 10 { continue; }
        let t = p[4] / p[5];
        let d = (p[8] * (1.0 + (size_end - 1.0) * t)).max(0.5);
        let (mut su, mut sv, mut eu, mut ev) = (0.0, 0.0, 0.0, 0.0);
        if kind >= 2.0 && kind != 5.0 {
            let i = ((p[9] * cells as f64) as i64) % cells;
            let cw = (u1 - u0) / cols as f64;
            let ch = (v1 - v0) / rows as f64;
            su = u0 + (i % cols) as f64 * cw;
            sv = v0 + (i / cols) as f64 * ch;
            eu = su + cw;
            ev = sv + ch;
        }
        let v = [p[0] + ox, p[1] + oy, d, d, p[6].to_radians(), 1.0, kind, 0.0,
                 r0 + (r1 - r0) * t, g0 + (g1 - g0) * t, b0 + (b1 - b0) * t, (a0 + (a1 - a0) * t) * opacity,
                 su, sv, eu, ev];
        out.extend(v.iter().map(|x| *x as f32));
    }
    let bytes: Vec<u8> = out.iter().flat_map(|f| f.to_ne_bytes()).collect();
    PyBytes::new(py, &bytes)
}

/// A* on a grid. blocked: w*h bytes (1 = wall). Returns [x0, y0, x1, y1, ...] from start to goal, or [] if there is no way.
/// Diagonal steps are only allowed when both side cells are free, so paths never cut wall corners.
#[pyfunction]
fn astar(blocked: Vec<u8>, w: i64, h: i64, sx: i64, sy: i64, gx: i64, gy: i64) -> Vec<i64> {
    use std::cmp::Reverse;
    use std::collections::BinaryHeap;
    if w <= 0 || h <= 0 || blocked.len() != (w * h) as usize { return vec![]; }
    let inside = |x: i64, y: i64| x >= 0 && y >= 0 && x < w && y < h;
    let idx = |x: i64, y: i64| (y * w + x) as usize;
    if !inside(sx, sy) || !inside(gx, gy) || blocked[idx(gx, gy)] != 0 { return vec![]; }
    let n = (w * h) as usize;
    let mut g = vec![f64::INFINITY; n];
    let mut from = vec![usize::MAX; n];
    let mut open = BinaryHeap::new();
    let hfun = |x: i64, y: i64| {
        let (dx, dy) = ((x - gx).abs() as f64, (y - gy).abs() as f64);
        dx.max(dy) + (std::f64::consts::SQRT_2 - 1.0) * dx.min(dy)
    };
    g[idx(sx, sy)] = 0.0;
    open.push((Reverse((hfun(sx, sy) * 1000.0) as i64), sx, sy));
    let dirs: [(i64, i64); 8] = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)];
    while let Some((_, x, y)) = open.pop() {
        if x == gx && y == gy {
            let mut path = vec![];
            let mut cur = idx(gx, gy);
            while cur != usize::MAX {
                path.push((cur as i64) / w);
                path.push((cur as i64) % w);
                cur = from[cur];
            }
            // path holds y,x pairs backwards: turn into x,y pairs from the start
            let mut out = Vec::with_capacity(path.len());
            for pair in path.chunks(2).rev() { out.push(pair[1]); out.push(pair[0]); }
            return out;
        }
        let gcur = g[idx(x, y)];
        for (dx, dy) in dirs.iter() {
            let (nx, ny) = (x + dx, y + dy);
            if !inside(nx, ny) || blocked[idx(nx, ny)] != 0 { continue; }
            if *dx != 0 && *dy != 0 && (blocked[idx(x + dx, y)] != 0 || blocked[idx(x, y + dy)] != 0) { continue; }
            let step = if *dx != 0 && *dy != 0 { std::f64::consts::SQRT_2 } else { 1.0 };
            let ng = gcur + step;
            if ng < g[idx(nx, ny)] {
                g[idx(nx, ny)] = ng;
                from[idx(nx, ny)] = idx(x, y);
                open.push((Reverse(((ng + hfun(nx, ny)) * 1000.0) as i64), nx, ny));
            }
        }
    }
    vec![]
}

#[pymodule]
fn pawn_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(step, m)?)?;
    m.add_function(wrap_pyfunction!(pack_particles, m)?)?;
    m.add_function(wrap_pyfunction!(astar, m)?)?;
    m.add("VERSION", "1.1.0")?;
    Ok(())
}
